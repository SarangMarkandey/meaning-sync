from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from app.domain.agreement_guidance import (
    addressed_participants,
    agreement_semantic_fingerprint,
    clarification_fingerprint,
    neutral_question_and_options,
    optional_item_keys,
    ordered_clarification_candidates,
    semantic_target,
)
from app.schemas.analysis import (
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AgreementTerm,
    AnalysisClarificationContext,
    AnalysisMessage,
    MeaningState,
    PartyRole,
    SessionMode,
)
from app.schemas.teachback import (
    TeachbackComparisonState,
    TeachbackEvaluationRequest,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AgreementVersion,
    AgreementVersionChange,
    AnalyzeLiveSessionSubmission,
    ClarificationAnswerSubmission,
    ClarificationHistoryEntry,
    ClarificationWorkflowRecord,
    ClarificationWorkflowStatus,
    ConfirmationDecision,
    ConfirmationRecord,
    ConfirmationStatusView,
    ConfirmationSubmission,
    IssueReceiptSubmission,
    LeaveClarificationUnresolvedSubmission,
    LiveClarityReceipt,
    LiveGuidanceAction,
    LiveSessionCreate,
    LiveSessionStage,
    LiveSessionView,
    LiveUserStage,
    LiveWorkflowGuidance,
    NotApplicableProposal,
    NotApplicableProposalSubmission,
    OptionalDetailsReviewedSubmission,
    ParticipantReview,
    ParticipantReviewStatus,
    ReceiptConfirmation,
    ReceiptParticipant,
    ReceiptStatus,
    ReceiptTeachbackStatus,
    StartReviewSubmission,
    TeachbackRecord,
    TeachbackSubmission,
    WorkflowErrorCode,
)
from app.services.analyzers import AgreementAnalyzer
from app.services.teachbacks import TeachbackEvaluator


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _now() -> datetime:
    return datetime.now(UTC)


def _deep_copy[T](model: T) -> T:
    return deepcopy(model)


class WorkflowFailure(Exception):
    def __init__(
        self,
        code: WorkflowErrorCode,
        message: str,
        *,
        status_code: int,
        retryable: bool = False,
        current_agreement_version_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.current_agreement_version_id = current_agreement_version_id


@dataclass
class _LiveSessionRecord:
    id: str
    created_at: datetime
    participants: list
    messages: list[AnalysisMessage]
    stage: LiveSessionStage = LiveSessionStage.CONVERSATION_DRAFT
    versions: list[AgreementVersion] = field(default_factory=list)
    current_version_id: str | None = None
    clarifications: list[ClarificationWorkflowRecord] = field(default_factory=list)
    pending_answers: dict[str, dict[PartyRole, str]] = field(default_factory=dict)
    reviews: dict[PartyRole, ParticipantReview] = field(default_factory=dict)
    active_participant_id: PartyRole | None = None
    teachbacks: list[TeachbackRecord] = field(default_factory=list)
    confirmations: list[ConfirmationRecord] = field(default_factory=list)
    receipt: LiveClarityReceipt | None = None
    processed_request_ids: set[str] = field(default_factory=set)
    optional_details_reviewed: bool = False


class LiveSessionService:
    """Server-owned, in-memory lifecycle for Live agreement sessions."""

    def __init__(
        self,
        *,
        analyzer: AgreementAnalyzer,
        teachback_evaluator: TeachbackEvaluator,
        clarification_attempt_limit: int = 3,
    ) -> None:
        if clarification_attempt_limit < 1:
            raise ValueError("clarification attempt limit must be positive")
        self._analyzer = analyzer
        self._teachback_evaluator = teachback_evaluator
        self._clarification_attempt_limit = clarification_attempt_limit
        self._sessions: dict[str, _LiveSessionRecord] = {}
        self._lock = RLock()

    def create(self, submission: LiveSessionCreate) -> LiveSessionView:
        session_id = _id("live")
        request = AgreementAnalysisRequest(
            session_id=session_id,
            mode=SessionMode.LIVE,
            participants=submission.participants,
            messages=submission.messages,
        )
        if any(
            participant.id != participant.role.value
            for participant in request.participants
        ):
            raise WorkflowFailure(
                WorkflowErrorCode.PARTICIPANT_MISMATCH,
                "Live participant IDs must match the server-owned hirer and "
                "worker roles.",
                status_code=422,
            )
        record = _LiveSessionRecord(
            id=session_id,
            created_at=_now(),
            participants=[_deep_copy(item) for item in request.participants],
            messages=[_deep_copy(item) for item in request.messages],
        )
        with self._lock:
            self._sessions[record.id] = record
            return self._view(record)

    def get(self, session_id: str) -> LiveSessionView:
        with self._lock:
            return self._view(self._record(session_id))

    def list_versions(self, session_id: str) -> list[AgreementVersion]:
        with self._lock:
            return [_deep_copy(item) for item in self._record(session_id).versions]

    def get_version(self, session_id: str, version_id: str) -> AgreementVersion:
        with self._lock:
            record = self._record(session_id)
            version = next(
                (item for item in record.versions if item.id == version_id), None
            )
            if version is None:
                raise WorkflowFailure(
                    WorkflowErrorCode.STALE_AGREEMENT_VERSION,
                    "That agreement version does not belong to this session.",
                    status_code=404,
                    current_agreement_version_id=record.current_version_id,
                )
            return _deep_copy(version)

    async def analyze(
        self, session_id: str, submission: AnalyzeLiveSessionSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if record.stage != LiveSessionStage.CONVERSATION_DRAFT:
                self._require_current_version(
                    record, submission.expected_agreement_version_id
                )
                raise self._invalid_state(
                    record, "This session has already been analyzed."
                )
            if submission.expected_agreement_version_id is not None:
                raise self._stale(record)
            record.stage = LiveSessionStage.ANALYZING
            request = self._analysis_request(record, record.messages)

        try:
            response = await self._analyzer.analyze(request)
        except Exception:
            with self._lock:
                current = self._record(session_id)
                if current.stage == LiveSessionStage.ANALYZING:
                    current.stage = LiveSessionStage.CONVERSATION_DRAFT
            raise

        with self._lock:
            record = self._record(session_id)
            if record.stage != LiveSessionStage.ANALYZING or record.versions:
                raise self._invalid_state(
                    record, "The analysis result is no longer current."
                )
            self._apply_analysis(record, response)
            return self._view(record)

    async def submit_clarification_answer(
        self,
        session_id: str,
        clarification_id: str,
        submission: ClarificationAnswerSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_stage(record, LiveSessionStage.NEEDS_CLARIFICATION)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            clarification = self._clarification(record, clarification_id)
            if clarification.status == ClarificationWorkflowStatus.STILL_UNRESOLVED:
                attempts = sum(
                    item.semantic_target == clarification.semantic_target
                    for item in record.clarifications
                )
                if attempts >= self._clarification_attempt_limit:
                    raise WorkflowFailure(
                        WorkflowErrorCode.CLARIFICATION_LIMIT_REACHED,
                        "This item reached the clarification limit. Leave it "
                        "explicitly unresolved to continue.",
                        status_code=409,
                        current_agreement_version_id=version.id,
                    )
                clarification = ClarificationWorkflowRecord(
                    id=_id("clarification"),
                    target_item_key=clarification.target_item_key,
                    target_agreement_version_id=version.id,
                    term_id=self._term(version, clarification.target_item_key).id,
                    question=clarification.question,
                    answer_options=clarification.answer_options,
                    fingerprint=clarification.fingerprint,
                    semantic_target=clarification.semantic_target,
                    addressed_participant_ids=(clarification.addressed_participant_ids),
                    status=ClarificationWorkflowStatus.PENDING,
                    attempt_number=attempts + 1,
                    created_at=_now(),
                )
                record.clarifications.append(clarification)
            if clarification.status not in {
                ClarificationWorkflowStatus.PENDING,
                ClarificationWorkflowStatus.ANSWERED,
            }:
                raise self._invalid_state(
                    record, "This clarification is no longer accepting answers."
                )
            answers = record.pending_answers.setdefault(clarification.id, {})
            retrying_analysis = (
                len(answers) == len(clarification.addressed_participant_ids)
                and submission.participant_id in answers
            )
            if not retrying_analysis:
                expected_actor = self._next_clarification_actor(record, clarification)
                if submission.participant_id != expected_actor:
                    raise self._participant_mismatch(expected_actor)
            if submission.participant_id not in answers:
                answers[submission.participant_id] = submission.answer
            elif len(answers) < len(clarification.addressed_participant_ids):
                return self._view(record)
            self._replace_clarification(
                record,
                clarification.model_copy(
                    update={
                        "answers_received_from": list(answers),
                        "responses_revealed": False,
                        "status": (
                            ClarificationWorkflowStatus.ANSWERED
                            if len(answers)
                            == len(clarification.addressed_participant_ids)
                            else ClarificationWorkflowStatus.PENDING
                        ),
                    }
                ),
            )
            if len(answers) < len(clarification.addressed_participant_ids):
                record.processed_request_ids.add(submission.request_id)
                record.active_participant_id = clarification.addressed_participant_ids[
                    len(answers)
                ]
                return self._view(record)

            response_messages = self._clarification_messages(
                record, clarification, answers
            )
            candidate_messages = [*record.messages, *response_messages]
            response_ids = {
                PartyRole(message.speaker_id): message.message_id
                for message in response_messages
            }
            request = self._analysis_request(
                record,
                candidate_messages,
                additional_contexts=[
                    AnalysisClarificationContext(
                        clarification_id=clarification.id,
                        target_item_key=clarification.target_item_key,
                        question=clarification.question,
                        response_message_ids=response_ids,
                    )
                ],
            )
            record.stage = LiveSessionStage.ANALYZING

        try:
            response = await self._analyzer.analyze(request)
        except Exception:
            with self._lock:
                current = self._record(session_id)
                if current.stage == LiveSessionStage.ANALYZING:
                    current.stage = LiveSessionStage.NEEDS_CLARIFICATION
                    current.active_participant_id = submission.participant_id
            raise

        with self._lock:
            record = self._record(session_id)
            if record.current_version_id != version.id:
                raise self._stale(record)
            record.messages.extend(response_messages)
            record.pending_answers.pop(clarification.id, None)
            record.processed_request_ids.add(submission.request_id)
            new_version = self._build_version(record, response)
            target = next(
                (
                    term
                    for term in new_version.terms
                    if term.analysis_item_key == clarification.target_item_key
                ),
                None,
            )
            resolved = target is not None and target.state == MeaningState.ALIGNED
            completed = clarification.model_copy(
                update={
                    "answers_received_from": list(
                        clarification.addressed_participant_ids
                    ),
                    "responses_revealed": True,
                    "response_message_ids": response_ids,
                    "status": (
                        ClarificationWorkflowStatus.RESOLVED
                        if resolved
                        else ClarificationWorkflowStatus.STILL_UNRESOLVED
                    ),
                    "resolved_at": _now(),
                    "resulting_agreement_version_id": new_version.id,
                }
            )
            self._replace_clarification(record, completed)
            self._commit_version(record, new_version)
            self._select_next_stage(record)
            return self._view(record)

    def leave_clarification_unresolved(
        self,
        session_id: str,
        clarification_id: str,
        submission: LeaveClarificationUnresolvedSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_stage(record, LiveSessionStage.NEEDS_CLARIFICATION)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            clarification = self._clarification(record, clarification_id)
            if clarification.status not in {
                ClarificationWorkflowStatus.PENDING,
                ClarificationWorkflowStatus.ANSWERED,
                ClarificationWorkflowStatus.STILL_UNRESOLVED,
            }:
                raise self._invalid_state(
                    record, "This clarification has already been closed."
                )
            self._replace_clarification(
                record,
                clarification.model_copy(
                    update={
                        "status": ClarificationWorkflowStatus.LEFT_UNRESOLVED,
                        "resolved_at": _now(),
                        "resulting_agreement_version_id": version.id,
                    }
                ),
            )
            record.pending_answers.pop(clarification.id, None)
            record.processed_request_ids.add(submission.request_id)
            record.active_participant_id = None
            self._select_next_stage(record)
            return self._view(record)

    async def add_statements(
        self, session_id: str, submission: AdditionalStatementsSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_modifiable(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            messages = self._validated_appended_messages(record, submission.messages)
            candidate_messages = [*record.messages, *messages]
            request = self._analysis_request(record, candidate_messages)
            previous_stage = record.stage
            record.stage = LiveSessionStage.ANALYZING

        try:
            response = await self._analyzer.analyze(request)
        except Exception:
            with self._lock:
                current = self._record(session_id)
                if current.stage == LiveSessionStage.ANALYZING:
                    current.stage = previous_stage
            raise

        with self._lock:
            record = self._record(session_id)
            if record.current_version_id != version.id:
                raise self._stale(record)
            record.messages.extend(messages)
            record.processed_request_ids.add(submission.request_id)
            new_version = self._build_version(record, response)
            self._close_pending_clarifications(record, new_version)
            self._commit_version(record, new_version)
            self._invalidate_review(record)
            self._select_next_stage(record)
            return self._view(record)

    def propose_not_applicable(
        self, session_id: str, submission: NotApplicableProposalSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_modifiable(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if self._active_clarification(record) is not None:
                raise self._invalid_state(
                    record,
                    "Finish or leave the current required clarification before "
                    "reviewing optional details.",
                )
            term = self._term(version, submission.item_key)
            if term.state != MeaningState.NOT_DISCUSSED:
                raise WorkflowFailure(
                    WorkflowErrorCode.CLARIFICATION_TARGET_MISSING,
                    "Only a not-discussed item can be proposed as not applicable.",
                    status_code=422,
                    current_agreement_version_id=version.id,
                )
            proposals = list(version.not_applicable_proposals)
            existing = next(
                (item for item in proposals if item.item_key == term.analysis_item_key),
                None,
            )
            if existing is None:
                proposals.append(
                    NotApplicableProposal(
                        item_key=term.analysis_item_key,
                        label=term.label,
                        summary=term.summary,
                        proposed_by=[submission.participant_id],
                    )
                )
            elif submission.participant_id not in existing.proposed_by:
                proposals[proposals.index(existing)] = existing.model_copy(
                    update={
                        "proposed_by": [
                            *existing.proposed_by,
                            submission.participant_id,
                        ]
                    }
                )
            else:
                record.processed_request_ids.add(submission.request_id)
                return self._view(record)

            mutual = self._mutually_not_applicable(proposals)
            semantic_fingerprint = agreement_semantic_fingerprint(version.terms, mutual)
            meaningful = semantic_fingerprint != version.semantic_fingerprint
            changes = (
                [
                    AgreementVersionChange(
                        item_key=term.analysis_item_key,
                        label=term.label,
                        previous_state=term.state,
                        current_state=term.state,
                        resulting_meaning=(
                            "Both participants marked this optional detail as not "
                            "applicable."
                        ),
                    )
                ]
                if meaningful
                else []
            )
            derived = AgreementVersion(
                **version.model_dump(
                    mode="python",
                    exclude={
                        "id",
                        "version_number",
                        "meaningful_version_number",
                        "has_meaningful_change",
                        "semantic_fingerprint",
                        "parent_version_id",
                        "created_at",
                        "unresolved_item_keys",
                        "not_applicable_proposals",
                        "changes",
                    },
                ),
                id=_id("agreement"),
                version_number=version.version_number + 1,
                meaningful_version_number=(
                    version.meaningful_version_number + 1
                    if meaningful
                    else version.meaningful_version_number
                ),
                has_meaningful_change=meaningful,
                semantic_fingerprint=semantic_fingerprint,
                parent_version_id=version.id,
                created_at=_now(),
                unresolved_item_keys=[
                    item for item in version.unresolved_item_keys if item not in mutual
                ],
                not_applicable_proposals=proposals,
                changes=changes,
            )
            record.processed_request_ids.add(submission.request_id)
            self._commit_version(record, derived)
            self._invalidate_review(record)
            record.stage = LiveSessionStage.READY_FOR_REVIEW
            return self._view(record)

    def mark_optional_details_reviewed(
        self,
        session_id: str,
        submission: OptionalDetailsReviewedSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if self._active_clarification(record) is not None:
                raise self._invalid_state(
                    record,
                    "Finish or leave the current required clarification first.",
                )
            if record.stage not in {
                LiveSessionStage.NEEDS_CLARIFICATION,
                LiveSessionStage.READY_FOR_REVIEW,
            }:
                raise self._invalid_state(
                    record, "Optional details cannot be reviewed during this step."
                )
            record.optional_details_reviewed = True
            record.stage = LiveSessionStage.READY_FOR_REVIEW
            record.processed_request_ids.add(submission.request_id)
            return self._view(record)

    def start_review(
        self, session_id: str, submission: StartReviewSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            if record.stage not in {
                LiveSessionStage.NEEDS_CLARIFICATION,
                LiveSessionStage.READY_FOR_REVIEW,
            }:
                raise self._invalid_state(
                    record, "This agreement is not ready for review."
                )
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if any(record.pending_answers.values()):
                raise self._invalid_state(
                    record, "Complete the in-progress clarification before review."
                )
            if self._active_clarification(record) is not None:
                raise self._invalid_state(
                    record,
                    "Answer or explicitly leave the current clarification unresolved.",
                )
            if (
                optional_item_keys(
                    version.terms,
                    self._mutually_not_applicable(version.not_applicable_proposals),
                )
                and not record.optional_details_reviewed
            ):
                raise self._invalid_state(
                    record, "Review the optional missing details before final review."
                )
            pending_targets = {
                item.target_item_key
                for item in record.clarifications
                if item.status == ClarificationWorkflowStatus.PENDING
                and item.target_agreement_version_id == version.id
            }
            if not pending_targets.issubset(set(version.unresolved_item_keys)):
                raise self._invalid_state(
                    record,
                    "Resolve the teach-back or change-request clarification "
                    "before review.",
                )
            self._require_acknowledgments(
                version, submission.acknowledged_unresolved_item_keys
            )
            self._close_pending_clarifications(record, version)
            record.reviews = {
                PartyRole.HIRER: ParticipantReview(
                    participant_id=PartyRole.HIRER,
                    agreement_version_id=version.id,
                    status=ParticipantReviewStatus.REVIEWING,
                ),
                PartyRole.WORKER: ParticipantReview(
                    participant_id=PartyRole.WORKER,
                    agreement_version_id=version.id,
                    status=ParticipantReviewStatus.NOT_STARTED,
                ),
            }
            record.active_participant_id = PartyRole.HIRER
            record.stage = LiveSessionStage.AWAITING_TEACHBACKS
            record.processed_request_ids.add(submission.request_id)
            return self._view(record)

    async def submit_teachback(
        self, session_id: str, submission: TeachbackSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_stage(record, LiveSessionStage.AWAITING_TEACHBACKS)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            self._require_actor(record, submission.participant_id)
            self._require_acknowledgments(
                version, submission.acknowledged_unresolved_item_keys
            )
            previous_partial = next(
                (
                    item
                    for item in reversed(record.teachbacks)
                    if item.participant_id == submission.participant_id
                    and item.agreement_version_id == version.id
                    and item.overall_state
                    in {
                        TeachbackComparisonState.PARTIALLY_MATCHES,
                        TeachbackComparisonState.INSUFFICIENT,
                    }
                ),
                None,
            )
            evaluation_text = (
                submission.text
                if previous_partial is None
                else f"{previous_partial.original_text}\nFollow-up: {submission.text}"
            )
            request = TeachbackEvaluationRequest(
                participant_id=submission.participant_id,
                agreement_version_id=version.id,
                teachback_text=evaluation_text,
                original_language=submission.original_language,
                reviewed_terms=version.terms,
                required_item_keys=self._required_teachback_items(version),
                acknowledged_unresolved_item_keys=(
                    submission.acknowledged_unresolved_item_keys
                ),
            )

        evaluation = await self._teachback_evaluator.evaluate(request)

        with self._lock:
            record = self._record(session_id)
            if record.current_version_id != version.id:
                raise self._stale(record)
            self._require_actor(record, submission.participant_id)
            teachback = TeachbackRecord(
                id=_id("teachback"),
                participant_id=submission.participant_id,
                agreement_version_id=version.id,
                original_text=evaluation_text,
                original_language=submission.original_language,
                covered_item_keys=evaluation.covered_item_keys,
                item_results=evaluation.item_results,
                overall_state=evaluation.overall_state,
                missing_or_contradictory_summary=(
                    evaluation.missing_or_contradictory_summary
                ),
                follow_up_question=evaluation.follow_up_question,
                acknowledged_unresolved_item_keys=(
                    submission.acknowledged_unresolved_item_keys
                ),
                created_at=_now(),
            )
            record.teachbacks.append(teachback)
            record.processed_request_ids.add(submission.request_id)
            if evaluation.overall_state == TeachbackComparisonState.CONTRADICTS:
                affected = next(
                    item.analysis_item_key
                    for item in evaluation.item_results
                    if item.state == TeachbackComparisonState.CONTRADICTS
                )
                self._reopen_for_change(
                    record,
                    version,
                    affected,
                    "The teach-back differs from the recorded meaning. "
                    "What should the agreement say?",
                )
            elif evaluation.overall_state in {
                TeachbackComparisonState.PARTIALLY_MATCHES,
                TeachbackComparisonState.INSUFFICIENT,
            }:
                record.reviews[submission.participant_id] = ParticipantReview(
                    participant_id=submission.participant_id,
                    agreement_version_id=version.id,
                    status=ParticipantReviewStatus.REVIEWING,
                    teachback_id=teachback.id,
                )
            else:
                record.reviews[submission.participant_id] = ParticipantReview(
                    participant_id=submission.participant_id,
                    agreement_version_id=version.id,
                    status=ParticipantReviewStatus.TEACHBACK_SUBMITTED,
                    teachback_id=teachback.id,
                )
                if submission.participant_id == PartyRole.HIRER:
                    record.reviews[PartyRole.WORKER] = record.reviews[
                        PartyRole.WORKER
                    ].model_copy(update={"status": ParticipantReviewStatus.REVIEWING})
                    record.active_participant_id = PartyRole.WORKER
                else:
                    record.reviews = {
                        role: review.model_copy(
                            update={"status": ParticipantReviewStatus.READY_TO_CONFIRM}
                        )
                        for role, review in record.reviews.items()
                    }
                    record.active_participant_id = PartyRole.HIRER
                    record.stage = LiveSessionStage.AWAITING_CONFIRMATIONS
            return self._view(record)

    def submit_confirmation(
        self, session_id: str, submission: ConfirmationSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            if submission.request_id in record.processed_request_ids:
                return self._view(record)
            self._require_stage(record, LiveSessionStage.AWAITING_CONFIRMATIONS)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            self._require_actor(record, submission.participant_id)
            if submission.decision == ConfirmationDecision.CONFIRM:
                self._require_acknowledgments(
                    version, submission.unresolved_item_acknowledgments
                )
            teachback = next(
                (
                    item
                    for item in reversed(record.teachbacks)
                    if item.id == submission.teachback_id
                    and item.participant_id == submission.participant_id
                    and item.agreement_version_id == version.id
                ),
                None,
            )
            if teachback is None:
                raise WorkflowFailure(
                    WorkflowErrorCode.CONFIRMATION_VERSION_MISMATCH,
                    "Confirmation must use this participant's current teach-back.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            if teachback.overall_state != TeachbackComparisonState.MATCHES:
                raise WorkflowFailure(
                    WorkflowErrorCode.TEACHBACK_INCOMPLETE,
                    "A matching teach-back is required before confirmation.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            if submission.decision == ConfirmationDecision.REQUEST_CHANGE:
                self._term(version, submission.change_item_key or "")
                record.processed_request_ids.add(submission.request_id)
                self._reopen_for_change(
                    record,
                    version,
                    submission.change_item_key or "",
                    "A participant requested a change. What should this "
                    "agreement item say?",
                )
                return self._view(record)
            existing = next(
                (
                    item
                    for item in record.confirmations
                    if item.participant_id == submission.participant_id
                    and item.agreement_version_id == version.id
                    and item.invalidated_at is None
                ),
                None,
            )
            if existing is None:
                participant = next(
                    item
                    for item in record.participants
                    if item.role == submission.participant_id
                )
                confirmation = ConfirmationRecord(
                    id=_id("confirmation"),
                    participant_id=submission.participant_id,
                    agreement_version_id=version.id,
                    teachback_id=teachback.id,
                    unresolved_item_acknowledgments=(
                        submission.unresolved_item_acknowledgments
                    ),
                    confirmed_at=_now(),
                    language=participant.language,
                    request_id=submission.request_id,
                )
                record.confirmations.append(confirmation)
            record.processed_request_ids.add(submission.request_id)
            record.reviews[submission.participant_id] = record.reviews[
                submission.participant_id
            ].model_copy(update={"status": ParticipantReviewStatus.CONFIRMED})
            current_confirmations = self._current_confirmations(record, version.id)
            if len(current_confirmations) == 2:
                record.stage = LiveSessionStage.CONFIRMED
                record.active_participant_id = None
            else:
                record.active_participant_id = PartyRole.WORKER
            return self._view(record)

    def issue_receipt(
        self, session_id: str, submission: IssueReceiptSubmission
    ) -> LiveClarityReceipt:
        with self._lock:
            record = self._record(session_id)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if record.receipt is not None:
                return _deep_copy(record.receipt)
            confirmations = self._current_confirmations(record, version.id)
            if record.stage != LiveSessionStage.CONFIRMED or len(confirmations) != 2:
                raise WorkflowFailure(
                    WorkflowErrorCode.RECEIPT_NOT_READY,
                    "Both participants must confirm the current version first.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            teachbacks = [
                item
                for item in record.teachbacks
                if item.agreement_version_id == version.id
                and item.overall_state == TeachbackComparisonState.MATCHES
                and item.id
                in {confirmation.teachback_id for confirmation in confirmations}
            ]
            if len(teachbacks) != 2:
                raise WorkflowFailure(
                    WorkflowErrorCode.RECEIPT_NOT_READY,
                    "Both participants need a matching teach-back.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            issued_at = _now()
            payload = self._receipt_payload(
                record, version, confirmations, teachbacks, issued_at
            )
            receipt_without_hash = LiveClarityReceipt(
                **payload, integrity_hash="0" * 64
            )
            canonical = json.dumps(
                receipt_without_hash.model_dump(
                    mode="json", exclude={"integrity_hash"}
                ),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            receipt = receipt_without_hash.model_copy(
                update={"integrity_hash": hashlib.sha256(canonical).hexdigest()}
            )
            record.receipt = receipt
            record.stage = LiveSessionStage.RECEIPT_ISSUED
            record.processed_request_ids.add(submission.request_id)
            return _deep_copy(receipt)

    def get_receipt(self, session_id: str) -> LiveClarityReceipt:
        with self._lock:
            record = self._record(session_id)
            if record.receipt is None:
                raise WorkflowFailure(
                    WorkflowErrorCode.RECEIPT_NOT_READY,
                    "A clarity receipt has not been issued for this session.",
                    status_code=409,
                    current_agreement_version_id=record.current_version_id,
                )
            return _deep_copy(record.receipt)

    def confirmation_status(self, session_id: str) -> ConfirmationStatusView:
        with self._lock:
            record = self._record(session_id)
            confirmations = (
                self._current_confirmations(record, record.current_version_id)
                if record.current_version_id
                else []
            )
            return ConfirmationStatusView(
                session_id=record.id,
                stage=record.stage,
                current_agreement_version_id=record.current_version_id,
                confirmations=[_deep_copy(item) for item in confirmations],
                receipt_ready=(
                    len(confirmations) == 2
                    and record.stage
                    in {
                        LiveSessionStage.CONFIRMED,
                        LiveSessionStage.RECEIPT_ISSUED,
                    }
                ),
            )

    def _record(self, session_id: str) -> _LiveSessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise WorkflowFailure(
                WorkflowErrorCode.SESSION_NOT_FOUND,
                "Live session not found. It may have expired because storage "
                "is in memory.",
                status_code=404,
            )
        return record

    def _view(self, record: _LiveSessionRecord) -> LiveSessionView:
        current_confirmations = (
            self._current_confirmations(record, record.current_version_id)
            if record.current_version_id
            else []
        )
        return LiveSessionView(
            id=record.id,
            stage=record.stage,
            created_at=record.created_at,
            participants=[_deep_copy(item) for item in record.participants],
            messages=[_deep_copy(item) for item in record.messages],
            agreement_versions=[_deep_copy(item) for item in record.versions],
            current_agreement_version_id=record.current_version_id,
            clarifications=[_deep_copy(item) for item in record.clarifications],
            reviews={role: _deep_copy(item) for role, item in record.reviews.items()},
            active_participant_id=record.active_participant_id,
            teachbacks=[_deep_copy(item) for item in record.teachbacks],
            confirmations=[_deep_copy(item) for item in record.confirmations],
            receipt_id=record.receipt.id if record.receipt else None,
            receipt_ready=(
                record.stage
                in {LiveSessionStage.CONFIRMED, LiveSessionStage.RECEIPT_ISSUED}
                and len(current_confirmations) == 2
            ),
            clarification_attempt_limit=self._clarification_attempt_limit,
            guidance=self._guidance(record),
        )

    def _guidance(self, record: _LiveSessionRecord) -> LiveWorkflowGuidance:
        version = self._current_version(record)
        mutual = (
            self._mutually_not_applicable(version.not_applicable_proposals)
            if version
            else set()
        )
        required_keys = (
            self._outstanding_required_item_keys(record, version) if version else []
        )
        optional_keys = optional_item_keys(version.terms, mutual) if version else []
        active = self._active_clarification(record)
        common = {
            "required_issue_count": len(required_keys),
            "optional_missing_count": len(optional_keys),
            "acting_participant": record.active_participant_id,
            "active_clarification_id": active.id if active else None,
            "target_item_key": active.target_item_key if active else None,
            "required_item_keys": required_keys,
            "optional_item_keys": optional_keys,
        }

        if record.stage in {
            LiveSessionStage.CONVERSATION_DRAFT,
            LiveSessionStage.ANALYZING,
        }:
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CONVERSATION,
                headline="Building the agreement map",
                explanation=("MeaningSync is comparing the two stated understandings."),
                primary_action=LiveGuidanceAction.REVIEW_FINAL_UNDERSTANDING,
                primary_label="Preparing agreement map",
                **common,
            )
        if active is not None:
            if active.status == ClarificationWorkflowStatus.STILL_UNRESOLVED:
                attempts = sum(
                    item.semantic_target == active.semantic_target
                    for item in record.clarifications
                )
                if attempts >= self._clarification_attempt_limit:
                    return LiveWorkflowGuidance(
                        user_stage=LiveUserStage.CLARIFY,
                        headline="This point is still different",
                        explanation=(
                            "The clarification limit was reached. Keep this point "
                            "explicitly unresolved to continue."
                        ),
                        primary_action=LiveGuidanceAction.LEAVE_UNRESOLVED,
                        primary_label="Leave this unresolved",
                        **common,
                    )
                return LiveWorkflowGuidance(
                    user_stage=LiveUserStage.CLARIFY,
                    headline="This point is still different",
                    explanation=(
                        "Try one more neutral clarification, or keep this point "
                        "explicitly unresolved."
                    ),
                    primary_action=LiveGuidanceAction.ANSWER_CLARIFICATION,
                    primary_label="Try one more clarification",
                    secondary_action=LiveGuidanceAction.LEAVE_UNRESOLVED,
                    secondary_label="Leave this unresolved",
                    **common,
                )
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CLARIFY,
                headline="Clarify one required meaning",
                explanation=(
                    "Answer this exact item, or leave it explicitly unresolved."
                ),
                primary_action=LiveGuidanceAction.ANSWER_CLARIFICATION,
                primary_label="Answer 1 question",
                secondary_action=LiveGuidanceAction.LEAVE_UNRESOLVED,
                secondary_label="Leave this unresolved",
                **common,
            )
        if record.stage in {
            LiveSessionStage.NEEDS_CLARIFICATION,
            LiveSessionStage.READY_FOR_REVIEW,
        }:
            if optional_keys and not record.optional_details_reviewed:
                return LiveWorkflowGuidance(
                    user_stage=LiveUserStage.REVIEW,
                    headline="Review the final recorded understanding",
                    explanation=(
                        "Optional details were not discussed. Continue with them "
                        "open, or add any that matter before final review."
                    ),
                    primary_action=LiveGuidanceAction.REVIEW_FINAL_UNDERSTANDING,
                    primary_label="Review final understanding",
                    secondary_action=LiveGuidanceAction.REVIEW_OPTIONAL_DETAILS,
                    secondary_label="Add optional details",
                    **common,
                )
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.REVIEW,
                headline="Review the final recorded understanding",
                explanation=(
                    "Both participants will review this exact version separately."
                ),
                primary_action=LiveGuidanceAction.REVIEW_FINAL_UNDERSTANDING,
                primary_label="Review final understanding",
                **common,
            )
        if record.stage == LiveSessionStage.AWAITING_TEACHBACKS:
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.REVIEW,
                headline="Explain the agreement in your own words",
                explanation=(
                    "Complete the private teach-back for the acting participant."
                ),
                primary_action=LiveGuidanceAction.SUBMIT_TEACHBACK,
                primary_label="Continue teach-back",
                **common,
            )
        if record.stage == LiveSessionStage.AWAITING_CONFIRMATIONS:
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CONFIRM,
                headline="Confirm each understanding separately",
                explanation=(
                    "The acting participant confirms this exact agreement version."
                ),
                primary_action=LiveGuidanceAction.SUBMIT_CONFIRMATION,
                primary_label="Review my confirmation",
                **common,
            )
        if record.stage == LiveSessionStage.CONFIRMED:
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CONFIRM,
                headline="Both understandings are confirmed",
                explanation="The immutable clarity receipt can now be issued.",
                primary_action=LiveGuidanceAction.ISSUE_RECEIPT,
                primary_label="Issue clarity receipt",
                **common,
            )
        return LiveWorkflowGuidance(
            user_stage=LiveUserStage.RECEIPT,
            headline="The clarity receipt is ready",
            explanation=(
                "Review the aligned and explicitly unresolved meaning recorded."
            ),
            primary_action=LiveGuidanceAction.VIEW_RECEIPT,
            primary_label="View clarity receipt",
            **common,
        )

    def _active_clarification(
        self, record: _LiveSessionRecord
    ) -> ClarificationWorkflowRecord | None:
        return next(
            (
                item
                for item in reversed(record.clarifications)
                if (
                    item.target_agreement_version_id == record.current_version_id
                    and item.status
                    in {
                        ClarificationWorkflowStatus.PENDING,
                        ClarificationWorkflowStatus.ANSWERED,
                    }
                )
                or (
                    item.resulting_agreement_version_id == record.current_version_id
                    and item.status == ClarificationWorkflowStatus.STILL_UNRESOLVED
                )
            ),
            None,
        )

    def _outstanding_required_item_keys(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
    ) -> list[str]:
        active = self._active_clarification(record)
        outstanding = [active.target_item_key] if active is not None else []
        active_target = active.semantic_target if active is not None else None

        for term in ordered_clarification_candidates(version.terms):
            target = semantic_target(term)
            if target == active_target:
                continue
            if any(
                item.semantic_target == target
                and item.status == ClarificationWorkflowStatus.LEFT_UNRESOLVED
                for item in record.clarifications
            ):
                continue
            fingerprint = clarification_fingerprint(term, version.terms)
            if any(item.fingerprint == fingerprint for item in record.clarifications):
                continue
            attempts = sum(
                item.semantic_target == target for item in record.clarifications
            )
            if attempts >= self._clarification_attempt_limit:
                continue
            outstanding.append(term.analysis_item_key)
        return outstanding

    @staticmethod
    def _mutually_not_applicable(
        proposals: list[NotApplicableProposal],
    ) -> set[str]:
        all_roles = set(PartyRole)
        return {
            item.item_key for item in proposals if set(item.proposed_by) == all_roles
        }

    def _analysis_request(
        self,
        record: _LiveSessionRecord,
        messages: list[AnalysisMessage],
        *,
        additional_contexts: list[AnalysisClarificationContext] | None = None,
    ) -> AgreementAnalysisRequest:
        message_ids = {message.message_id for message in messages}
        contexts = [
            AnalysisClarificationContext(
                clarification_id=item.id,
                target_item_key=item.target_item_key,
                question=item.question,
                response_message_ids=item.response_message_ids,
            )
            for item in record.clarifications
            if item.response_message_ids
            and set(item.response_message_ids.values()).issubset(message_ids)
        ]
        contexts.extend(additional_contexts or [])
        return AgreementAnalysisRequest(
            session_id=record.id,
            mode=SessionMode.LIVE,
            participants=record.participants,
            messages=messages,
            clarification_contexts=contexts,
        )

    def _apply_analysis(
        self, record: _LiveSessionRecord, response: AgreementAnalysisResponse
    ) -> AgreementVersion:
        version = self._build_version(record, response)
        self._commit_version(record, version)
        self._select_next_stage(record)
        return version

    def _build_version(
        self, record: _LiveSessionRecord, response: AgreementAnalysisResponse
    ) -> AgreementVersion:
        if response.session_id != record.id or response.mode != SessionMode.LIVE:
            raise ValueError("analyzer returned a result for another session")
        parent = self._current_version(record)
        terms = [self._with_evidence_provenance(item) for item in response.terms]
        not_discussed_keys = {
            item.analysis_item_key
            for item in terms
            if item.state == MeaningState.NOT_DISCUSSED
        }
        proposals = (
            [
                item
                for item in parent.not_applicable_proposals
                if item.item_key in not_discussed_keys
            ]
            if parent
            else []
        )
        mutual = self._mutually_not_applicable(proposals)
        semantic_fingerprint = agreement_semantic_fingerprint(terms, mutual)
        meaningful = (
            parent is None or semantic_fingerprint != parent.semantic_fingerprint
        )
        unresolved = [
            item.analysis_item_key
            for item in terms
            if item.state != MeaningState.ALIGNED
            and item.analysis_item_key not in mutual
        ]
        changes = self._changes(parent, terms) if parent else []
        return AgreementVersion(
            id=_id("agreement"),
            version_number=len(record.versions) + 1,
            meaningful_version_number=(
                1
                if parent is None
                else parent.meaningful_version_number + (1 if meaningful else 0)
            ),
            has_meaningful_change=meaningful,
            semantic_fingerprint=semantic_fingerprint,
            parent_version_id=parent.id if parent else None,
            session_id=record.id,
            created_at=_now(),
            source_message_ids=[item.message_id for item in record.messages],
            terms=terms,
            unresolved_item_keys=unresolved,
            not_applicable_proposals=proposals,
            prompt_version=response.prompt_version,
            model=response.model,
            analysis_status=response.status,
            warnings=response.warnings,
            primary_clarification=response.primary_clarification,
            changes=changes,
        )

    def _with_evidence_provenance(self, term: AgreementTerm) -> AgreementTerm:
        return term.model_copy(
            update={
                "evidence": [
                    item.model_copy(update={"source": "clarification"})
                    if item.message_id is not None
                    and item.message_id.startswith("clarification-")
                    else _deep_copy(item)
                    for item in term.evidence
                ]
            },
            deep=True,
        )

    def _commit_version(
        self, record: _LiveSessionRecord, version: AgreementVersion
    ) -> None:
        record.versions.append(_deep_copy(version))
        record.current_version_id = version.id
        record.optional_details_reviewed = False
        self._invalidate_confirmations(record, version.id)

    def _select_next_stage(self, record: _LiveSessionRecord) -> None:
        version = self._current_version(record)
        if version is None:
            record.stage = LiveSessionStage.CONVERSATION_DRAFT
            record.active_participant_id = None
            return
        active = self._active_clarification(record)
        if active is not None:
            record.stage = LiveSessionStage.NEEDS_CLARIFICATION
            record.active_participant_id = self._next_clarification_actor(
                record, active
            )
            return

        provider_question = version.primary_clarification
        for term in ordered_clarification_candidates(version.terms):
            fingerprint = clarification_fingerprint(term, version.terms)
            target = semantic_target(term)
            if any(
                item.semantic_target == target
                and item.status == ClarificationWorkflowStatus.LEFT_UNRESOLVED
                for item in record.clarifications
            ):
                continue
            if any(item.fingerprint == fingerprint for item in record.clarifications):
                continue
            attempts = sum(
                item.semantic_target == target for item in record.clarifications
            )
            if attempts >= self._clarification_attempt_limit:
                continue

            question, answer_options = neutral_question_and_options(term)
            if (
                provider_question is not None
                and provider_question.target_item_key == term.analysis_item_key
            ):
                question = provider_question.prompt
                if provider_question.options:
                    answer_options = list(provider_question.options)
            addressed = addressed_participants(term)
            if not addressed:
                continue
            clarification = ClarificationWorkflowRecord(
                id=_id("clarification"),
                target_item_key=term.analysis_item_key,
                target_agreement_version_id=version.id,
                term_id=term.id,
                question=question,
                answer_options=answer_options,
                fingerprint=fingerprint,
                semantic_target=target,
                addressed_participant_ids=addressed,
                status=ClarificationWorkflowStatus.PENDING,
                attempt_number=attempts + 1,
                created_at=_now(),
            )
            record.clarifications.append(clarification)
            record.stage = LiveSessionStage.NEEDS_CLARIFICATION
            record.active_participant_id = addressed[0]
            return

        record.stage = LiveSessionStage.READY_FOR_REVIEW
        record.active_participant_id = None

    def _changes(
        self, parent: AgreementVersion, current_terms: list[AgreementTerm]
    ) -> list[AgreementVersionChange]:
        previous = {item.analysis_item_key: item for item in parent.terms}
        current = {item.analysis_item_key: item for item in current_terms}
        changes: list[AgreementVersionChange] = []
        for term in current_terms:
            old = previous.get(term.analysis_item_key)
            if old is not None and agreement_semantic_fingerprint(
                [old]
            ) == agreement_semantic_fingerprint([term]):
                continue
            changes.append(
                AgreementVersionChange(
                    item_key=term.analysis_item_key,
                    label=term.label,
                    previous_state=old.state if old else None,
                    current_state=term.state,
                    resulting_meaning=term.summary,
                    new_evidence_reference_ids=[
                        item
                        for item in sorted(set(term.evidence_message_ids))
                        if old is None or item not in set(old.evidence_message_ids)
                    ],
                )
            )
        for item_key in sorted(set(previous) - set(current)):
            old = previous[item_key]
            changes.append(
                AgreementVersionChange(
                    item_key=item_key,
                    label=old.label,
                    previous_state=old.state,
                    current_state=None,
                    resulting_meaning="This item is no longer present in the analysis.",
                )
            )
        return changes

    def _clarification_messages(
        self,
        record: _LiveSessionRecord,
        clarification: ClarificationWorkflowRecord,
        answers: dict[PartyRole, str],
    ) -> list[AnalysisMessage]:
        if len(record.messages) + len(answers) > 40:
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_STATE,
                "This in-memory session has reached the statement limit.",
                status_code=422,
                current_agreement_version_id=record.current_version_id,
            )
        timestamp = _now()
        start = max(item.order for item in record.messages) + 1
        return [
            AnalysisMessage(
                message_id=_id(f"clarification-{clarification.attempt_number}"),
                speaker_id=role.value,
                original_text=answers[role],
                original_language=next(
                    participant.language
                    for participant in record.participants
                    if participant.role == role
                ),
                order=start + offset,
                timestamp=timestamp,
            )
            for offset, role in enumerate(clarification.addressed_participant_ids)
        ]

    def _validated_appended_messages(
        self, record: _LiveSessionRecord, messages: list[AnalysisMessage]
    ) -> list[AnalysisMessage]:
        if len(record.messages) + len(messages) > 40:
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_STATE,
                "This in-memory session has reached the statement limit.",
                status_code=422,
                current_agreement_version_id=record.current_version_id,
            )
        existing_ids = {item.message_id for item in record.messages}
        expected_order = max(item.order for item in record.messages) + 1
        for offset, message in enumerate(messages):
            if (
                message.message_id in existing_ids
                or message.order != expected_order + offset
            ):
                raise WorkflowFailure(
                    WorkflowErrorCode.INVALID_STATE,
                    "New statements need unique IDs and the next chronological order.",
                    status_code=422,
                    current_agreement_version_id=record.current_version_id,
                )
        self._analysis_request(record, [*record.messages, *messages])
        return [_deep_copy(item) for item in messages]

    def _clarification(
        self, record: _LiveSessionRecord, clarification_id: str
    ) -> ClarificationWorkflowRecord:
        clarification = next(
            (item for item in record.clarifications if item.id == clarification_id),
            None,
        )
        if clarification is None:
            raise WorkflowFailure(
                WorkflowErrorCode.CLARIFICATION_TARGET_MISSING,
                "Clarification not found for this session.",
                status_code=404,
                current_agreement_version_id=record.current_version_id,
            )
        applies_to_current_version = (
            clarification.target_agreement_version_id == record.current_version_id
            or (
                clarification.status == ClarificationWorkflowStatus.STILL_UNRESOLVED
                and clarification.resulting_agreement_version_id
                == record.current_version_id
            )
        )
        if not applies_to_current_version:
            raise self._stale(record)
        return clarification

    def _replace_clarification(
        self, record: _LiveSessionRecord, updated: ClarificationWorkflowRecord
    ) -> None:
        index = next(
            index
            for index, item in enumerate(record.clarifications)
            if item.id == updated.id
        )
        record.clarifications[index] = updated

    def _close_pending_clarifications(
        self,
        record: _LiveSessionRecord,
        resulting_version: AgreementVersion,
    ) -> None:
        term_by_key = {item.analysis_item_key: item for item in resulting_version.terms}
        closed_at = _now()
        record.clarifications = [
            item.model_copy(
                update={
                    "status": (
                        ClarificationWorkflowStatus.RESOLVED
                        if term_by_key.get(item.target_item_key) is not None
                        and term_by_key[item.target_item_key].state
                        == MeaningState.ALIGNED
                        else ClarificationWorkflowStatus.STILL_UNRESOLVED
                    ),
                    "resolved_at": closed_at,
                    "resulting_agreement_version_id": resulting_version.id,
                }
            )
            if item.status
            in {
                ClarificationWorkflowStatus.PENDING,
                ClarificationWorkflowStatus.ANSWERED,
            }
            else item
            for item in record.clarifications
        ]
        record.pending_answers = {
            clarification_id: answers
            for clarification_id, answers in record.pending_answers.items()
            if any(
                item.id == clarification_id
                and item.status
                in {
                    ClarificationWorkflowStatus.PENDING,
                    ClarificationWorkflowStatus.ANSWERED,
                }
                for item in record.clarifications
            )
        }

    def _next_clarification_actor(
        self, record: _LiveSessionRecord, clarification: ClarificationWorkflowRecord
    ) -> PartyRole:
        answers = record.pending_answers.get(clarification.id, {})
        return next(
            role
            for role in clarification.addressed_participant_ids
            if role not in answers
        )

    def _current_version(self, record: _LiveSessionRecord) -> AgreementVersion | None:
        return next(
            (
                item
                for item in reversed(record.versions)
                if item.id == record.current_version_id
            ),
            None,
        )

    def _require_current_version(
        self, record: _LiveSessionRecord, expected: str | None
    ) -> AgreementVersion:
        version = self._current_version(record)
        if version is None or expected != version.id:
            raise self._stale(record)
        return version

    def _stale(self, record: _LiveSessionRecord) -> WorkflowFailure:
        return WorkflowFailure(
            WorkflowErrorCode.STALE_AGREEMENT_VERSION,
            "The agreement changed. Refresh before continuing.",
            status_code=409,
            current_agreement_version_id=record.current_version_id,
        )

    def _invalid_state(
        self, record: _LiveSessionRecord, message: str
    ) -> WorkflowFailure:
        return WorkflowFailure(
            WorkflowErrorCode.INVALID_STATE,
            message,
            status_code=409,
            current_agreement_version_id=record.current_version_id,
        )

    def _require_stage(
        self, record: _LiveSessionRecord, stage: LiveSessionStage
    ) -> None:
        if record.stage != stage:
            raise self._invalid_state(
                record, f"This action is not available during {record.stage.value}."
            )

    def _require_modifiable(self, record: _LiveSessionRecord) -> None:
        if record.stage not in {
            LiveSessionStage.NEEDS_CLARIFICATION,
            LiveSessionStage.READY_FOR_REVIEW,
            LiveSessionStage.AWAITING_TEACHBACKS,
            LiveSessionStage.AWAITING_CONFIRMATIONS,
            LiveSessionStage.CONFIRMED,
        }:
            raise self._invalid_state(record, "The agreement cannot be changed now.")

    def _require_actor(
        self, record: _LiveSessionRecord, participant: PartyRole
    ) -> None:
        if record.active_participant_id != participant:
            raise self._participant_mismatch(record.active_participant_id)

    def _participant_mismatch(self, expected: PartyRole | None) -> WorkflowFailure:
        name = expected.value if expected else "the active participant"
        return WorkflowFailure(
            WorkflowErrorCode.PARTICIPANT_MISMATCH,
            f"Pass the device to {name} before continuing.",
            status_code=409,
        )

    def _require_acknowledgments(
        self, version: AgreementVersion, acknowledgments: list[str]
    ) -> None:
        required = self._acknowledgment_item_keys(version)
        if set(acknowledgments) != set(required) or len(acknowledgments) != len(
            set(acknowledgments)
        ):
            raise WorkflowFailure(
                WorkflowErrorCode.TEACHBACK_INCOMPLETE,
                "Acknowledge every conflicting or one-sided item in this version.",
                status_code=422,
                current_agreement_version_id=version.id,
            )

    @staticmethod
    def _acknowledgment_item_keys(version: AgreementVersion) -> list[str]:
        return [
            item.analysis_item_key
            for item in version.terms
            if item.analysis_item_key in version.unresolved_item_keys
            and item.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
        ]

    def _term(self, version: AgreementVersion, item_key: str) -> AgreementTerm:
        term = next(
            (item for item in version.terms if item.analysis_item_key == item_key), None
        )
        if term is None:
            raise WorkflowFailure(
                WorkflowErrorCode.CLARIFICATION_TARGET_MISSING,
                "The selected item is not part of this agreement version.",
                status_code=422,
                current_agreement_version_id=version.id,
            )
        return term

    def _required_teachback_items(self, version: AgreementVersion) -> list[str]:
        preferred = {
            "scope.work",
            "price.amount",
            "materials.inclusion",
            "timing.start",
            "payment.timing",
        }
        critical = [
            item.analysis_item_key
            for item in version.terms
            if item.analysis_item_key in preferred
            and item.state != MeaningState.NOT_DISCUSSED
        ]
        discussed_unresolved = [
            item.analysis_item_key
            for item in version.terms
            if item.analysis_item_key in version.unresolved_item_keys
            and item.state != MeaningState.NOT_DISCUSSED
        ]
        return list(dict.fromkeys([*critical, *discussed_unresolved]))

    def _reopen_for_change(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        item_key: str,
        question: str,
    ) -> None:
        term = self._term(version, item_key)
        target = semantic_target(term)
        attempts = sum(item.semantic_target == target for item in record.clarifications)
        # A deliberate teach-back contradiction or confirmation change request
        # must never disappear merely because this item exhausted its earlier
        # automatic clarification budget. Allow exactly this user-driven reopen;
        # if re-analysis still cannot align it, guidance permits only an explicit
        # unresolved decision once the configured budget has been reached.
        record.clarifications.append(
            ClarificationWorkflowRecord(
                id=_id("clarification"),
                target_item_key=item_key,
                target_agreement_version_id=version.id,
                term_id=term.id,
                question=question,
                answer_options=[],
                fingerprint=clarification_fingerprint(term, version.terms),
                semantic_target=target,
                addressed_participant_ids=[PartyRole.HIRER, PartyRole.WORKER],
                status=ClarificationWorkflowStatus.PENDING,
                attempt_number=min(attempts + 1, 20),
                created_at=_now(),
            )
        )
        self._invalidate_all_confirmations(record)
        self._invalidate_review(record)
        record.stage = LiveSessionStage.NEEDS_CLARIFICATION
        record.active_participant_id = PartyRole.HIRER

    def _invalidate_review(self, record: _LiveSessionRecord) -> None:
        record.reviews = {}
        record.active_participant_id = None

    def _invalidate_confirmations(
        self, record: _LiveSessionRecord, current_version_id: str
    ) -> None:
        invalidated_at = _now()
        record.confirmations = [
            item.model_copy(update={"invalidated_at": invalidated_at})
            if item.agreement_version_id != current_version_id
            and item.invalidated_at is None
            else item
            for item in record.confirmations
        ]

    def _invalidate_all_confirmations(self, record: _LiveSessionRecord) -> None:
        invalidated_at = _now()
        record.confirmations = [
            item.model_copy(update={"invalidated_at": invalidated_at})
            if item.invalidated_at is None
            else item
            for item in record.confirmations
        ]

    def _current_confirmations(
        self, record: _LiveSessionRecord, version_id: str | None
    ) -> list[ConfirmationRecord]:
        return [
            item
            for item in record.confirmations
            if item.agreement_version_id == version_id and item.invalidated_at is None
        ]

    def _receipt_payload(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        confirmations: list[ConfirmationRecord],
        teachbacks: list[TeachbackRecord],
        issued_at: datetime,
    ) -> dict:
        mutually_not_applicable = self._mutually_not_applicable(
            version.not_applicable_proposals
        )
        aligned = [item for item in version.terms if item.state == MeaningState.ALIGNED]
        conflicting = [
            item for item in version.terms if item.state == MeaningState.CONFLICTING
        ]
        one_sided = [
            item for item in version.terms if item.state == MeaningState.STATED_BY_ONE
        ]
        not_discussed = [
            item
            for item in version.terms
            if item.state == MeaningState.NOT_DISCUSSED
            and item.analysis_item_key not in mutually_not_applicable
        ]
        return {
            "id": _id("receipt"),
            "session_id": record.id,
            "agreement_version_id": version.id,
            "agreement_version_number": version.meaningful_version_number,
            "issued_at": issued_at,
            "participants": [
                ReceiptParticipant(
                    participant_id=item.role,
                    role=item.role,
                    display_name=(
                        "Homeowner" if item.role == PartyRole.HIRER else "Electrician"
                    ),
                    language=item.language,
                )
                for item in record.participants
            ],
            "aligned_terms": aligned,
            "unresolved_terms": conflicting,
            "one_sided_terms": one_sided,
            "not_applicable_terms": version.not_applicable_proposals,
            "not_discussed_terms": not_discussed,
            "clarification_history": [
                ClarificationHistoryEntry(
                    clarification_id=item.id,
                    target_item_key=item.target_item_key,
                    target_agreement_version_id=item.target_agreement_version_id,
                    resulting_agreement_version_id=item.resulting_agreement_version_id,
                    status=item.status,
                    response_message_ids=item.response_message_ids,
                    fingerprint=item.fingerprint,
                    semantic_target=item.semantic_target,
                )
                for item in record.clarifications
            ],
            "teachback_status": [
                ReceiptTeachbackStatus(
                    participant_id=item.participant_id,
                    teachback_id=item.id,
                    result=item.overall_state,
                    completed_at=item.created_at,
                )
                for item in teachbacks
            ],
            "confirmations": [
                ReceiptConfirmation(
                    participant_id=item.participant_id,
                    confirmation_id=item.id,
                    confirmed_at=item.confirmed_at,
                    language=item.language,
                )
                for item in confirmations
            ],
            "status": (
                ReceiptStatus.CONTAINS_UNRESOLVED_ITEMS
                if version.unresolved_item_keys
                else ReceiptStatus.FULLY_ALIGNED
            ),
        }
