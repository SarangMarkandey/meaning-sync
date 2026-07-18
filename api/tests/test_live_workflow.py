from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
    UnderstandingQuestionStatus,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AnalyzeLiveSessionSubmission,
    ConfirmationDecision,
    ConfirmationSubmission,
    ConversationReentrySubmission,
    CurrencyCode,
    DraftStatementSubmission,
    IssueReceiptSubmission,
    LiveParticipationMode,
    LiveSessionCreate,
    LiveSessionStage,
    ParticipantReadinessSubmission,
    ReceiptStatus,
    StartUnderstandingCheckSubmission,
    WorkflowErrorCode,
)
from app.services.analyzers.validation import build_analysis_response
from app.services.live_sessions import LiveSessionService, WorkflowFailure


class FixtureAnalyzer:
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        evidence_by_role = {
            role: next(
                message.message_id
                for message in request.messages
                if message.speaker_id == role.value
            )
            for role in PartyRole
        }
        terms = [
            ModelAgreementTerm(
                item_key="scope.work",
                topic=AgreementTopic.SCOPE,
                facet=AgreementFacet.WORK,
                neutral_summary="Repair one fan and two switches.",
                state=MeaningState.ALIGNED,
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id=role.value,
                        summary="Repair one fan and two switches.",
                        evidence_message_ids=[evidence_by_role[role]],
                    )
                    for role in PartyRole
                ],
                evidence_message_ids=list(evidence_by_role.values()),
            ),
            ModelAgreementTerm(
                item_key="materials.inclusion",
                topic=AgreementTopic.MATERIALS,
                facet=AgreementFacet.INCLUSION,
                neutral_summary="The two meanings for replacement parts differ.",
                state=MeaningState.CONFLICTING,
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id=PartyRole.HIRER,
                        summary="Replacement parts are included in ₹1,200.",
                        evidence_message_ids=[evidence_by_role[PartyRole.HIRER]],
                    ),
                    ModelParticipantPosition(
                        participant_id=PartyRole.WORKER,
                        summary="Labour only; replacement parts cost extra.",
                        evidence_message_ids=[evidence_by_role[PartyRole.WORKER]],
                    ),
                ],
                evidence_message_ids=list(evidence_by_role.values()),
                clarification_question="What will the ₹1,200 cover?",
            ),
            ModelAgreementTerm(
                item_key="completion.deadline",
                topic=AgreementTopic.COMPLETION,
                facet=AgreementFacet.DEADLINE,
                neutral_summary="No completion time was discussed.",
                state=MeaningState.NOT_DISCUSSED,
            ),
        ]
        return build_analysis_response(
            request,
            AgreementAnalysisModelOutput(terms=terms),
            prompt_version="conversation-first-test-v1",
            model="mock",
        )


def workflow() -> LiveSessionService:
    return LiveSessionService(
        analyzer=FixtureAnalyzer(),
        repository=InMemoryLiveSessionRepository(),
    )


def participants() -> list[AnalysisParticipant]:
    return [
        AnalysisParticipant(id=role.value, role=role, language="en")
        for role in PartyRole
    ]


def initial_messages() -> list[AnalysisMessage]:
    timestamp = datetime(2026, 7, 18, 9, tzinfo=UTC)
    return [
        AnalysisMessage(
            message_id="message-1",
            speaker_id="hirer",
            original_text="Repair the fan and switches for ₹1,200 including parts.",
            original_language="en",
            order=1,
            timestamp=timestamp,
        ),
        AnalysisMessage(
            message_id="message-2",
            speaker_id="worker",
            original_text="₹1,200 is labour; replacement parts cost extra.",
            original_language="en",
            order=2,
            timestamp=timestamp,
        ),
    ]


async def analyzed(service: LiveSessionService):
    created = service.create(
        LiveSessionCreate(participants=participants(), messages=initial_messages())
    )
    return await service.analyze(created.id, AnalyzeLiveSessionSubmission())


def active_question(session):
    question_id = session.guidance.active_question_id
    assert question_id
    return next(item for item in session.questions if item.id == question_id)


def option(question, kind_or_text, label: str | None = None):
    is_kind = hasattr(kind_or_text, "value")
    return next(
        item
        for item in question.options
        if (
            (not is_kind and kind_or_text in item.label)
            or (
                is_kind
                and item.kind == kind_or_text
                and (label is None or label in item.label)
            )
        )
    )


def create_submission() -> LiveSessionCreate:
    return LiveSessionCreate(
        participants=participants(),
        messages=initial_messages(),
    )


def select(service, session, question, role, selected, request_id):
    return service.submit_selection(
        session.id,
        question.id,
        UnderstandingSelectionSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=role,
            option_id=selected.id,
            request_id=request_id,
        ),
    )


def start_confirmation(service, session):
    return service.start_understanding_check(
        session.id,
        StartUnderstandingCheckSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            acknowledged_unresolved_item_keys=required_acknowledgments(session),
            request_id="start-confirmation",
        ),
    )


def resolve_initial_materials(service, session):
    question = active_question(session)
    selected = option(question, "cost extra")
    for role in PartyRole:
        session = select(
            service,
            session,
            question,
            role,
            selected,
            f"resolve-{role.value}",
        )
    return session


def start_check(service, session, suffix: str = ""):
    return service.start_understanding_check(
        session.id,
        StartUnderstandingCheckSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            acknowledged_unresolved_item_keys=required_acknowledgments(session),
            request_id=f"start-confirmation{suffix}",
        ),
    )


def complete_current_checks(service, session):
    return session


def confirm_both(service, session):
    for role in PartyRole:
        session = confirm(service, session, role, f"confirm-{role.value}")
    return session


def confirm(service, session, role, request_id):
    review = session.understanding_reviews[role]
    return service.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=role,
            understanding_review_id=review.id,
            decision=ConfirmationDecision.CONFIRM,
            unresolved_item_acknowledgments=required_acknowledgments(session),
            request_id=request_id,
        ),
    )


def required_acknowledgments(session) -> list[str]:
    return [
        term.analysis_item_key
        for term in session.current_version.terms
        if term.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
    ]


def test_preferences_creator_and_readiness_are_durable() -> None:
    service = workflow()
    session = service.create(
        LiveSessionCreate(
            participants=participants(),
            participation_mode=LiveParticipationMode.SEPARATE_DEVICES,
            currency=CurrencyCode.EUR,
            creator_role=PartyRole.WORKER,
        )
    )
    restored = service.get(session.id)
    assert restored.currency == CurrencyCode.EUR
    assert restored.creator_role == PartyRole.WORKER
    assert restored.participation_mode == LiveParticipationMode.SEPARATE_DEVICES
    assert restored.participant_readiness == {
        PartyRole.HIRER: False,
        PartyRole.WORKER: False,
    }


@pytest.mark.parametrize("currency", list(CurrencyCode))
def test_each_supported_currency_round_trips(currency: CurrencyCode) -> None:
    service = workflow()
    created = service.create(
        LiveSessionCreate(participants=participants(), currency=currency)
    )
    assert service.get(created.id).currency == currency


@pytest.mark.anyio
async def test_legacy_statement_batch_returns_to_conversation_without_analysis() -> (
    None
):
    class CountingAnalyzer(FixtureAnalyzer):
        calls = 0

        async def analyze(
            self, request: AgreementAnalysisRequest
        ) -> AgreementAnalysisResponse:
            self.calls += 1
            return await super().analyze(request)

    analyzer = CountingAnalyzer()
    service = LiveSessionService(
        analyzer=analyzer,
        repository=InMemoryLiveSessionRepository(),
    )
    session = await analyzed(service)
    assert analyzer.calls == 1
    message = AnalysisMessage(
        message_id="message-3",
        speaker_id="hirer",
        original_text="Payment is due after the work is complete.",
        original_language="en",
        order=3,
        timestamp=datetime(2026, 7, 18, 9, 2, tzinfo=UTC),
    )
    session = await service.add_statements(
        session.id,
        AdditionalStatementsSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            messages=[message],
            request_id="append-without-analysis",
        ),
    )
    assert analyzer.calls == 1
    assert session.stage == LiveSessionStage.CONVERSATION_DRAFT
    assert session.messages[-1].original_text == message.original_text
    assert not any(session.participant_readiness.values())


@pytest.mark.anyio
async def test_both_people_must_speak_and_be_ready_before_compare() -> None:
    service = workflow()
    session = service.create(LiveSessionCreate(participants=participants()))
    for role, text in [
        (PartyRole.HIRER, "Please repair the fan and switches."),
        (PartyRole.WORKER, "The labour price is ₹1,200."),
    ]:
        session = service.add_draft_statement(
            session.id,
            role,
            DraftStatementSubmission(original_text=text, request_id=f"message-{role}"),
        )
    with pytest.raises(WorkflowFailure) as not_ready:
        await service.analyze(session.id, AnalyzeLiveSessionSubmission())
    assert not_ready.value.code == WorkflowErrorCode.INVALID_STATE
    for role in PartyRole:
        session = service.set_participant_readiness(
            session.id,
            role,
            ParticipantReadinessSubmission(ready=True, request_id=f"ready-{role}"),
        )
    analyzed_session = await service.analyze(session.id, AnalyzeLiveSessionSubmission())
    assert analyzed_session.current_agreement_version_id
    assert not any(analyzed_session.participant_readiness.values())


def test_new_message_clears_both_readiness_flags() -> None:
    service = workflow()
    session = service.create(LiveSessionCreate(participants=participants()))
    for role in PartyRole:
        session = service.set_participant_readiness(
            session.id,
            role,
            ParticipantReadinessSubmission(ready=True, request_id=f"ready-{role}"),
        )
    session = service.add_draft_statement(
        session.id,
        PartyRole.HIRER,
        DraftStatementSubmission(
            original_text="One more thing about the work.",
            request_id="late-message",
        ),
    )
    assert not any(session.participant_readiness.values())


@pytest.mark.anyio
async def test_first_choice_is_hidden_until_both_submit() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    selected = option(question, "cost extra")
    first = select(service, session, question, PartyRole.HIRER, selected, "first")
    public = next(item for item in first.questions if item.id == question.id)
    assert public.status == UnderstandingQuestionStatus.PARTIALLY_ANSWERED
    assert public.responses_revealed is False
    assert public.outcome is None
    assert "selections" not in first.model_dump_json()
    second = select(service, first, question, PartyRole.WORKER, selected, "second")
    revealed = next(item for item in second.questions if item.id == question.id)
    assert revealed.responses_revealed is True
    assert revealed.outcome is not None
    assert len(second.agreement_versions) == 2
    material = next(
        item
        for item in second.current_version.terms
        if item.analysis_item_key == "materials.inclusion"
    )
    assert material.state == MeaningState.ALIGNED


@pytest.mark.anyio
async def test_different_choices_do_not_repeat_the_same_choice_question() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    included = option(question, "included")
    extra = option(question, "cost extra")
    session = select(service, session, question, PartyRole.HIRER, included, "one")
    session = select(service, session, question, PartyRole.WORKER, extra, "two")
    completed = next(item for item in session.questions if item.id == question.id)
    assert completed.responses_revealed is True
    assert completed.outcome is not None
    marker = active_question(session)
    assert marker.id != question.id
    assert marker.status == UnderstandingQuestionStatus.NEEDS_CLARIFICATION


@pytest.mark.anyio
async def test_missing_items_are_optional_and_no_teachback_is_created() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    selected = option(question, "cost extra")
    for role in PartyRole:
        session = select(service, session, question, role, selected, f"resolve-{role}")
    session = start_confirmation(service, session)
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    assert not [
        item for item in session.questions if item.kind.value == "understanding_check"
    ]
    assert all(
        item.status.value == "skipped"
        for item in session.understanding_reviews.values()
    )


@pytest.mark.anyio
async def test_two_separate_confirmations_are_required() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    selected = option(question, "cost extra")
    for role in PartyRole:
        session = select(service, session, question, role, selected, f"resolve-{role}")
    session = start_confirmation(service, session)
    session = confirm(service, session, PartyRole.HIRER, "confirm-hirer")
    assert session.stage == LiveSessionStage.AWAITING_CONFIRMATIONS
    session = confirm(service, session, PartyRole.WORKER, "confirm-worker")
    assert session.stage == LiveSessionStage.CONFIRMED


@pytest.mark.anyio
async def test_change_request_reenters_and_invalidates_confirmation() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    selected = option(question, "cost extra")
    for role in PartyRole:
        session = select(service, session, question, role, selected, f"resolve-{role}")
    session = start_confirmation(service, session)
    session = confirm(service, session, PartyRole.HIRER, "confirm-hirer")
    worker_review = session.understanding_reviews[PartyRole.WORKER]
    changed = service.submit_confirmation(
        session.id,
        ConfirmationSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            participant_id=PartyRole.WORKER,
            understanding_review_id=worker_review.id,
            decision=ConfirmationDecision.REQUEST_CHANGE,
            change_item_key="scope.work",
            request_id="request-change",
        ),
    )
    assert changed.stage == LiveSessionStage.CONVERSATION_DRAFT
    assert changed.conversation_reentry_item_key == "scope.work"
    assert not [item for item in changed.confirmations if item.invalidated_at is None]
    assert not any(changed.participant_readiness.values())


@pytest.mark.anyio
async def test_receipt_preserves_open_missing_currency_evidence_and_history() -> None:
    service = workflow()
    session = await analyzed(service)
    question = active_question(session)
    for role in PartyRole:
        session = service.leave_question_unresolved(
            session.id,
            question.id,
            LeaveQuestionUnresolvedSubmission(
                expected_agreement_version_id=session.current_agreement_version_id,
                participant_id=role,
                request_id=f"leave-{role}",
            ),
        )
    session = start_confirmation(service, session)
    for role in PartyRole:
        session = confirm(service, session, role, f"confirm-{role}")
    receipt = service.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="receipt",
        ),
    )
    assert receipt.currency == CurrencyCode.INR
    assert receipt.status == ReceiptStatus.CONTAINS_UNRESOLVED_ITEMS
    assert receipt.unresolved_terms
    assert receipt.not_discussed_terms
    assert all(term.evidence for term in receipt.unresolved_terms)
    assert receipt.clarification_history


@pytest.mark.anyio
async def test_explicit_reentry_keeps_versions_immutable() -> None:
    service = workflow()
    session = await analyzed(service)
    first_version = session.current_version
    session = service.reenter_conversation(
        session.id,
        ConversationReentrySubmission(
            expected_agreement_version_id=first_version.id,
            item_key="scope.work",
            request_id="reenter",
        ),
    )
    for role in PartyRole:
        session = service.set_participant_readiness(
            session.id,
            role,
            ParticipantReadinessSubmission(
                ready=True, request_id=f"ready-again-{role}"
            ),
        )
    session = await service.analyze(
        session.id,
        AnalyzeLiveSessionSubmission(expected_agreement_version_id=first_version.id),
    )
    assert len(session.agreement_versions) == 2
    assert session.current_version.parent_version_id == first_version.id
    assert session.agreement_versions[0] == first_version
