from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.agreement_guidance import semantic_target
from app.domain.understanding_choices import (
    MAX_UNDERSTANDING_QUESTIONS,
    build_question_definition,
    select_understanding_terms,
    semantic_meaning_fingerprint,
)
from app.schemas.analysis import (
    AgreementFacet,
    AgreementTerm,
    AgreementTopic,
    EvidenceReference,
    MeaningState,
    ParticipantPosition,
    ParticipantTermStatus,
    PartyRole,
)
from app.schemas.understanding import (
    UnderstandingOptionKind,
    UnderstandingQuestionKind,
)

_ITEM_PARTS = {
    "scope.work": (AgreementTopic.SCOPE, AgreementFacet.WORK),
    "price.amount": (AgreementTopic.PRICE, AgreementFacet.AMOUNT),
    "materials.inclusion": (AgreementTopic.MATERIALS, AgreementFacet.INCLUSION),
    "timing.start": (AgreementTopic.TIMING, AgreementFacet.START),
    "completion.deadline": (AgreementTopic.COMPLETION, AgreementFacet.DEADLINE),
    "payment.timing": (AgreementTopic.PAYMENT, AgreementFacet.TIMING),
    "responsibilities.assignment": (
        AgreementTopic.RESPONSIBILITIES,
        AgreementFacet.ASSIGNMENT,
    ),
    "additional_work.policy": (
        AgreementTopic.ADDITIONAL_WORK,
        AgreementFacet.POLICY,
    ),
}


def _term(
    item_key: str,
    summary: str,
    *,
    state: MeaningState = MeaningState.ALIGNED,
    hirer_position: str | None = None,
    worker_position: str | None = None,
) -> AgreementTerm:
    topic, facet = _ITEM_PARTS[item_key]
    supplied_positions = {
        PartyRole.HIRER: hirer_position,
        PartyRole.WORKER: worker_position,
    }
    if state == MeaningState.NOT_DISCUSSED:
        supplied_positions = {role: None for role in PartyRole}
    elif state == MeaningState.STATED_BY_ONE:
        supplied_positions[PartyRole.WORKER] = None
    else:
        supplied_positions = {
            role: value or summary for role, value in supplied_positions.items()
        }

    timestamp = datetime(2026, 7, 17, 9, tzinfo=UTC)
    positions: list[ParticipantPosition] = []
    evidence: list[EvidenceReference] = []
    for order, role in enumerate(PartyRole, start=1):
        position_summary = supplied_positions[role]
        if position_summary is None:
            continue
        message_id = f"message-{item_key.replace('.', '-')}-{role.value}"
        positions.append(
            ParticipantPosition(
                participant_id=role.value,
                role=role,
                summary=position_summary,
                evidence_message_ids=[message_id],
            )
        )
        evidence.append(
            EvidenceReference(
                source="transcript",
                reference_id=message_id,
                participant_id=role.value,
                role=role,
                speaker_name=(
                    "Homeowner" if role == PartyRole.HIRER else "Electrician"
                ),
                message_id=message_id,
                original_text=position_summary,
                original_language="en",
                order=order,
                timestamp=timestamp,
            )
        )

    if state == MeaningState.ALIGNED:
        statuses = {role: ParticipantTermStatus.CONFIRMED for role in PartyRole}
    elif state == MeaningState.CONFLICTING:
        statuses = {role: ParticipantTermStatus.CONFLICTING for role in PartyRole}
    elif state == MeaningState.STATED_BY_ONE:
        statuses = {
            PartyRole.HIRER: ParticipantTermStatus.STATED,
            PartyRole.WORKER: ParticipantTermStatus.NOT_STATED,
        }
    else:
        statuses = {role: ParticipantTermStatus.NOT_STATED for role in PartyRole}

    return AgreementTerm(
        id=f"term-{item_key.replace('.', '-')}",
        analysis_item_key=item_key,
        topic=topic,
        facet=facet,
        label=item_key.replace(".", " ").title(),
        summary=summary,
        state=state,
        participant_positions=positions,
        participant_confirmations=statuses,
        evidence_message_ids=[item.message_id for item in evidence if item.message_id],
        evidence=evidence,
        clarification_target=(
            item_key
            if state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
            else None
        ),
    )


def test_clarification_choices_are_stable_and_derived_from_actual_positions() -> None:
    materials = _term(
        "materials.inclusion",
        "The participants stated different price coverage.",
        state=MeaningState.CONFLICTING,
        hirer_position="₹1,200 includes replacement parts.",
        worker_position="₹1,200 is labour only; replacement parts cost extra.",
    )

    first = build_question_definition(
        materials,
        [materials],
        kind=UnderstandingQuestionKind.CLARIFICATION,
    )
    repeated = build_question_definition(
        materials,
        [materials],
        kind=UnderstandingQuestionKind.CLARIFICATION,
        prompt_override="Which recorded price coverage did you understand?",
    )

    assert [item.option.id for item in first.options] == [
        item.option.id for item in repeated.options
    ]
    assert [item.option.kind for item in first.options] == [
        UnderstandingOptionKind.RECORDED_POSITION,
        UnderstandingOptionKind.RECORDED_POSITION,
        UnderstandingOptionKind.OTHER,
        UnderstandingOptionKind.UNSURE,
    ]
    assert [item.semantic_value for item in first.options[:2]] == [
        "₹1,200 includes replacement parts.",
        "₹1,200 is labour only; replacement parts cost extra.",
    ]
    assert [item.option.label for item in first.options[-2:]] == [
        "Something else",
        "I'm not sure",
    ]
    assert first.evidence_reference_ids == tuple(materials.evidence_message_ids)


def test_meaning_identity_is_stage_independent_but_changes_with_meaning() -> None:
    scope = _term("scope.work", "Repair the fan and two switches.")
    clarification = build_question_definition(
        scope,
        [scope],
        kind=UnderstandingQuestionKind.CLARIFICATION,
    )
    understanding = build_question_definition(
        scope,
        [scope],
        kind=UnderstandingQuestionKind.UNDERSTANDING_CHECK,
    )

    assert clarification.meaning_fingerprint == understanding.meaning_fingerprint
    assert clarification.question_fingerprint != understanding.question_fingerprint

    changed = _term("scope.work", "Replace the fan and both switches.")
    assert semantic_meaning_fingerprint(scope, [scope]) != (
        semantic_meaning_fingerprint(changed, [changed])
    )


def test_understanding_selection_deduplicates_one_semantic_commitment() -> None:
    price_coverage = _term(
        "price.amount",
        "The ₹1,200 price includes replacement materials.",
    )
    materials = _term(
        "materials.inclusion",
        "Replacement materials are included in the ₹1,200 price.",
    )
    scope = _term("scope.work", "Repair the fan and two switches.")
    terms = [scope, price_coverage, materials]

    selected = select_understanding_terms(terms, excluded_meanings=set())

    targets = [semantic_target(item) for item in selected]
    assert len(targets) == len(set(targets))
    assert targets.count("materials.inclusion") == 1
    coverage = next(
        item for item in selected if semantic_target(item) == "materials.inclusion"
    )
    assert coverage.analysis_item_key == "materials.inclusion"
    coverage_questions = [
        item for item in selected if semantic_target(item) == "materials.inclusion"
    ]
    assert [item.analysis_item_key for item in coverage_questions] == [
        "materials.inclusion"
    ]


def test_completed_meaning_is_excluded_without_excluding_a_changed_meaning() -> None:
    original = _term("scope.work", "Repair the fan and two switches.")
    original_key = (
        semantic_target(original),
        semantic_meaning_fingerprint(original, [original]),
    )

    assert (
        select_understanding_terms([original], excluded_meanings={original_key}) == []
    )

    changed = _term("scope.work", "Replace the fan and both switches.")
    assert select_understanding_terms([changed], excluded_meanings={original_key}) == [
        changed
    ]


def test_understanding_questions_respect_global_and_remaining_limits() -> None:
    terms = [
        _term("scope.work", "Repair the fan and two switches."),
        _term("price.amount", "Labour costs ₹1,200."),
        _term("materials.inclusion", "Replacement parts cost extra."),
        _term("timing.start", "Work starts today."),
        _term("payment.timing", "Payment is due after completion."),
    ]

    assert len(select_understanding_terms(terms, excluded_meanings=set())) == (
        MAX_UNDERSTANDING_QUESTIONS
    )
    assert (
        len(
            select_understanding_terms(
                terms,
                excluded_meanings=set(),
                max_questions=1,
            )
        )
        == 1
    )
    assert (
        select_understanding_terms(
            terms,
            excluded_meanings=set(),
            max_questions=0,
        )
        == []
    )


@pytest.mark.parametrize(
    "state",
    [MeaningState.NOT_DISCUSSED, MeaningState.CONFLICTING],
)
def test_optional_or_unresolved_terms_are_not_mandatory_quizzes(
    state: MeaningState,
) -> None:
    completion = _term(
        "completion.deadline",
        (
            "No completion time was discussed."
            if state == MeaningState.NOT_DISCUSSED
            else "The participants stated different completion times."
        ),
        state=state,
        hirer_position="Finish today." if state == MeaningState.CONFLICTING else None,
        worker_position=(
            "Finish tomorrow." if state == MeaningState.CONFLICTING else None
        ),
    )
    scope = _term("scope.work", "Repair the fan and two switches.")

    assert select_understanding_terms([completion, scope], excluded_meanings=set()) == [
        scope
    ]
