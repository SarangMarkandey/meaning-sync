from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Sequence

from app.schemas.analysis import (
    AgreementTerm,
    MeaningState,
    ParticipantTermStatus,
    PartyRole,
)

# These are product rules, not model judgments. A "required" issue still may be
# left explicitly unresolved; required means that the guided flow surfaces it
# before optional, not that MeaningSync forces agreement.
CRITICAL_ONE_SIDED_ITEM_KEYS = frozenset(
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

_ITEM_PRIORITY = {
    "scope.work": 0,
    "price.amount": 10,
    "materials.inclusion": 20,
    "timing.start": 30,
    "completion.deadline": 31,
    "payment.timing": 40,
    "responsibilities.assignment": 50,
    "additional_work.policy": 51,
    "warranty.coverage": 60,
    "cancellation.policy": 61,
    "other.detail": 70,
}

_COVERAGE_NOUNS = re.compile(r"\b(parts?|materials?|replacement)\b")
_COVERAGE_RELATIONS = re.compile(
    r"\b(include[ds]?|including|cover(?:s|ed|age)?|separate(?:ly)?|extra)\b"
)
_NON_WORD = re.compile(r"[^\w\u20b9]+", flags=re.UNICODE)


def normalize_meaning_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(_NON_WORD.sub(" ", normalized).split())


def is_required_issue(term: AgreementTerm) -> bool:
    if term.state == MeaningState.CONFLICTING:
        return True
    return (
        term.state == MeaningState.STATED_BY_ONE
        and term.analysis_item_key in CRITICAL_ONE_SIDED_ITEM_KEYS
    )


def required_issue_keys(terms: Sequence[AgreementTerm]) -> list[str]:
    return [
        term.analysis_item_key
        for term in sorted(terms, key=clarification_priority)
        if is_required_issue(term)
    ]


def optional_item_keys(
    terms: Sequence[AgreementTerm],
    mutually_not_applicable: Iterable[str] = (),
) -> list[str]:
    excluded = set(mutually_not_applicable)
    return [
        term.analysis_item_key
        for term in sorted(terms, key=clarification_priority)
        if term.analysis_item_key not in excluded
        and (
            term.state == MeaningState.NOT_DISCUSSED
            or (
                term.state == MeaningState.STATED_BY_ONE and not is_required_issue(term)
            )
        )
    ]


def clarification_priority(term: AgreementTerm) -> tuple[int, str]:
    return (_ITEM_PRIORITY.get(term.analysis_item_key, 100), term.analysis_item_key)


def semantic_target(term: AgreementTerm) -> str:
    if term.analysis_item_key == "materials.inclusion":
        return "materials.inclusion"
    if term.analysis_item_key != "price.amount":
        return term.analysis_item_key

    meaning = " ".join(
        [term.summary, *(position.summary for position in term.participant_positions)]
    ).casefold()
    if _COVERAGE_NOUNS.search(meaning) and _COVERAGE_RELATIONS.search(meaning):
        return "materials.inclusion"
    return term.analysis_item_key


def ordered_clarification_candidates(
    terms: Sequence[AgreementTerm],
) -> list[AgreementTerm]:
    required = [term for term in terms if is_required_issue(term)]
    grouped: dict[str, list[AgreementTerm]] = {}
    for term in required:
        grouped.setdefault(semantic_target(term), []).append(term)

    representatives: list[AgreementTerm] = []
    for target, group in grouped.items():
        exact = next(
            (term for term in group if term.analysis_item_key == target),
            None,
        )
        representatives.append(exact or min(group, key=clarification_priority))
    return sorted(representatives, key=clarification_priority)


def clarification_fingerprint(
    term: AgreementTerm, all_terms: Sequence[AgreementTerm]
) -> str:
    target = semantic_target(term)
    related = [
        candidate
        for candidate in all_terms
        if semantic_target(candidate) == target and is_required_issue(candidate)
    ]
    payload = {
        "schema": "clarification-fingerprint-v1",
        "semantic_target": target,
        "terms": [
            _term_meaning_payload(item)
            for item in sorted(related, key=lambda item: item.analysis_item_key)
        ],
    }
    return _hash_payload(payload)


def agreement_semantic_fingerprint(
    terms: Sequence[AgreementTerm], mutually_not_applicable: Iterable[str] = ()
) -> str:
    payload = {
        "schema": "agreement-meaning-v1",
        "terms": [
            _term_meaning_payload(term)
            for term in sorted(terms, key=lambda item: item.analysis_item_key)
        ],
        "mutually_not_applicable": sorted(set(mutually_not_applicable)),
    }
    return _hash_payload(payload)


def addressed_participants(term: AgreementTerm) -> list[PartyRole]:
    if term.state == MeaningState.CONFLICTING:
        return [PartyRole.HIRER, PartyRole.WORKER]
    if term.state == MeaningState.STATED_BY_ONE:
        missing = [
            role
            for role in PartyRole
            if term.participant_confirmations[role] == ParticipantTermStatus.NOT_STATED
        ]
        if missing:
            return missing
        stated = {position.role for position in term.participant_positions}
        return [role for role in PartyRole if role not in stated]
    return []


def neutral_question_and_options(term: AgreementTerm) -> tuple[str, list[str]]:
    templates: dict[str, tuple[str, list[str]]] = {
        "scope.work": (
            "Does the recorded scope of work match your understanding?",
            ["Yes, it matches", "No, I understand the scope differently"],
        ),
        "price.amount": (
            "What price amount did you understand was agreed?",
            [],
        ),
        "materials.inclusion": (
            "Does the price include replacement parts, or are they charged separately?",
            ["Parts are included", "Parts are charged separately"],
        ),
        "timing.start": ("When did you understand the work would start?", []),
        "completion.deadline": (
            "When did you understand the work would be completed?",
            [],
        ),
        "payment.timing": ("When did you understand payment would be due?", []),
        "responsibilities.assignment": (
            "Who did you understand was responsible for this item?",
            [],
        ),
        "additional_work.policy": (
            "What did you understand would happen before additional work or cost?",
            [],
        ),
        "warranty.coverage": ("What warranty coverage did you each understand?", []),
        "cancellation.policy": (
            "What cancellation arrangement did you each understand?",
            [],
        ),
    }
    return templates.get(
        term.analysis_item_key,
        (f"What did you each understand about {term.label.casefold()}?", []),
    )


def _term_meaning_payload(term: AgreementTerm) -> dict[str, object]:
    return {
        "item_key": term.analysis_item_key,
        "state": term.state.value,
        "positions": [
            {
                "participant_id": position.participant_id,
                "role": position.role.value,
                "summary": normalize_meaning_text(position.summary),
            }
            for position in sorted(
                term.participant_positions,
                key=lambda item: (item.participant_id, item.role.value),
            )
        ],
        "statuses": {
            role.value: term.participant_confirmations[role].value for role in PartyRole
        },
    }


def _hash_payload(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
