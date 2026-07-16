from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.live_sessions import (
    analyze_live_session as api_analyze_live_session,
)
from app.api.live_sessions import create_live_session as api_create_live_session
from app.api.live_sessions import get_live_session as api_get_live_session
from app.api.live_sessions import start_review as api_start_review
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
from app.schemas.teachback import TeachbackComparisonState
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AnalyzeLiveSessionSubmission,
    ClarificationAnswerSubmission,
    ConfirmationDecision,
    ConfirmationSubmission,
    IssueReceiptSubmission,
    LeaveClarificationUnresolvedSubmission,
    LiveSessionCreate,
    LiveSessionStage,
    NotApplicableProposalSubmission,
    OptionalDetailsReviewedSubmission,
    ReceiptStatus,
    StartReviewSubmission,
    TeachbackSubmission,
    WorkflowErrorCode,
)
from app.services.analyzers import DeterministicAgreementAnalyzer
from app.services.analyzers.validation import build_analysis_response
from app.services.live_sessions import LiveSessionService, WorkflowFailure
from app.services.teachbacks import DeterministicTeachbackEvaluator


class AlignedAnalyzer:
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        positions = [
            ModelParticipantPosition(
                participant_id=role.value,
                summary=(
                    "Repair the fan and switches for ₹1,200, with parts charged "
                    "separately, starting today."
                ),
                evidence_message_ids=[f"message-{index}"],
            )
            for index, role in enumerate(PartyRole, start=1)
        ]
        output = AgreementAnalysisModelOutput(
            terms=[
                ModelAgreementTerm(
                    item_key=f"{topic.value}.{facet.value}",
                    topic=topic,
                    facet=facet,
                    neutral_summary=summary,
                    state=MeaningState.ALIGNED,
                    participant_positions=positions,
                    evidence_message_ids=["message-1", "message-2"],
                )
                for topic, facet, summary in [
                    (
                        AgreementTopic.SCOPE,
                        AgreementFacet.WORK,
                        "Repair one fan and two switches.",
                    ),
                    (
                        AgreementTopic.PRICE,
                        AgreementFacet.AMOUNT,
                        "The labour price is ₹1,200.",
                    ),
                    (
                        AgreementTopic.MATERIALS,
                        AgreementFacet.INCLUSION,
                        "Replacement parts are charged separately.",
                    ),
                    (
                        AgreementTopic.TIMING,
                        AgreementFacet.START,
                        "The work starts today.",
                    ),
                ]
            ]
        )
        return build_analysis_response(
            request,
            output,
            prompt_version="aligned-test-v1",
            model="mock",
        )


class NotApplicableInvalidationAnalyzer(AlignedAnalyzer):
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        base = await super().analyze(request)
        discussed = {item.message_id for item in request.messages}.issuperset(
            {"message-5", "message-6"}
        )
        completion = ModelAgreementTerm(
            item_key="completion.deadline",
            topic=AgreementTopic.COMPLETION,
            facet=AgreementFacet.DEADLINE,
            neutral_summary=(
                "The participants stated different completion times."
                if discussed
                else "No completion date or time was discussed."
            ),
            state=(
                MeaningState.CONFLICTING if discussed else MeaningState.NOT_DISCUSSED
            ),
            participant_positions=(
                [
                    ModelParticipantPosition(
                        participant_id=role.value,
                        summary=(
                            "The work should finish today."
                            if role == PartyRole.HIRER
                            else "The work should finish tomorrow."
                        ),
                        evidence_message_ids=[f"message-{index}"],
                    )
                    for index, role in zip((5, 6), PartyRole, strict=True)
                ]
                if discussed
                else []
            ),
            evidence_message_ids=["message-5", "message-6"] if discussed else [],
        )
        completion_response = build_analysis_response(
            request,
            AgreementAnalysisModelOutput(terms=[completion]),
            prompt_version="not-applicable-invalidation-v1",
            model="mock",
        )
        return AgreementAnalysisResponse(
            **base.model_dump(exclude={"terms", "primary_clarification"}),
            terms=[*base.terms, *completion_response.terms],
            primary_clarification=None,
        )


class OverlappingCoverageAnalyzer:
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        positions = [
            ModelParticipantPosition(
                participant_id=role.value,
                summary=(
                    "₹1,200 includes replacement parts."
                    if role == PartyRole.HIRER
                    else "₹1,200 is labour only; replacement parts are separate."
                ),
                evidence_message_ids=[f"message-{index}"],
            )
            for index, role in enumerate(PartyRole, start=1)
        ]
        return build_analysis_response(
            request,
            AgreementAnalysisModelOutput(
                terms=[
                    ModelAgreementTerm(
                        item_key="price.amount",
                        topic=AgreementTopic.PRICE,
                        facet=AgreementFacet.AMOUNT,
                        neutral_summary=(
                            "The participants differ on whether ₹1,200 includes "
                            "replacement parts."
                        ),
                        state=MeaningState.CONFLICTING,
                        participant_positions=positions,
                        evidence_message_ids=["message-1", "message-2"],
                    ),
                    ModelAgreementTerm(
                        item_key="materials.inclusion",
                        topic=AgreementTopic.MATERIALS,
                        facet=AgreementFacet.INCLUSION,
                        neutral_summary=(
                            "Whether replacement parts are included is unresolved."
                        ),
                        state=MeaningState.CONFLICTING,
                        participant_positions=positions,
                        evidence_message_ids=["message-1", "message-2"],
                    ),
                ]
            ),
            prompt_version="overlapping-coverage-v1",
            model="mock",
        )


class ParaphrasingOneSidedAnalyzer:
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        has_followup = any(item.message_id == "message-5" for item in request.messages)
        evidence_id = "message-5" if has_followup else "message-1"
        summary = (
            "The homeowner wants the electrician to fix two switches and one fan."
            if has_followup
            else "The homeowner requested repair of one fan and two switches."
        )
        return build_analysis_response(
            request,
            AgreementAnalysisModelOutput(
                terms=[
                    ModelAgreementTerm(
                        item_key="scope.work",
                        topic=AgreementTopic.SCOPE,
                        facet=AgreementFacet.WORK,
                        neutral_summary=summary,
                        state=MeaningState.STATED_BY_ONE,
                        participant_positions=[
                            ModelParticipantPosition(
                                participant_id=PartyRole.HIRER.value,
                                summary=summary,
                                evidence_message_ids=[evidence_id],
                            )
                        ],
                        evidence_message_ids=[evidence_id],
                    )
                ]
            ),
            prompt_version="paraphrasing-one-sided-v1",
            model="mock",
        )


def create_submission() -> LiveSessionCreate:
    timestamp = datetime(2026, 7, 16, 9, tzinfo=UTC)
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
            "I will repair them for ₹1,200 labour; replacement parts are separate.",
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


def service(*, aligned: bool = False, attempt_limit: int = 3) -> LiveSessionService:
    return LiveSessionService(
        analyzer=AlignedAnalyzer() if aligned else DeterministicAgreementAnalyzer(),
        teachback_evaluator=DeterministicTeachbackEvaluator(),
        clarification_attempt_limit=attempt_limit,
    )


async def analyzed_session(
    workflow: LiveSessionService,
):
    created = workflow.create(create_submission())
    return await workflow.analyze(created.id, AnalyzeLiveSessionSubmission())


def acknowledgment_keys(version) -> list[str]:
    return [
        item.analysis_item_key
        for item in version.terms
        if item.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
        and item.analysis_item_key in version.unresolved_item_keys
    ]


def clear_required_clarifications(workflow: LiveSessionService, session):
    while session.guidance.active_clarification_id is not None:
        version = session.current_version
        assert version is not None
        clarification_id = session.guidance.active_clarification_id
        session = workflow.leave_clarification_unresolved(
            session.id,
            clarification_id,
            LeaveClarificationUnresolvedSubmission(
                expected_agreement_version_id=version.id,
                request_id=f"leave-{len(session.clarifications)}",
            ),
        )
    return session


def start_review(workflow: LiveSessionService, session, *, request_suffix: str = ""):
    session = clear_required_clarifications(workflow, session)
    if session.guidance.optional_missing_count:
        version = session.current_version
        assert version is not None
        session = workflow.mark_optional_details_reviewed(
            session.id,
            OptionalDetailsReviewedSubmission(
                expected_agreement_version_id=version.id,
                request_id=f"optional-reviewed{request_suffix}",
            ),
        )
    version = session.current_version
    assert version is not None
    return workflow.start_review(
        session.id,
        StartReviewSubmission(
            expected_agreement_version_id=version.id,
            acknowledged_unresolved_item_keys=acknowledgment_keys(version),
            request_id=f"review-request{request_suffix}",
        ),
    )


async def matching_teachbacks(
    workflow: LiveSessionService,
    session,
    *,
    request_suffix: str = "",
):
    version = session.current_version
    assert version is not None
    text = (
        "Repair one fan and two switches. Labour is ₹1200. Replacement parts are "
        "charged separately. The work starts today. Both participants agree that "
        "work can start today."
    )
    for role in PartyRole:
        session = await workflow.submit_teachback(
            session.id,
            TeachbackSubmission(
                expected_agreement_version_id=version.id,
                participant_id=role,
                text=text,
                acknowledged_unresolved_item_keys=acknowledgment_keys(version),
                request_id=f"teachback-{role.value}{request_suffix}",
            ),
        )
    return session


def confirmations(
    workflow: LiveSessionService,
    session,
):
    version = session.current_version
    assert version is not None
    for role in PartyRole:
        teachback = next(
            item
            for item in session.teachbacks
            if item.participant_id == role
            and item.agreement_version_id == version.id
            and item.overall_state == TeachbackComparisonState.MATCHES
        )
        session = workflow.submit_confirmation(
            session.id,
            ConfirmationSubmission(
                expected_agreement_version_id=version.id,
                participant_id=role,
                teachback_id=teachback.id,
                decision=ConfirmationDecision.CONFIRM,
                unresolved_item_acknowledgments=acknowledgment_keys(version),
                request_id=f"confirmation-{role.value}",
            ),
        )
    return session


@pytest.mark.anyio
async def test_state_machine_and_immutable_versions_with_hidden_answers() -> None:
    workflow = service()
    session = await analyzed_session(workflow)
    v1 = session.current_version
    clarification = session.clarifications[-1]
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert v1 is not None and v1.version_number == 1
    assert clarification.target_item_key == "scope.work"
    assert clarification.addressed_participant_ids == [PartyRole.WORKER]
    assert clarification.answer_options == [
        "Yes, it matches",
        "No, I understand the scope differently",
    ]

    scope_answered = await workflow.submit_clarification_answer(
        session.id,
        clarification.id,
        ClarificationAnswerSubmission(
            expected_agreement_version_id=v1.id,
            participant_id=PartyRole.WORKER,
            answer="The recorded scope matches my understanding.",
            request_id="answer-scope-worker",
        ),
    )
    v2 = scope_answered.current_version
    assert v2 is not None
    assert v2.meaningful_version_number == 1
    assert v2.has_meaningful_change is False
    assert scope_answered.guidance.headline == "This point is still different"
    assert scope_answered.guidance.primary_action.value == "answer_clarification"
    materials_session = workflow.leave_clarification_unresolved(
        session.id,
        clarification.id,
        LeaveClarificationUnresolvedSubmission(
            expected_agreement_version_id=v2.id,
            request_id="leave-scope-unresolved",
        ),
    )
    clarification = materials_session.clarifications[-1]
    assert clarification.target_item_key == "materials.inclusion"

    first = await workflow.submit_clarification_answer(
        session.id,
        clarification.id,
        ClarificationAnswerSubmission(
            expected_agreement_version_id=v2.id,
            participant_id=PartyRole.HIRER,
            answer="Replacement parts should be charged separately.",
            request_id="answer-hirer",
        ),
    )
    assert first.active_participant_id == PartyRole.WORKER
    assert first.clarifications[-1].answers_received_from == [PartyRole.HIRER]
    assert first.clarifications[-1].response_message_ids == {}
    assert first.clarifications[-1].responses_revealed is False
    assert len(first.messages) == 5

    second = await workflow.submit_clarification_answer(
        session.id,
        clarification.id,
        ClarificationAnswerSubmission(
            expected_agreement_version_id=v2.id,
            participant_id=PartyRole.WORKER,
            answer="Replacement parts are charged separately.",
            request_id="answer-worker",
        ),
    )
    assert len(second.agreement_versions) == 3
    assert second.agreement_versions[0].model_dump() == v1.model_dump()
    assert second.agreement_versions[1].parent_version_id == v1.id
    assert len(second.messages) == 7
    assert second.clarifications[-1].responses_revealed is True
    assert set(second.clarifications[-1].response_message_ids) == set(PartyRole)


@pytest.mark.anyio
async def test_clarification_attempt_limit_preserves_unresolved_meaning() -> None:
    workflow = service(attempt_limit=1)
    session = await analyzed_session(workflow)
    version = session.current_version
    scope_question = session.clarifications[-1]
    assert version is not None
    session = await workflow.submit_clarification_answer(
        session.id,
        scope_question.id,
        ClarificationAnswerSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            answer="My position has not changed.",
            request_id="limit-scope-worker",
        ),
    )
    version = session.current_version
    assert version is not None
    assert session.guidance.headline == "This point is still different"
    assert session.guidance.primary_action.value == "leave_unresolved"
    session = workflow.leave_clarification_unresolved(
        session.id,
        scope_question.id,
        LeaveClarificationUnresolvedSubmission(
            expected_agreement_version_id=version.id,
            request_id="limit-leave-scope",
        ),
    )
    question = session.clarifications[-1]
    assert question.target_item_key == "materials.inclusion"
    for role in PartyRole:
        session = await workflow.submit_clarification_answer(
            session.id,
            question.id,
            ClarificationAnswerSubmission(
                expected_agreement_version_id=version.id,
                participant_id=role,
                answer="My position has not changed.",
                request_id=f"limit-{role.value}",
            ),
        )
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert session.guidance.headline == "This point is still different"
    assert session.guidance.primary_action.value == "leave_unresolved"
    current = session.current_version
    assert current is not None
    session = workflow.leave_clarification_unresolved(
        session.id,
        question.id,
        LeaveClarificationUnresolvedSubmission(
            expected_agreement_version_id=current.id,
            request_id="limit-leave-materials",
        ),
    )
    assert session.stage == LiveSessionStage.READY_FOR_REVIEW
    assert len(session.clarifications) == 2
    assert len({item.semantic_target for item in session.clarifications}) == 2
    assert "materials.inclusion" in session.current_version.unresolved_item_keys


@pytest.mark.anyio
async def test_guidance_counts_only_outstanding_required_actions() -> None:
    workflow = service()
    session = await analyzed_session(workflow)
    assert session.guidance.required_issue_count == 2
    assert session.guidance.required_item_keys == [
        "scope.work",
        "materials.inclusion",
    ]

    carried = clear_required_clarifications(workflow, session)
    assert carried.stage == LiveSessionStage.READY_FOR_REVIEW
    assert carried.guidance.required_issue_count == 0
    assert carried.guidance.required_item_keys == []
    assert {"scope.work", "materials.inclusion"}.issubset(
        set(carried.current_version.unresolved_item_keys)
    )


@pytest.mark.anyio
async def test_guidance_counts_overlapping_price_and_materials_once() -> None:
    workflow = LiveSessionService(
        analyzer=OverlappingCoverageAnalyzer(),
        teachback_evaluator=DeterministicTeachbackEvaluator(),
    )
    session = await analyzed_session(workflow)
    assert session.guidance.required_issue_count == 1
    assert session.guidance.required_item_keys == ["materials.inclusion"]
    assert session.clarifications[-1].target_item_key == "materials.inclusion"


@pytest.mark.anyio
async def test_explicitly_left_semantic_target_is_not_reasked_after_paraphrase() -> (
    None
):
    workflow = LiveSessionService(
        analyzer=ParaphrasingOneSidedAnalyzer(),
        teachback_evaluator=DeterministicTeachbackEvaluator(),
    )
    session = await analyzed_session(workflow)
    initial = session.clarifications[-1]
    version = session.current_version
    assert version is not None
    session = workflow.leave_clarification_unresolved(
        session.id,
        initial.id,
        LeaveClarificationUnresolvedSubmission(
            expected_agreement_version_id=version.id,
            request_id="leave-scope-before-paraphrase",
        ),
    )

    updated = await workflow.add_statements(
        session.id,
        AdditionalStatementsSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            messages=[
                AnalysisMessage(
                    message_id="message-5",
                    speaker_id=PartyRole.HIRER.value,
                    original_text="Please fix two switches and one fan.",
                    original_language="en",
                    order=5,
                    timestamp=datetime(2026, 7, 16, 10, tzinfo=UTC),
                )
            ],
            request_id="paraphrase-scope",
        ),
    )
    assert updated.stage == LiveSessionStage.READY_FOR_REVIEW
    assert len(updated.clarifications) == 1
    assert updated.guidance.required_issue_count == 0
    assert updated.guidance.active_clarification_id is None


@pytest.mark.anyio
async def test_stale_write_and_cross_participant_action_are_rejected() -> None:
    workflow = service(aligned=True)
    session = await analyzed_session(workflow)
    current = session.current_version
    assert current is not None
    with pytest.raises(WorkflowFailure) as stale:
        workflow.start_review(
            session.id,
            StartReviewSubmission(
                expected_agreement_version_id="agreement-old",
                request_id="stale",
            ),
        )
    assert stale.value.code == WorkflowErrorCode.STALE_AGREEMENT_VERSION
    session = start_review(workflow, session)
    with pytest.raises(WorkflowFailure) as mismatch:
        await workflow.submit_teachback(
            session.id,
            TeachbackSubmission(
                expected_agreement_version_id=current.id,
                participant_id=PartyRole.WORKER,
                text="I understand the agreement.",
                request_id="wrong-actor",
            ),
        )
    assert mismatch.value.code == WorkflowErrorCode.PARTICIPANT_MISMATCH


@pytest.mark.anyio
async def test_partial_teachback_gets_focused_followup_and_cannot_confirm() -> None:
    workflow = service(aligned=True)
    session = start_review(workflow, await analyzed_session(workflow))
    version = session.current_version
    assert version is not None
    session = await workflow.submit_teachback(
        session.id,
        TeachbackSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            text="Repair.",
            request_id="partial",
        ),
    )
    result = session.teachbacks[-1]
    assert result.overall_state in {
        TeachbackComparisonState.PARTIALLY_MATCHES,
        TeachbackComparisonState.INSUFFICIENT,
    }
    assert result.follow_up_question
    assert session.active_participant_id == PartyRole.HIRER
    assert session.stage == LiveSessionStage.AWAITING_TEACHBACKS


@pytest.mark.anyio
async def test_teachback_followup_reuses_private_prior_text() -> None:
    workflow = service(aligned=True)
    session = start_review(workflow, await analyzed_session(workflow))
    version = session.current_version
    assert version is not None
    first_text = "Repair one fan and two switches."
    session = await workflow.submit_teachback(
        session.id,
        TeachbackSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            text=first_text,
            request_id="partial-first",
        ),
    )
    assert session.teachbacks[-1].overall_state in {
        TeachbackComparisonState.PARTIALLY_MATCHES,
        TeachbackComparisonState.INSUFFICIENT,
    }

    followup_text = (
        "Labour is ₹1200. Replacement parts are charged separately. "
        "The work starts today."
    )
    session = await workflow.submit_teachback(
        session.id,
        TeachbackSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            text=followup_text,
            request_id="partial-followup",
        ),
    )
    combined = f"{first_text}\nFollow-up: {followup_text}"
    latest = session.teachbacks[-1]
    assert latest.original_text == combined
    assert "original_text" not in latest.model_dump(mode="json")
    assert latest.overall_state == TeachbackComparisonState.MATCHES
    assert session.active_participant_id == PartyRole.WORKER


@pytest.mark.anyio
async def test_contradictory_teachback_reopens_exact_item() -> None:
    workflow = service(aligned=True)
    session = start_review(workflow, await analyzed_session(workflow))
    version = session.current_version
    assert version is not None
    session = await workflow.submit_teachback(
        session.id,
        TeachbackSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            text=(
                "Replace the fan. Labour is ₹1200. Parts are charged separately. "
                "Work starts today."
            ),
            request_id="contradiction",
        ),
    )
    assert session.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert session.clarifications[-1].target_item_key == "scope.work"
    assert session.active_participant_id == PartyRole.HIRER
    with pytest.raises(WorkflowFailure) as bypass:
        workflow.start_review(
            session.id,
            StartReviewSubmission(
                expected_agreement_version_id=version.id,
                request_id="cannot-bypass-teachback-contradiction",
            ),
        )
    assert bypass.value.code == WorkflowErrorCode.INVALID_STATE


@pytest.mark.anyio
async def test_deliberate_change_reopens_item_after_prior_attempt_limit() -> None:
    workflow = service(aligned=True, attempt_limit=1)
    session = await matching_teachbacks(
        workflow,
        start_review(
            workflow,
            await analyzed_session(workflow),
            request_suffix="-first",
        ),
        request_suffix="-first",
    )
    version = session.current_version
    assert version is not None
    hirer_teachback = next(
        item
        for item in session.teachbacks
        if item.participant_id == PartyRole.HIRER
        and item.agreement_version_id == version.id
    )
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            teachback_id=hirer_teachback.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="scope.work",
            request_id="first-scope-change",
        ),
    )
    first_question = session.clarifications[-1]
    for role in PartyRole:
        session = await workflow.submit_clarification_answer(
            session.id,
            first_question.id,
            ClarificationAnswerSubmission(
                expected_agreement_version_id=version.id,
                participant_id=role,
                answer="The existing scope is correct.",
                request_id=f"first-scope-answer-{role.value}",
            ),
        )
    assert session.stage == LiveSessionStage.READY_FOR_REVIEW

    session = await matching_teachbacks(
        workflow,
        start_review(workflow, session, request_suffix="-second"),
        request_suffix="-second",
    )
    version = session.current_version
    assert version is not None
    hirer_teachback = next(
        item
        for item in session.teachbacks
        if item.participant_id == PartyRole.HIRER
        and item.agreement_version_id == version.id
    )
    reopened = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            teachback_id=hirer_teachback.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="scope.work",
            request_id="second-scope-change",
        ),
    )
    assert reopened.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert reopened.clarifications[-1].target_item_key == "scope.work"
    assert reopened.clarifications[-1].status.value == "pending"


@pytest.mark.anyio
async def test_separate_confirmations_are_bound_and_idempotent() -> None:
    workflow = service(aligned=True)
    session = await matching_teachbacks(
        workflow, start_review(workflow, await analyzed_session(workflow))
    )
    version = session.current_version
    assert version is not None
    hirer_teachback = next(
        item for item in session.teachbacks if item.participant_id == PartyRole.HIRER
    )
    submission = ConfirmationSubmission(
        expected_agreement_version_id=version.id,
        participant_id=PartyRole.HIRER,
        teachback_id=hirer_teachback.id,
        decision=ConfirmationDecision.CONFIRM,
        request_id="confirm-once",
    )
    first = workflow.submit_confirmation(session.id, submission)
    duplicate = workflow.submit_confirmation(session.id, submission)
    assert len(first.confirmations) == len(duplicate.confirmations) == 1
    assert duplicate.active_participant_id == PartyRole.WORKER
    with pytest.raises(WorkflowFailure) as wrong_record:
        workflow.submit_confirmation(
            session.id,
            ConfirmationSubmission(
                expected_agreement_version_id=version.id,
                participant_id=PartyRole.WORKER,
                teachback_id=hirer_teachback.id,
                decision=ConfirmationDecision.CONFIRM,
                request_id="cross-bind",
            ),
        )
    assert wrong_record.value.code == WorkflowErrorCode.CONFIRMATION_VERSION_MISMATCH


@pytest.mark.anyio
async def test_change_request_reopens_item_and_invalidates_confirmation() -> None:
    workflow = service(aligned=True)
    session = await matching_teachbacks(
        workflow, start_review(workflow, await analyzed_session(workflow))
    )
    version = session.current_version
    assert version is not None
    hirer_teachback = next(
        item for item in session.teachbacks if item.participant_id == PartyRole.HIRER
    )
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            teachback_id=hirer_teachback.id,
            decision=ConfirmationDecision.CONFIRM,
            request_id="confirm-before-change",
        ),
    )
    worker_teachback = next(
        item for item in session.teachbacks if item.participant_id == PartyRole.WORKER
    )
    changed = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            teachback_id=worker_teachback.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="materials.inclusion",
            request_id="request-change",
        ),
    )
    assert changed.stage == LiveSessionStage.NEEDS_CLARIFICATION
    assert changed.clarifications[-1].target_item_key == "materials.inclusion"
    assert changed.confirmations[0].invalidated_at is not None


@pytest.mark.anyio
async def test_receipt_requires_two_confirmations_and_is_immutable() -> None:
    workflow = service(aligned=True)
    session = await matching_teachbacks(
        workflow, start_review(workflow, await analyzed_session(workflow))
    )
    version = session.current_version
    assert version is not None
    hirer_teachback = next(
        item for item in session.teachbacks if item.participant_id == PartyRole.HIRER
    )
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            teachback_id=hirer_teachback.id,
            decision=ConfirmationDecision.CONFIRM,
            request_id="only-one",
        ),
    )
    with pytest.raises(WorkflowFailure) as not_ready:
        workflow.issue_receipt(
            session.id,
            IssueReceiptSubmission(
                expected_agreement_version_id=version.id,
                request_id="too-early",
            ),
        )
    assert not_ready.value.code == WorkflowErrorCode.RECEIPT_NOT_READY

    worker_teachback = next(
        item for item in session.teachbacks if item.participant_id == PartyRole.WORKER
    )
    session = workflow.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            teachback_id=worker_teachback.id,
            decision=ConfirmationDecision.CONFIRM,
            request_id="second-confirmation",
        ),
    )
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=version.id,
            request_id="issue-receipt",
        ),
    )
    duplicate = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=version.id,
            request_id="issue-again",
        ),
    )
    assert receipt == duplicate
    assert receipt.status == ReceiptStatus.FULLY_ALIGNED
    assert len(receipt.confirmations) == 2
    assert len(receipt.integrity_hash) == 64
    assert "not presented as a legally enforceable contract" in receipt.disclaimer


@pytest.mark.anyio
async def test_unresolved_receipt_preserves_all_non_aligned_categories() -> None:
    workflow = service()
    session = await matching_teachbacks(
        workflow, start_review(workflow, await analyzed_session(workflow))
    )
    session = confirmations(workflow, session)
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
    assert "scope.work" in {item.analysis_item_key for item in receipt.one_sided_terms}
    assert "completion.deadline" in {
        item.analysis_item_key for item in receipt.not_discussed_terms
    }


@pytest.mark.anyio
async def test_not_applicable_is_unilateral_until_both_propose_and_never_aligned() -> (
    None
):
    workflow = service()
    session = clear_required_clarifications(workflow, await analyzed_session(workflow))
    version = session.current_version
    assert version is not None
    session = workflow.propose_not_applicable(
        session.id,
        NotApplicableProposalSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.HIRER,
            item_key="completion.deadline",
            request_id="na-hirer",
        ),
    )
    proposal = session.current_version.not_applicable_proposals[0]
    assert proposal.proposed_by == [PartyRole.HIRER]
    assert session.current_version.version_number == version.version_number + 1
    assert (
        session.current_version.meaningful_version_number
        == version.meaningful_version_number
    )
    assert session.current_version.has_meaningful_change is False
    assert session.current_version.changes == []
    term = next(
        item
        for item in session.current_version.terms
        if item.analysis_item_key == "completion.deadline"
    )
    assert term.state == MeaningState.NOT_DISCUSSED
    version = session.current_version
    session = workflow.propose_not_applicable(
        session.id,
        NotApplicableProposalSubmission(
            expected_agreement_version_id=version.id,
            participant_id=PartyRole.WORKER,
            item_key="completion.deadline",
            request_id="na-worker",
        ),
    )
    assert set(session.current_version.not_applicable_proposals[0].proposed_by) == set(
        PartyRole
    )
    assert session.current_version.version_number == version.version_number + 1
    assert (
        session.current_version.meaningful_version_number
        == version.meaningful_version_number + 1
    )
    assert session.current_version.has_meaningful_change is True
    assert session.current_version.changes[0].item_key == "completion.deadline"
    assert (
        next(
            item
            for item in session.current_version.terms
            if item.analysis_item_key == "completion.deadline"
        ).state
        == MeaningState.NOT_DISCUSSED
    )
    proposal = session.current_version.not_applicable_proposals[0]
    assert proposal.label == "Completion date or time"
    assert proposal.summary == "No completion date or time was discussed."

    session = await matching_teachbacks(
        workflow,
        start_review(workflow, session, request_suffix="-not-applicable"),
        request_suffix="-not-applicable",
    )
    session = confirmations(workflow, session)
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="not-applicable-receipt",
        ),
    )
    assert receipt.not_applicable_terms[0].label == "Completion date or time"
    assert "completion.deadline" not in {
        item.analysis_item_key for item in receipt.not_discussed_terms
    }


@pytest.mark.anyio
async def test_later_evidence_invalidates_not_applicable_in_receipt() -> None:
    workflow = LiveSessionService(
        analyzer=NotApplicableInvalidationAnalyzer(),
        teachback_evaluator=DeterministicTeachbackEvaluator(),
    )
    session = await analyzed_session(workflow)
    version = session.current_version
    assert version is not None
    for role in PartyRole:
        session = workflow.propose_not_applicable(
            session.id,
            NotApplicableProposalSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=role,
                item_key="completion.deadline",
                request_id=f"obsolete-na-{role.value}",
            ),
        )
    assert session.current_version.not_applicable_proposals

    changed = await workflow.add_statements(
        session.id,
        AdditionalStatementsSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            messages=[
                AnalysisMessage(
                    message_id="message-5",
                    speaker_id=PartyRole.HIRER.value,
                    original_text="The work should finish today.",
                    original_language="en",
                    order=5,
                    timestamp=datetime(2026, 7, 16, 10, tzinfo=UTC),
                ),
                AnalysisMessage(
                    message_id="message-6",
                    speaker_id=PartyRole.WORKER.value,
                    original_text="The work should finish tomorrow.",
                    original_language="en",
                    order=6,
                    timestamp=datetime(2026, 7, 16, 10, 1, tzinfo=UTC),
                ),
            ],
            request_id="discuss-formerly-not-applicable",
        ),
    )
    current = changed.current_version
    assert current is not None
    assert current.not_applicable_proposals == []
    assert "completion.deadline" in current.unresolved_item_keys

    session = await matching_teachbacks(
        workflow,
        start_review(workflow, changed, request_suffix="-obsolete-na"),
        request_suffix="-obsolete-na",
    )
    session = confirmations(workflow, session)
    receipt = workflow.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="obsolete-na-receipt",
        ),
    )
    assert receipt.status == ReceiptStatus.CONTAINS_UNRESOLVED_ITEMS
    assert receipt.not_applicable_terms == []
    assert {item.analysis_item_key for item in receipt.unresolved_terms} == {
        "completion.deadline"
    }


@pytest.mark.anyio
async def test_new_statement_creates_version_and_invalidates_confirmations() -> None:
    workflow = service(aligned=True)
    session = confirmations(
        workflow,
        await matching_teachbacks(
            workflow, start_review(workflow, await analyzed_session(workflow))
        ),
    )
    old_version = session.current_version
    assert old_version is not None
    changed = await workflow.add_statements(
        session.id,
        AdditionalStatementsSubmission(
            expected_agreement_version_id=old_version.id,
            messages=[
                AnalysisMessage(
                    message_id="message-5",
                    speaker_id=PartyRole.HIRER.value,
                    original_text="I want to restate the final understanding.",
                    original_language="en",
                    order=5,
                    timestamp=datetime(2026, 7, 16, 10, tzinfo=UTC),
                )
            ],
            request_id="new-statement",
        ),
    )
    assert changed.current_version.parent_version_id == old_version.id
    assert all(item.invalidated_at for item in changed.confirmations)
    assert changed.receipt_ready is False


@pytest.mark.anyio
async def test_live_api_returns_controlled_missing_and_stale_errors() -> None:
    workflow = service(aligned=True)
    with pytest.raises(HTTPException) as missing:
        api_get_live_session("not-here", workflow)
    assert missing.value.status_code == 404
    assert missing.value.detail["code"] == "session_not_found"

    created = api_create_live_session(create_submission(), workflow)
    analyzed = await api_analyze_live_session(
        created.id, AnalyzeLiveSessionSubmission(), workflow
    )
    assert analyzed.current_agreement_version_id is not None
    with pytest.raises(HTTPException) as stale:
        api_start_review(
            created.id,
            StartReviewSubmission(
                expected_agreement_version_id="agreement-old",
                request_id="api-stale",
            ),
            workflow,
        )
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "stale_agreement_version"
