from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final

from app.domain.agreement_guidance import (
    agreement_semantic_fingerprint,
    clarification_priority,
    normalize_meaning_text,
    semantic_target,
)
from app.schemas.analysis import AgreementTerm, MeaningState, PartyRole
from app.schemas.understanding import (
    UnderstandingOption,
    UnderstandingOptionKind,
    UnderstandingQuestionKind,
)

MAX_UNDERSTANDING_QUESTIONS: Final = 3

_HIGH_IMPACT_KEYS: Final = frozenset(
    {
        "scope.work",
        "price.amount",
        "materials.inclusion",
        "timing.start",
        "completion.deadline",
        "payment.timing",
        "responsibilities.assignment",
        "additional_work.policy",
    }
)


@dataclass(frozen=True)
class OptionDefinition:
    option: UnderstandingOption
    semantic_value: str


@dataclass(frozen=True)
class QuestionDefinition:
    semantic_target: str
    meaning_fingerprint: str
    question_fingerprint: str
    prompt: str
    options: tuple[OptionDefinition, ...]
    evidence_reference_ids: tuple[str, ...]


def build_question_definition(
    term: AgreementTerm,
    all_terms: list[AgreementTerm],
    *,
    kind: UnderstandingQuestionKind,
    prompt_override: str | None = None,
) -> QuestionDefinition:
    target = semantic_target(term)
    meaning_fingerprint = semantic_meaning_fingerprint(term, all_terms)
    question_fingerprint = semantic_question_fingerprint(term, all_terms, kind=kind)
    positions = _meaning_options(term, kind=kind)
    option_definitions = [
        _option_definition(
            question_fingerprint,
            label=label,
            semantic_value=semantic_value,
            kind=option_kind,
        )
        for label, semantic_value, option_kind in positions
    ]
    option_definitions.extend(
        [
            _option_definition(
                question_fingerprint,
                label="Something else",
                semantic_value="other",
                kind=UnderstandingOptionKind.OTHER,
            ),
            _option_definition(
                question_fingerprint,
                label="I'm not sure",
                semantic_value="unsure",
                kind=UnderstandingOptionKind.UNSURE,
            ),
        ]
    )
    prompt = prompt_override or _prompt(term, kind=kind)
    return QuestionDefinition(
        semantic_target=target,
        meaning_fingerprint=meaning_fingerprint,
        question_fingerprint=question_fingerprint,
        prompt=prompt,
        options=tuple(option_definitions),
        evidence_reference_ids=tuple(
            dict.fromkeys(item.reference_id for item in term.evidence)
        ),
    )


def select_understanding_terms(
    terms: list[AgreementTerm],
    *,
    excluded_meanings: set[tuple[str, str]],
    max_questions: int = MAX_UNDERSTANDING_QUESTIONS,
) -> list[AgreementTerm]:
    if max_questions <= 0:
        return []
    grouped: dict[str, AgreementTerm] = {}
    for term in sorted(terms, key=clarification_priority):
        target = semantic_target(term)
        if (
            term.analysis_item_key not in _HIGH_IMPACT_KEYS
            or term.state != MeaningState.ALIGNED
            or (target, semantic_meaning_fingerprint(term, terms)) in excluded_meanings
        ):
            continue
        # A semantic commitment can span adjacent facets (for example, a price
        # summary that also says whether materials are included). Prefer the
        # facet that owns the semantic target so the question and any later
        # mutation remain attached to the precise agreement item.
        if target not in grouped or term.analysis_item_key == target:
            grouped[target] = term

    candidates = list(grouped.values())
    # Simple service agreements should feel like a quick check. Reserve the
    # third question for unusually broad agreements with at least five distinct
    # high-impact commitments.
    preferred_limit = 3 if len(candidates) >= 5 else 2
    return candidates[
        : min(preferred_limit, MAX_UNDERSTANDING_QUESTIONS, max_questions)
    ]


def semantic_question_fingerprint(
    term: AgreementTerm,
    all_terms: list[AgreementTerm],
    *,
    kind: UnderstandingQuestionKind,
) -> str:
    return _hash(
        {
            "schema": "meaning-question-v1",
            "kind": kind.value,
            "meaning_fingerprint": semantic_meaning_fingerprint(term, all_terms),
        }
    )


def semantic_meaning_fingerprint(
    term: AgreementTerm,
    all_terms: list[AgreementTerm],
) -> str:
    target = semantic_target(term)
    related = [item for item in all_terms if semantic_target(item) == target]
    payload = {
        "schema": "semantic-commitment-v1",
        "semantic_target": target,
        "meaning": agreement_semantic_fingerprint(related),
    }
    return _hash(payload)


def _meaning_options(
    term: AgreementTerm,
    *,
    kind: UnderstandingQuestionKind,
) -> list[tuple[str, str, UnderstandingOptionKind]]:
    if kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK:
        return [
            (
                term.summary,
                term.summary,
                UnderstandingOptionKind.RECORDED_MEANING,
            )
        ]

    if term.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}:
        values: list[tuple[str, str, UnderstandingOptionKind]] = []
        seen: set[str] = set()
        by_role = {position.role: position for position in term.participant_positions}
        for role in PartyRole:
            position = by_role.get(role)
            if position is None:
                continue
            normalized = normalize_meaning_text(position.summary)
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append(
                (
                    position.summary,
                    position.summary,
                    UnderstandingOptionKind.RECORDED_POSITION,
                )
            )
        if values:
            return values[:2]
    return [
        (
            term.summary,
            term.summary,
            UnderstandingOptionKind.RECORDED_MEANING,
        )
    ]


def _prompt(term: AgreementTerm, *, kind: UnderstandingQuestionKind) -> str:
    if kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK:
        if term.analysis_item_key == "materials.inclusion":
            return "Which statement matches what you understood about the price?"
        return (
            f"Which statement matches what you understood about {term.label.lower()}?"
        )
    templates = {
        "scope.work": "What work did you understand was included?",
        "price.amount": "What price amount did you understand was agreed?",
        "materials.inclusion": "What will the recorded price cover?",
        "timing.start": "When did you understand the work would start?",
        "completion.deadline": "When did you understand the work would be completed?",
        "payment.timing": "When did you understand payment would be due?",
        "responsibilities.assignment": (
            "Who did you understand was responsible for this item?"
        ),
        "additional_work.policy": (
            "What should happen before additional work or cost?"
        ),
    }
    return templates.get(
        term.analysis_item_key,
        f"What did you understand about {term.label.lower()}?",
    )


def _option_definition(
    question_fingerprint: str,
    *,
    label: str,
    semantic_value: str,
    kind: UnderstandingOptionKind,
) -> OptionDefinition:
    option_hash = _hash(
        {
            "schema": "meaning-option-v1",
            "question": question_fingerprint,
            "kind": kind.value,
            "semantic_value": normalize_meaning_text(semantic_value),
        }
    )
    return OptionDefinition(
        option=UnderstandingOption(
            id=f"option-{option_hash[:24]}",
            label=label,
            kind=kind,
        ),
        semantic_value=semantic_value,
    )


def _hash(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(serialized).hexdigest()
