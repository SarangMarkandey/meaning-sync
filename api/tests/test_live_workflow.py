from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.live_sessions import (
    get_live_session as api_get_live_session,
)
from app.api.live_sessions import (
    start_understanding_check as api_start_understanding_check,
)
from app.repositories import InMemoryLiveSessionRepository
from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AgreementFacet,
    AgreementTopic,
    AnalysisMessage,
    AnalysisParticipant,
    MeaningState,
    ModelAgreementTerm,
    ModelParticipantPosition,
    PartyRole,
)
from app.schemas.understanding import (
    LeaveQuestionUnresolvedSubmission,
    UnderstandingOptionKind,
    UnderstandingOutcomeState,
    UnderstandingQuestionKind,
    UnderstandingQuestionStatus,
    UnderstandingReviewResult,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AnalyzeLiveSessionSubmission,
    ConfirmationDecision,
    ConfirmationSubmission,
    IssueReceiptSubmission,
    LiveSessionCreate,
    LiveSessionStage,
    OptionalDetailsReviewedSubmission,
    ParticipantReviewStatus,
    ReceiptStatus,
    StartUnderstandingCheckSubmission,
    WorkflowErrorCode,
)
from app.services.analyzers.validation import build_analysis_response
from app.services.live_sessions import LiveSessionService, WorkflowFailure


class FixtureAnalyzer:
    def __init__(
        self,
        *,
        materials_conflict: bool = True,
        high_impact_count: int = 4,
        include_missing: bool = True,
    ) -> None:
        self.materials_conflict = materials_conflict
        self.high_impact_count = high_impact_count
        self.include_missing = include_missing

    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        terms = self._terms()
        return build_analysis_response(
            request,
            AgreementAnalysisModelOutput(terms=terms),
            prompt_version="choice-test-v1",
            model="mock",
        )

    def _terms(self) -> list[ModelAgreementTerm]:
        definitions = [
            (
                "scope.work",
                AgreementTopic.SCOPE,
                AgreementFacet.WORK,
                "Repair one fan and two switches.",
            ),
            (
                "price.amount",
                AgreementTopic.PRICE,
                AgreementFacet.AMOUNT,
                "The labour price is ₹1,200.",
            ),
            (
                "materials.inclusion",
                AgreementTopic.MATERIALS,
                AgreementFacet.INCLUSION,
                "Replacement parts are charged separately.",
            ),
            (
                "timing.start",
                AgreementTopic.TIMING,
                AgreementFacet.START,
                "The work starts today.",
            ),
            (
                "completion.deadline",
                AgreementTopic.COMPLETION,
                AgreementFacet.DEADLINE,
                "The work will finish tomorrow.",
            ),
            (
                "payment.timing",
                AgreementTopic.PAYMENT,
                AgreementFacet.TIMING,
                "Payment is due after the work is complete.",
            ),
        ]
        terms: list[ModelAgreementTerm] = []
        for item_key, topic, facet, summary in definitions[: self.high_impact_count]:
            if item_key == "materials.inclusion" and self.materials_conflict:
                positions = [
                    ModelParticipantPosition(
                        participant_id=PartyRole.HIRER.value,
                        summary="Replacement parts are included in ₹1,200.",
                        evidence_message_ids=["message-1"],
                    ),
                    ModelParticipantPosition(
                        participant_id=PartyRole.WORKER.value,
                        summary="Labour only; replacement parts cost extra.",
                        evidence_message_ids=["message-2"],
                    ),
                ]
                state = MeaningState.CONFLICTING
                evidence_ids = ["message-1", "message-2"]
                clarification = "What will the ₹1,200 cover?"
            else:
                positions = [
                    ModelParticipantPosition(
                        participant_id=role.value,
                        summary=summary,
                        evidence_message_ids=[f"message-{role_index}"],
                    )
                    for role_index, role in enumerate(PartyRole, start=1)
                ]
                state = MeaningState.ALIGNED
                evidence_ids = ["message-1", "message-2"]
                clarification = None
            terms.append(
                ModelAgreementTerm(
                    item_key=item_key,
                    topic=topic,
                    facet=facet,
                    neutral_summary=summary,
                    state=state,
                    participant_positions=positions,
                    evidence_message_ids=evidence_ids,
                    clarification_question=clarification,
                )
            )
        if self.include_missing:
            discussed = {item.item_key for item in terms}
            for item_key, topic, facet, summary in [
                (
                    "completion.deadline",
                    AgreementTopic.COMPLETION,
                    AgreementFacet.DEADLINE,
                    "No completion date or time was discussed.",
                ),
                (
                    "payment.timing",
                    AgreementTopic.PAYMENT,
                    AgreementFacet.TIMING,
                    "No payment timing was discussed.",
                ),
                (
                    "responsibilities.assignment",
                    AgreementTopic.RESPONSIBILITIES,
                    AgreementFacet.ASSIGNMENT,
                    "No additional responsibilities were discussed.",
                ),
                (
                    "warranty.coverage",
                    AgreementTopic.WARRANTY,
                    AgreementFacet.COVERAGE,
                    "No warranty was discussed.",
                ),
                (
                    "cancellation.policy",
                    AgreementTopic.CANCELLATION,
                    AgreementFacet.POLICY,
                    "No cancellation policy was discussed.",
                ),
                (
                    "additional_work.policy",
                    AgreementTopic.ADDITIONAL_WORK,
                    AgreementFacet.POLICY,
                    "No policy for additional work was discussed.",
                ),
            ]:
                if item_key in discussed:
                    continue
                terms.append(
                    ModelAgreementTerm(
                        item_key=item_key,
                        topic=topic,
                        facet=facet,
                        neutral_summary=summary,
                        state=MeaningState.NOT_DISCUSSED,
                    )
                )
        return terms


class MaterialsOnlyFixtureAnalyzer(FixtureAnalyzer):
    def __init__(self) -> None:
        super().__init__(
            materials_conflict=True,
            high_impact_count=3,
            include_missing=False,
        )

    def _terms(self) -> list[ModelAgreementTerm]:
        return [
            term for term in super()._terms() if term.item_key == "materials.inclusion"
        ]


def create_submission() -> LiveSessionCreate:
    timestamp = datetime(2026, 7, 17, 9, tzinfo=UTC)
    participants = [
        AnalysisParticipant(id=role.value, role=role, language="en")
        for role in PartyRole
    ]
    statements = [
        (
            PartyRole.HIRER,
            "Repair one fan and two switches for ₹1,200; I thought parts included.",
        ),
        (
            PartyRole.WORKER,
            "I will repair them for ₹1,200 labour; replacement parts cost extra.",
        ),
        (PartyRole.HIRER, "The work should start today."),
        (PartyRole.WORKER, "I can start the work today."),
    ]
    messages = [
        AnalysisMessage(
            message_id=f"message-{index}",
            speaker_id=role.value,
            original_text=text,
            original_language="en",
            order=index,
            timestamp=timestamp,
        )
        for index, (role, text) in enumerate(statements, start=1)
    ]
    return LiveSessionCreate(participants=participants, messages=messages)


def create_crowded_submission(message_count: int) -> LiveSessionCreate:
    base = create_submission()
    timestamp = datetime(2026, 7, 17, 9, tzinfo=UTC)
    return LiveSessionCreate(
        participants=base.participants,
        messages=[
            AnalysisMessage(
                message_id=f"message-{index}",
                speaker_id=(
                    PartyRole.HIRER.value if index % 2 else PartyRole.WORKER.value
                ),
                original_text=f"Conversation statement {index}.",
                original_language="en",
                order=index,
                timestamp=timestamp,
            )
            for index in range(1, message_count + 1)
        ],
    )


def service(
    *,
    conflict: bool = True,
    high_impact_count: int = 4,
    include_missing: bool = True,
    attempt_limit: int = 3,
) -> LiveSessionService:
    return LiveSessionService(
        analyzer=FixtureAnalyzer(
            materials_conflict=conflict,
            high_impact_count=high_impact_count,
            include_missing=include_missing,
        ),
        repository=InMemoryLiveSessionRepository(),
        clarification_attempt_limit=attempt_limit,
    )


async def analyzed(workflow: LiveSessionService):
    created = workflow.create(create_submission())
    return await workflow.analyze(created.id, AnalyzeLiveSessionSubmission())


def active_question(session):
    question_id = session.guidance.active_question_id
    assert question_id is not None
    return next(item for item in session.questions if item.id == question_id)


def option(question, kind: UnderstandingOptionKind, label: str | None = None):
    return next(
        item
        for item in question.options
        if item.kind == kind and (label is None or label in item.label)
    )


def acknowledgments(session) -> list[str]:
    version = session.current_version
    assert version is not None
    return [
        item.analysis_item_key
        for item in version.terms
        if item.analysis_item_key in version.unresolved_item_keys
        and item.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
    ]


def review_optional(workflow: LiveSessionService, session, suffix: str = ""):
    if session.guidance.optional_missing_count:
        session = workflow.mark_optional_details_reviewed(
            session.id,
            OptionalDetailsReviewedSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                request_id=f"optional{suffix}",
            ),
        )
    return session


def start_check(workflow: LiveSessionService, session, suffix: str = ""):
    session = review_optional(workflow, session, suffix)
    return workflow.start_understanding_check(
        session.id,
        StartUnderstandingCheckSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            acknowledged_unresolved_item_keys=acknowledgments(session),
            request_id=f"start-check{suffix}",
        ),
    )


def select(
    workflow: LiveSessionService,
    session,
    question,
    role: PartyRole,
    selected_option,
    request_id: str,
    *,
    other_text: str | None = None,
):
    return workflow.submit_selection(
        session.id,
        question.id,
        UnderstandingSelectionSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=role,
            option_id=selected_option.id,
            other_text=other_text,
            request_id=request_id,
        ),
    )


def resolve_initial_materials(workflow: LiveSessionService, session):
    question = active_question(session)
    assert question.kind == UnderstandingQuestionKind.CLARIFICATION
    separate = option(
        question,
        UnderstandingOptionKind.RECORDED_POSITION,
        "cost extra",
    )
    for role in PartyRole:
        session = select(
            workflow,
            session,
            question,
            role,
            separate,
            f"materials-{role.value}",
        )
    return session


def complete_current_checks(workflow: LiveSessionService, session):
    while session.stage == LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS:
        question = active_question(session)
        recorded = option(question, UnderstandingOptionKind.RECORDED_MEANING)
        for role in PartyRole:
            session = select(
                workflow,
                session,
                question,
                role,
                recorded,
                f"check-{question.id}-{role.value}",
            )
    return session


def confirm_both(workflow: LiveSessionService, session):
    for role in PartyRole:
        review = session.understanding_reviews[role]
        session = workflow.submit_confirmation(
            session.id,
            ConfirmationSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=role,
                understanding_review_id=review.id,
                decision=ConfirmationDecision.CONFIRM,
                unresolved_item_acknowledgments=acknowledgments(session),
                request_id=f"confirm-{role.value}",
            ),
        )
    return session


@pytest.mark.anyio
async def test_clarification_uses_stable_recorded_choices_and_no_free_text() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert question.kind == UnderstandingQuestionKind.CLARIFICATION
    assert question.prompt == "What will the ₹1,200 cover?"
    assert [item.kind for item in question.options] == [
        UnderstandingOptionKind.RECORDED_POSITION,
        UnderstandingOptionKind.RECORDED_POSITION,
        UnderstandingOptionKind.OTHER,
        UnderstandingOptionKind.UNSURE,
    ]
    assert [item.label for item in question.options[:2]] == [
        "Replacement parts are included in ₹1,200.",
        "Labour only; replacement parts cost extra.",
    ]
    repeated = build_question_ids = [item.id for item in question.options]
    other_session = await analyzed(service())
    assert [item.id for item in active_question(other_session).options] == repeated
    assert build_question_ids

    resolved = resolve_initial_materials(workflow, session)
    completed = next(item for item in resolved.questions if item.id == question.id)
    assert completed.status == UnderstandingQuestionStatus.COMPLETED
    assert completed.outcome is not None
    assert completed.outcome.state == UnderstandingOutcomeState.MEANING_CHANGED
    assert len(resolved.agreement_versions) == 2
    materials = next(
        item
        for item in resolved.current_version.terms
        if item.analysis_item_key == "materials.inclusion"
    )
    price = next(
        item
        for item in resolved.current_version.terms
        if item.analysis_item_key == "price.amount"
    )
    assert materials.state == MeaningState.ALIGNED
    assert materials.summary == "Labour only; replacement parts cost extra."
    assert price.summary == "The labour price is ₹1,200."


@pytest.mark.anyio
async def test_first_selection_is_hidden_until_second_participant_answers() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    selected = option(question, UnderstandingOptionKind.OTHER)
    secret = "Private first-person meaning 7f4a."
    first = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        selected,
        "hidden-first",
        other_text=secret,
    )
    public = next(item for item in first.questions if item.id == question.id)
    assert public.status == UnderstandingQuestionStatus.PARTIALLY_ANSWERED
    assert public.answered_participant_ids == [PartyRole.HIRER]
    assert public.responses_revealed is False
    assert public.outcome is None
    dumped = first.model_dump(mode="json")
    assert "selections" not in dumped
    assert "other_text" not in dumped["questions"][0]
    assert secret not in first.model_dump_json()
    assert secret not in " ".join(item.original_text for item in first.messages)
    assert first.active_participant_id == PartyRole.WORKER

    second = select(
        workflow,
        first,
        question,
        PartyRole.WORKER,
        selected,
        "hidden-second",
        other_text=secret,
    )
    revealed = next(item for item in second.questions if item.id == question.id)
    assert revealed.responses_revealed is True
    assert [item.participant_id for item in revealed.outcome.positions] == list(
        PartyRole
    )


@pytest.mark.anyio
async def test_other_requires_bounded_text_and_non_other_rejects_text() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    other = option(question, UnderstandingOptionKind.OTHER)
    with pytest.raises(WorkflowFailure) as missing:
        select(
            workflow,
            session,
            question,
            PartyRole.HIRER,
            other,
            "other-missing",
        )
    assert missing.value.code == WorkflowErrorCode.INVALID_OPTION

    for index, text in enumerate(["!!", "--"], start=1):
        with pytest.raises(WorkflowFailure) as punctuation_only:
            select(
                workflow,
                session,
                question,
                PartyRole.HIRER,
                other,
                f"other-punctuation-{index}",
                other_text=text,
            )
        assert punctuation_only.value.code == WorkflowErrorCode.INVALID_OPTION
    unchanged = workflow.get(session.id)
    assert unchanged.questions[0].answered_participant_ids == []
    assert unchanged.active_participant_id == PartyRole.HIRER

    recorded = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    with pytest.raises(WorkflowFailure) as unexpected:
        select(
            workflow,
            session,
            question,
            PartyRole.HIRER,
            recorded,
            "other-unexpected",
            other_text="This must not be accepted.",
        )
    assert unexpected.value.code == WorkflowErrorCode.INVALID_OPTION


@pytest.mark.anyio
async def test_unsure_never_aligns_and_returns_only_item_to_clarification() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    unsure = option(question, UnderstandingOptionKind.UNSURE)
    recorded = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        unsure,
        "unsure-hirer",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.WORKER,
        recorded,
        "unsure-worker",
    )
    original = next(item for item in session.questions if item.id == question.id)
    assert original.outcome.state == UnderstandingOutcomeState.UNSURE
    assert original.status == UnderstandingQuestionStatus.UNSURE
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    retry = active_question(session)
    assert retry.id != question.id
    assert retry.agreement_item_id == question.agreement_item_id
    term = next(
        item
        for item in session.current_version.terms
        if item.analysis_item_key == "materials.inclusion"
    )
    assert term.state == MeaningState.CONFLICTING


@pytest.mark.anyio
async def test_unsure_follow_up_does_not_reactivate_terminal_check() -> None:
    workflow = service(conflict=False, high_impact_count=2, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    source = active_question(session)
    assert source.agreement_item_id == "scope.work"
    unsure = option(source, UnderstandingOptionKind.UNSURE)
    recorded = option(source, UnderstandingOptionKind.RECORDED_MEANING)
    session = select(
        workflow,
        session,
        source,
        PartyRole.HIRER,
        unsure,
        "follow-up-unsure-hirer",
    )
    session = select(
        workflow,
        session,
        source,
        PartyRole.WORKER,
        recorded,
        "follow-up-unsure-worker",
    )
    follow_up = active_question(session)
    assert follow_up.kind == UnderstandingQuestionKind.CLARIFICATION
    assert follow_up.agreement_item_id == source.agreement_item_id
    clarification_meaning = option(
        follow_up,
        UnderstandingOptionKind.RECORDED_MEANING,
    )
    for role in PartyRole:
        session = select(
            workflow,
            session,
            follow_up,
            role,
            clarification_meaning,
            f"follow-up-resolve-{role.value}",
        )

    next_check = active_question(session)
    assert session.stage == LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS
    assert next_check.id != source.id
    assert next_check.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    assert next_check.agreement_item_id == "price.amount"
    assert (
        len(
            [
                item
                for item in session.questions
                if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
                and item.agreement_item_id == "scope.work"
            ]
        )
        == 1
    )

    session = complete_current_checks(workflow, session)
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    assert len(session.understanding_reviews) == 2
    assert all(
        review.status == ParticipantReviewStatus.COMPLETED
        for review in session.understanding_reviews.values()
    )
    assert confirm_both(workflow, session).stage == LiveSessionStage.CONFIRMED


@pytest.mark.anyio
async def test_question_option_participant_session_and_version_are_bound() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    with pytest.raises(WorkflowFailure) as invalid_option:
        workflow.submit_selection(
            session.id,
            question.id,
            UnderstandingSelectionSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=PartyRole.HIRER,
                option_id="option-not-here",
                request_id="invalid-option",
            ),
        )
    assert invalid_option.value.code == WorkflowErrorCode.INVALID_OPTION

    with pytest.raises(WorkflowFailure) as wrong_actor:
        select(
            workflow,
            session,
            question,
            PartyRole.WORKER,
            question.options[0],
            "wrong-actor",
        )
    assert wrong_actor.value.code == WorkflowErrorCode.PARTICIPANT_MISMATCH

    other = await analyzed(workflow)
    with pytest.raises(WorkflowFailure) as wrong_session:
        workflow.submit_selection(
            other.id,
            question.id,
            UnderstandingSelectionSubmission(
                expected_agreement_version_id=other.current_agreement_version_id,
                participant_id=PartyRole.HIRER,
                option_id=question.options[0].id,
                request_id="cross-session",
            ),
        )
    assert wrong_session.value.code == WorkflowErrorCode.QUESTION_NOT_FOUND

    resolved = resolve_initial_materials(workflow, session)
    with pytest.raises(WorkflowFailure) as stale:
        workflow.submit_selection(
            session.id,
            question.id,
            UnderstandingSelectionSubmission(
                expected_agreement_version_id=question.agreement_version_id,
                participant_id=PartyRole.HIRER,
                option_id=question.options[0].id,
                request_id="stale-question",
            ),
        )
    assert stale.value.code == WorkflowErrorCode.STALE_AGREEMENT_VERSION
    assert resolved.current_agreement_version_id != question.agreement_version_id


@pytest.mark.anyio
async def test_completed_clarification_is_not_repeated_in_understanding_check() -> None:
    workflow = service()
    session = resolve_initial_materials(workflow, await analyzed(workflow))
    assert session.guidance.headline == "One final understanding check"
    session = start_check(workflow, session)
    checks = [
        item
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(checks) == 1
    assert checks[0].agreement_item_id == "scope.work"
    assert "materials.inclusion" not in {item.agreement_item_id for item in checks}
    assert checks[0].question_number == checks[0].question_count == 1
    assert session.guidance.headline == "One final understanding check"
    assert session.guidance.explanation.startswith(
        "One final understanding check remains."
    )


@pytest.mark.anyio
async def test_completed_clarification_can_skip_directly_to_confirmation() -> None:
    workflow = LiveSessionService(
        analyzer=MaterialsOnlyFixtureAnalyzer(),
        repository=InMemoryLiveSessionRepository(),
    )
    session = resolve_initial_materials(workflow, await analyzed(workflow))

    session = start_check(workflow, session)

    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    assert all(
        question.kind != UnderstandingQuestionKind.UNDERSTANDING_CHECK
        for question in session.questions
    )
    assert all(
        review.status == ParticipantReviewStatus.SKIPPED
        for review in session.understanding_reviews.values()
    )
    assert session.guidance.headline == (
        "The important difference is already clarified"
    )
    assert "no additional understanding question was needed" in (
        session.guidance.explanation
    )


@pytest.mark.anyio
async def test_matching_recorded_meaning_completes_checks_without_new_version() -> None:
    workflow = service()
    session = start_check(
        workflow, resolve_initial_materials(workflow, await analyzed(workflow))
    )
    version_id = session.current_agreement_version_id
    first = active_question(session)
    recorded = option(first, UnderstandingOptionKind.RECORDED_MEANING)
    for role in PartyRole:
        session = select(
            workflow,
            session,
            first,
            role,
            recorded,
            f"recorded-{role.value}",
        )
    completed = next(item for item in session.questions if item.id == first.id)
    assert completed.outcome.state == UnderstandingOutcomeState.ALIGNED
    assert completed.outcome.resulting_agreement_version_id is None
    assert session.current_agreement_version_id == version_id
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    assert all(
        review.status.value == "completed"
        for review in session.understanding_reviews.values()
    )


@pytest.mark.anyio
async def test_matching_other_normalizes_text_and_creates_meaningful_version() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    question = active_question(session)
    assert question.agreement_item_id == "scope.work"
    other = option(question, UnderstandingOptionKind.OTHER)
    old = session.current_version
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        other,
        "other-alt-hirer",
        other_text="Repair the fan only!",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.WORKER,
        other,
        "other-alt-worker",
        other_text=" repair the FAN only ",
    )
    current = session.current_version
    assert old is not None and current is not None
    assert current.parent_version_id == old.id
    assert current.has_meaningful_change is True
    assert current.meaningful_version_number == old.meaningful_version_number + 1
    assert session.stage == LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
    outcome = next(item for item in session.questions if item.id == question.id).outcome
    assert outcome.state == UnderstandingOutcomeState.MEANING_CHANGED
    assert outcome.resulting_agreement_version_id == current.id
    scope = next(
        item for item in current.terms if item.analysis_item_key == "scope.work"
    )
    assert scope.summary == "Repair the fan only!"
    assert {item.source for item in scope.evidence} >= {
        "transcript",
        "understanding_check",
    }
    assert current.changes[0].new_evidence_reference_ids
    assert all(
        reference.startswith("selection-")
        for reference in current.changes[0].new_evidence_reference_ids
    )

    # A later deterministic analysis can cite a synthetic understanding message.
    # Preserve that source instead of presenting it as transcript evidence.
    synthetic = next(
        item
        for item in scope.evidence
        if item.message_id is not None and item.message_id.startswith("understanding-")
    )
    analyzer_term = scope.model_copy(
        update={
            "evidence": [
                item.model_copy(update={"source": "transcript"})
                if item.reference_id == synthetic.reference_id
                else item
                for item in scope.evidence
            ]
        },
        deep=True,
    )
    remapped = workflow._with_evidence_provenance(analyzer_term)
    assert (
        next(
            item
            for item in remapped.evidence
            if item.reference_id == synthetic.reference_id
        ).source
        == "understanding_check"
    )


@pytest.mark.anyio
async def test_other_text_equal_to_current_meaning_does_not_create_version() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    question = active_question(session)
    other = option(question, UnderstandingOptionKind.OTHER)
    old_version_id = session.current_agreement_version_id
    for role, text in [
        (PartyRole.HIRER, "REPAIR ONE FAN AND TWO SWITCHES!"),
        (PartyRole.WORKER, "repair one fan and two switches"),
    ]:
        session = select(
            workflow,
            session,
            question,
            role,
            other,
            f"other-current-{role.value}",
            other_text=text,
        )
    outcome = next(item for item in session.questions if item.id == question.id).outcome
    assert outcome.state == UnderstandingOutcomeState.ALIGNED
    assert session.current_agreement_version_id == old_version_id


@pytest.mark.anyio
async def test_changed_check_is_current_completed_evidence_in_receipt() -> None:
    workflow = service(conflict=False, high_impact_count=1, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    question = active_question(session)
    other = option(question, UnderstandingOptionKind.OTHER)
    for role, text in [
        (PartyRole.HIRER, "Repair only the fan."),
        (PartyRole.WORKER, "repair only the fan"),
    ]:
        session = select(
            workflow,
            session,
            question,
            role,
            other,
            f"current-changed-check-{role.value}",
            other_text=text,
        )
    assert session.current_agreement_version_id != question.agreement_version_id
    assert session.stage == LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK

    session = start_check(workflow, session, "-current-change")
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    for review in session.understanding_reviews.values():
        assert review.status == ParticipantReviewStatus.COMPLETED
        assert review.completed_question_ids == [question.id]

    session = confirm_both(workflow, session)
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="current-changed-check-receipt",
        ),
    )
    assert [item.result for item in receipt.understanding_status] == [
        UnderstandingReviewResult.COMPLETED,
        UnderstandingReviewResult.COMPLETED,
    ]
    assert all(
        item.question_ids == [question.id] for item in receipt.understanding_status
    )


@pytest.mark.anyio
async def test_different_check_choices_reopen_only_target_item() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    question = active_question(session)
    recorded = option(question, UnderstandingOptionKind.RECORDED_MEANING)
    other = option(question, UnderstandingOptionKind.OTHER)
    old = session.current_version
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        recorded,
        "different-hirer",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.WORKER,
        other,
        "different-worker",
        other_text="Replace the fan instead.",
    )
    current = session.current_version
    assert old is not None and current is not None
    assert current.parent_version_id == old.id
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    mismatch = next(item for item in session.questions if item.id == question.id)
    assert mismatch.outcome.state == UnderstandingOutcomeState.DIFFERENT
    clarification = active_question(session)
    assert clarification.kind == UnderstandingQuestionKind.CLARIFICATION
    assert clarification.agreement_item_id == "scope.work"
    assert {
        item.analysis_item_key
        for item in current.terms
        if item.state != MeaningState.ALIGNED
    } == {"scope.work"}


@pytest.mark.anyio
async def test_different_other_text_is_not_inferred_compatible() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    question = active_question(session)
    other = option(question, UnderstandingOptionKind.OTHER)
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        other,
        "other-different-hirer",
        other_text="Repair the fan only.",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.WORKER,
        other,
        "other-different-worker",
        other_text="Replace the fan only.",
    )
    outcome = next(item for item in session.questions if item.id == question.id).outcome
    assert outcome.state == UnderstandingOutcomeState.DIFFERENT
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION


@pytest.mark.anyio
async def test_simple_skip_and_maximum_three_question_policy() -> None:
    simple_workflow = service(
        conflict=False, high_impact_count=1, include_missing=False
    )
    simple = start_check(simple_workflow, await analyzed(simple_workflow))
    simple_checks = [
        item
        for item in simple.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(simple_checks) == 1
    assert simple_checks[0].question_number == simple_checks[0].question_count == 1

    medium_workflow = service(
        conflict=False,
        high_impact_count=4,
        include_missing=False,
    )
    medium = start_check(medium_workflow, await analyzed(medium_workflow))
    medium_checks = [
        item
        for item in medium.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(medium_checks) == 2
    assert [item.question_number for item in medium_checks] == [1, 2]

    broad_workflow = service(conflict=False, high_impact_count=6, include_missing=False)
    broad = start_check(broad_workflow, await analyzed(broad_workflow))
    broad_checks = [
        item
        for item in broad.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(broad_checks) == 3
    assert [item.question_number for item in broad_checks] == [1, 2, 3]
    assert active_question(broad).question_number == 1

    skip_workflow = service(conflict=False, high_impact_count=0, include_missing=True)
    skip = start_check(skip_workflow, await analyzed(skip_workflow))
    assert skip.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    assert skip.questions == []
    assert all(
        item.status.value == "skipped" for item in skip.understanding_reviews.values()
    )
    assert skip.guidance.headline == "No additional understanding question was needed"
    assert "sufficient independent evidence" in skip.guidance.explanation
    skip = confirm_both(skip_workflow, skip)
    receipt = skip_workflow.issue_receipt(
        skip.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=skip.current_agreement_version_id,
            request_id="skip-receipt",
        ),
    )
    assert [item.result for item in receipt.understanding_status] == [
        UnderstandingReviewResult.SKIPPED,
        UnderstandingReviewResult.SKIPPED,
    ]


@pytest.mark.anyio
async def test_optional_missing_terms_never_become_mandatory_questions() -> None:
    workflow = service(conflict=False, high_impact_count=2, include_missing=True)
    session = start_check(workflow, await analyzed(workflow))
    keys = {
        item.agreement_item_id
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    }
    assert keys == {"scope.work", "price.amount"}
    assert "completion.deadline" not in keys
    assert "payment.timing" not in keys


@pytest.mark.anyio
async def test_selection_retry_is_idempotent_and_key_is_payload_bound() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    recorded = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    submission = UnderstandingSelectionSubmission(
        expected_agreement_version_id=session.current_agreement_version_id,
        participant_id=PartyRole.HIRER,
        option_id=recorded.id,
        request_id="selection-once",
    )
    first = workflow.submit_selection(session.id, question.id, submission)
    duplicate = workflow.submit_selection(session.id, question.id, submission)
    assert first == duplicate
    assert first.active_participant_id == PartyRole.WORKER
    assert first.questions[0].answered_participant_ids == [PartyRole.HIRER]

    other = option(question, UnderstandingOptionKind.OTHER)
    with pytest.raises(WorkflowFailure) as conflict:
        workflow.submit_selection(
            session.id,
            question.id,
            submission.model_copy(
                update={
                    "option_id": other.id,
                    "other_text": "A different payload.",
                }
            ),
        )
    assert conflict.value.code == WorkflowErrorCode.IDEMPOTENCY_CONFLICT


@pytest.mark.anyio
async def test_failed_second_selection_is_atomic_and_retry_is_not_cached() -> None:
    workflow = service()
    crowded = create_crowded_submission(39)
    created = workflow.create(crowded)
    session = await workflow.analyze(
        created.id,
        AnalyzeLiveSessionSubmission(),
    )
    question = active_question(session)
    included = option(
        question,
        UnderstandingOptionKind.RECORDED_POSITION,
        "included",
    )
    separate = option(
        question,
        UnderstandingOptionKind.RECORDED_POSITION,
        "cost extra",
    )
    first = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        included,
        "atomic-first",
    )
    second_submission = UnderstandingSelectionSubmission(
        expected_agreement_version_id=first.current_agreement_version_id,
        participant_id=PartyRole.WORKER,
        option_id=separate.id,
        request_id="atomic-second",
    )
    for _ in range(2):
        with pytest.raises(WorkflowFailure) as capacity:
            workflow.submit_selection(
                first.id,
                question.id,
                second_submission,
            )
        assert capacity.value.code == WorkflowErrorCode.INVALID_STATE

    unchanged = workflow.get(first.id)
    public = next(item for item in unchanged.questions if item.id == question.id)
    assert public.status == UnderstandingQuestionStatus.PARTIALLY_ANSWERED
    assert public.answered_participant_ids == [PartyRole.HIRER]
    assert public.responses_revealed is False
    assert public.outcome is None
    assert unchanged.active_participant_id == PartyRole.WORKER
    assert len(unchanged.messages) == 39


@pytest.mark.anyio
async def test_failed_final_leave_is_atomic_and_retry_is_not_cached() -> None:
    workflow = service(conflict=False, high_impact_count=1, include_missing=False)
    created = workflow.create(create_crowded_submission(40))
    session = await workflow.analyze(created.id, AnalyzeLiveSessionSubmission())
    session = complete_current_checks(workflow, start_check(workflow, session))
    review = session.understanding_reviews[PartyRole.HIRER]
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.HIRER,
            understanding_review_id=review.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="scope.work",
            request_id="atomic-change-request",
        ),
    )
    question = active_question(session)
    recorded = option(question, UnderstandingOptionKind.RECORDED_MEANING)
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        recorded,
        "atomic-leave-selection",
    )
    session = workflow.leave_question_unresolved(
        session.id,
        question.id,
        LeaveQuestionUnresolvedSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.WORKER,
            request_id="atomic-leave-worker",
        ),
    )
    final_leave = LeaveQuestionUnresolvedSubmission(
        expected_agreement_version_id=session.current_agreement_version_id,
        participant_id=PartyRole.HIRER,
        request_id="atomic-leave-hirer",
    )
    for _ in range(2):
        with pytest.raises(WorkflowFailure) as capacity:
            workflow.leave_question_unresolved(
                session.id,
                question.id,
                final_leave,
            )
        assert capacity.value.code == WorkflowErrorCode.INVALID_STATE

    unchanged = workflow.get(session.id)
    public = next(item for item in unchanged.questions if item.id == question.id)
    assert public.status == UnderstandingQuestionStatus.PARTIALLY_ANSWERED
    assert public.answered_participant_ids == [PartyRole.HIRER]
    assert public.responses_revealed is False
    assert public.outcome is None
    assert unchanged.active_participant_id == PartyRole.HIRER
    assert len(unchanged.messages) == 40
    assert len(unchanged.agreement_versions) == 1


@pytest.mark.anyio
async def test_both_people_must_explicitly_leave_clarification_unresolved() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    first = workflow.leave_question_unresolved(
        session.id,
        question.id,
        LeaveQuestionUnresolvedSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.HIRER,
            request_id="leave-hirer",
        ),
    )
    public = next(item for item in first.questions if item.id == question.id)
    assert public.status == UnderstandingQuestionStatus.PENDING
    assert public.outcome is None
    assert first.active_participant_id == PartyRole.WORKER

    second = workflow.leave_question_unresolved(
        session.id,
        question.id,
        LeaveQuestionUnresolvedSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.WORKER,
            request_id="leave-worker",
        ),
    )
    closed = next(item for item in second.questions if item.id == question.id)
    assert closed.status == UnderstandingQuestionStatus.LEFT_UNRESOLVED
    assert closed.outcome.state == UnderstandingOutcomeState.LEFT_UNRESOLVED
    assert second.stage == LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
    assert "materials.inclusion" in second.current_version.unresolved_item_keys


@pytest.mark.anyio
async def test_final_attempt_preserves_selections_and_leave_action() -> None:
    workflow = service(attempt_limit=1)
    session = await analyzed(workflow)
    question = active_question(session)
    included = option(
        question,
        UnderstandingOptionKind.RECORDED_POSITION,
        "included",
    )
    separate = option(
        question,
        UnderstandingOptionKind.RECORDED_POSITION,
        "cost extra",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.HIRER,
        included,
        "final-attempt-hirer",
    )
    session = select(
        workflow,
        session,
        question,
        PartyRole.WORKER,
        separate,
        "final-attempt-worker",
    )
    source = next(item for item in session.questions if item.id == question.id)
    assert source.outcome.state == UnderstandingOutcomeState.DIFFERENT
    assert source.outcome.resulting_agreement_version_id == (
        session.current_agreement_version_id
    )
    current_term = next(
        item
        for item in session.current_version.terms
        if item.analysis_item_key == "materials.inclusion"
    )
    assert sum(item.source == "clarification" for item in current_term.evidence) == 2
    original_term = next(
        item
        for item in session.agreement_versions[0].terms
        if item.analysis_item_key == "materials.inclusion"
    )
    assert {item.reference_id for item in current_term.evidence} > {
        item.reference_id for item in original_term.evidence
    }

    marker = active_question(session)
    assert marker.id != question.id
    assert marker.status == UnderstandingQuestionStatus.NEEDS_CLARIFICATION
    assert session.guidance.primary_action.value == "leave_unresolved"
    for role in PartyRole:
        session = workflow.leave_question_unresolved(
            session.id,
            marker.id,
            LeaveQuestionUnresolvedSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=role,
                request_id=f"final-leave-{role.value}",
            ),
        )
    assert session.stage == LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK


@pytest.mark.anyio
async def test_session_wide_budget_survives_meaning_change_restart() -> None:
    workflow = service(conflict=False, high_impact_count=6, include_missing=False)
    session = start_check(workflow, await analyzed(workflow))
    original_checks = [
        item
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(original_checks) == 3
    first = active_question(session)
    other = option(first, UnderstandingOptionKind.OTHER)
    for role, text in [
        (PartyRole.HIRER, "Repair only the fan."),
        (PartyRole.WORKER, "repair only the fan"),
    ]:
        session = select(
            workflow,
            session,
            first,
            role,
            other,
            f"budget-change-{role.value}",
            other_text=text,
        )
    current_checks = [
        item
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert [item.id for item in current_checks] == [first.id]
    assert session.stage == LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK

    restarted = start_check(workflow, session, "-restart")
    all_checks = [
        item
        for item in restarted.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
    ]
    assert len(all_checks) == 3
    assert [item.question_number for item in all_checks] == [1, 2, 3]
    assert active_question(restarted).question_number == 2
    assert "scope.work" not in {item.agreement_item_id for item in all_checks[1:]}


@pytest.mark.anyio
async def test_confirmation_and_receipt_bind_current_understanding_reviews() -> None:
    workflow = service(include_missing=False)
    session = resolve_initial_materials(workflow, await analyzed(workflow))
    session = complete_current_checks(workflow, start_check(workflow, session))
    version = session.current_version
    assert version is not None
    hirer_review = session.understanding_reviews[PartyRole.HIRER]
    worker_review = session.understanding_reviews[PartyRole.WORKER]
    with pytest.raises(WorkflowFailure) as wrong_review:
        workflow.submit_confirmation(
            session.id,
            ConfirmationSubmission(
                expected_agreement_version_id=version.id,
                participant_id=PartyRole.HIRER,
                understanding_review_id=worker_review.id,
                decision=ConfirmationDecision.CONFIRM,
                request_id="cross-participant-review",
            ),
        )
    assert wrong_review.value.code == WorkflowErrorCode.UNDERSTANDING_INCOMPLETE

    hirer_confirmation = ConfirmationSubmission(
        expected_agreement_version_id=version.id,
        participant_id=PartyRole.HIRER,
        understanding_review_id=hirer_review.id,
        decision=ConfirmationDecision.CONFIRM,
        request_id="confirm-hirer-once",
    )
    first = workflow.submit_confirmation(session.id, hirer_confirmation)
    replay = workflow.submit_confirmation(session.id, hirer_confirmation)
    assert replay == first
    assert len(replay.confirmations) == 1
    with pytest.raises(WorkflowFailure) as idempotency_conflict:
        workflow.submit_confirmation(
            session.id,
            hirer_confirmation.model_copy(
                update={"unresolved_item_acknowledgments": ["scope.work"]}
            ),
        )
    assert idempotency_conflict.value.code == WorkflowErrorCode.IDEMPOTENCY_CONFLICT

    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            understanding_review_id=worker_review.id,
            decision=ConfirmationDecision.CONFIRM,
            request_id="confirm-worker-once",
        ),
    )
    assert session.stage == LiveSessionStage.CONFIRMED
    assert len(session.confirmations) == 2
    assert session.confirmations[0].understanding_review_id == hirer_review.id
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=version.id,
            request_id="issue-receipt",
        ),
    )
    assert receipt.schema_version == "clarity-receipt-v2"
    assert receipt.application_version == "0.4.0"
    assert len(receipt.understanding_status) == 2
    assert {item.result for item in receipt.understanding_status} == {
        UnderstandingReviewResult.COMPLETED
    }
    assert receipt.status == ReceiptStatus.FULLY_ALIGNED
    canonical = json.dumps(
        receipt.model_dump(mode="json", exclude={"integrity_hash"}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert receipt.integrity_hash == hashlib.sha256(canonical).hexdigest()
    assert "not presented as a legally enforceable contract" in receipt.disclaimer
    assert receipt == workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=version.id,
            request_id="issue-again",
        ),
    )


@pytest.mark.anyio
async def test_unresolved_item_survives_confirmation_and_receipt() -> None:
    workflow = service()
    session = await analyzed(workflow)
    question = active_question(session)
    for role in PartyRole:
        session = workflow.leave_question_unresolved(
            session.id,
            question.id,
            LeaveQuestionUnresolvedSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=role,
                request_id=f"receipt-leave-{role.value}",
            ),
        )
    session = complete_current_checks(workflow, start_check(workflow, session))
    session = confirm_both(workflow, session)
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="unresolved-receipt",
        ),
    )
    assert receipt.status == ReceiptStatus.CONTAINS_UNRESOLVED_ITEMS
    assert {item.analysis_item_key for item in receipt.unresolved_terms} == {
        "materials.inclusion"
    }
    assert receipt.clarification_history[0].status.value == "left_unresolved"


@pytest.mark.anyio
async def test_confirmation_change_request_reopens_exact_item_and_invalidates() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = complete_current_checks(
        workflow, start_check(workflow, await analyzed(workflow))
    )
    version = session.current_version
    assert version is not None
    hirer_review = session.understanding_reviews[PartyRole.HIRER]
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            understanding_review_id=hirer_review.id,
            decision=ConfirmationDecision.CONFIRM,
            request_id="confirm-before-change",
        ),
    )
    worker_review = session.understanding_reviews[PartyRole.WORKER]
    changed = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            understanding_review_id=worker_review.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="price.amount",
            request_id="request-price-change",
        ),
    )
    assert changed.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert active_question(changed).agreement_item_id == "price.amount"
    assert changed.confirmations[0].invalidated_at is not None
    assert changed.understanding_reviews == {}


@pytest.mark.anyio
async def test_changed_meaning_does_not_carry_stale_check_into_receipt() -> None:
    workflow = service(conflict=False, high_impact_count=2, include_missing=False)
    session = complete_current_checks(
        workflow,
        start_check(workflow, await analyzed(workflow)),
    )
    scope_check = next(
        item
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
        and item.agreement_item_id == "scope.work"
    )
    stale_price_check = next(
        item
        for item in session.questions
        if item.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
        and item.agreement_item_id == "price.amount"
    )
    review = session.understanding_reviews[PartyRole.HIRER]
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.HIRER,
            understanding_review_id=review.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="price.amount",
            request_id="change-price-after-check",
        ),
    )
    clarification = active_question(session)
    other = option(clarification, UnderstandingOptionKind.OTHER)
    for role in PartyRole:
        session = select(
            workflow,
            session,
            clarification,
            role,
            other,
            f"new-price-{role.value}",
            other_text="The labour price is ₹1,350.",
        )
    price = next(
        item
        for item in session.current_version.terms
        if item.analysis_item_key == "price.amount"
    )
    assert price.summary == "The labour price is ₹1,350."

    session = start_check(workflow, session, "-changed-price")
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    for current_review in session.understanding_reviews.values():
        assert scope_check.id in current_review.completed_question_ids
        assert stale_price_check.id not in current_review.completed_question_ids

    session = confirm_both(workflow, session)
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="changed-price-receipt",
        ),
    )
    for status in receipt.understanding_status:
        assert scope_check.id in status.question_ids
        assert stale_price_check.id not in status.question_ids


@pytest.mark.anyio
async def test_api_returns_controlled_missing_and_stale_errors() -> None:
    workflow = service(conflict=False, include_missing=False)
    with pytest.raises(HTTPException) as missing:
        api_get_live_session("not-here", workflow)
    assert missing.value.status_code == 404
    assert missing.value.detail["code"] == "session_not_found"

    session = await analyzed(workflow)
    with pytest.raises(HTTPException) as stale:
        api_start_understanding_check(
            session.id,
            StartUnderstandingCheckSubmission(
                expected_agreement_version_id="agreement-old",
                request_id="api-stale",
            ),
            workflow,
        )
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "stale_agreement_version"


@pytest.mark.anyio
async def test_new_statement_parents_version_and_invalidates_confirmation() -> None:
    workflow = service(conflict=False, include_missing=False)
    session = confirm_both(
        workflow,
        complete_current_checks(
            workflow, start_check(workflow, await analyzed(workflow))
        ),
    )
    old = session.current_version
    assert old is not None
    changed = await workflow.add_statements(
        session.id,
        AdditionalStatementsSubmission(
            expected_agreement_version_id=old.id,
            messages=[
                AnalysisMessage(
                    message_id="message-5",
                    speaker_id=PartyRole.HIRER.value,
                    original_text="I want to restate the final understanding.",
                    original_language="en",
                    order=5,
                    timestamp=datetime(2026, 7, 17, 10, tzinfo=UTC),
                )
            ],
            request_id="new-statement",
        ),
    )
    assert changed.current_version.parent_version_id == old.id
    assert all(item.invalidated_at for item in changed.confirmations)
    assert changed.receipt_ready is False
