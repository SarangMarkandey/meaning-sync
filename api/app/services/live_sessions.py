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
    normalize_meaning_text,
    optional_item_keys,
    ordered_clarification_candidates,
    semantic_target,
)
from app.domain.understanding_choices import (
    MAX_UNDERSTANDING_QUESTIONS,
    build_question_definition,
    select_understanding_terms,
    semantic_meaning_fingerprint,
)
from app.schemas.analysis import (
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AgreementTerm,
    AnalysisClarificationContext,
    AnalysisMessage,
    AnalysisStatus,
    EvidenceReference,
    MeaningState,
    ParticipantPosition,
    ParticipantTermStatus,
    PartyRole,
    SessionMode,
)
from app.schemas.understanding import (
    IndependentMeaningEvidence,
    LeaveQuestionUnresolvedSubmission,
    ParticipantSelection,
    UnderstandingEvidenceSource,
    UnderstandingOptionKind,
    UnderstandingOutcomePosition,
    UnderstandingOutcomeState,
    UnderstandingQuestion,
    UnderstandingQuestionKind,
    UnderstandingQuestionOutcome,
    UnderstandingQuestionStatus,
    UnderstandingReviewResult,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AgreementVersion,
    AgreementVersionChange,
    AnalyzeLiveSessionSubmission,
    ClarificationHistoryEntry,
    ClarificationWorkflowStatus,
    ConfirmationDecision,
    ConfirmationRecord,
    ConfirmationStatusView,
    ConfirmationSubmission,
    IssueReceiptSubmission,
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
    ParticipantReviewStatus,
    ParticipantUnderstandingReview,
    ReceiptConfirmation,
    ReceiptParticipant,
    ReceiptStatus,
    ReceiptUnderstandingStatus,
    StartUnderstandingCheckSubmission,
    WorkflowErrorCode,
)
from app.services.analyzers import AgreementAnalyzer


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
class _QuestionRecord:
    question: UnderstandingQuestion
    semantic_target: str
    semantic_fingerprint: str
    option_semantics: dict[str, str]
    selections: dict[PartyRole, ParticipantSelection] = field(default_factory=dict)
    unresolved_acknowledgments: set[PartyRole] = field(default_factory=set)
    response_message_ids: dict[PartyRole, str] = field(default_factory=dict)
    attempt_number: int = 1


@dataclass
class _LiveSessionRecord:
    id: str
    created_at: datetime
    participants: list
    messages: list[AnalysisMessage]
    stage: LiveSessionStage = LiveSessionStage.CONVERSATION_DRAFT
    versions: list[AgreementVersion] = field(default_factory=list)
    current_version_id: str | None = None
    questions: list[_QuestionRecord] = field(default_factory=list)
    understanding_reviews: dict[PartyRole, ParticipantUnderstandingReview] = field(
        default_factory=dict
    )
    active_participant_id: PartyRole | None = None
    confirmations: list[ConfirmationRecord] = field(default_factory=list)
    evidence_ledger: list[IndependentMeaningEvidence] = field(default_factory=list)
    receipt: LiveClarityReceipt | None = None
    processed_requests: dict[str, str] = field(default_factory=dict)
    optional_details_reviewed: bool = False


class LiveSessionService:
    """Server-owned, in-memory lifecycle for Live agreement sessions."""

    def __init__(
        self,
        *,
        analyzer: AgreementAnalyzer,
        clarification_attempt_limit: int = 3,
    ) -> None:
        if clarification_attempt_limit < 1:
            raise ValueError("clarification attempt limit must be positive")
        self._analyzer = analyzer
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
            version = self._build_analysis_version(record, response)
            self._commit_version(record, version)
            self._record_conversation_evidence(record, version)
            self._select_next_stage(record)
            return self._view(record)

    def submit_selection(
        self,
        session_id: str,
        question_id: str,
        submission: UnderstandingSelectionSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("selection", question_id, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            question = self._question(record, question_id)
            self._require_question_stage(record, question)
            self._require_actor(record, submission.participant_id)
            if (
                submission.participant_id
                not in question.question.addressed_participant_ids
            ):
                raise self._participant_mismatch(record.active_participant_id)
            if question.question.status not in {
                UnderstandingQuestionStatus.PENDING,
                UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
            }:
                raise WorkflowFailure(
                    WorkflowErrorCode.QUESTION_INCOMPLETE,
                    "This question is not accepting another choice.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            option = next(
                (
                    item
                    for item in question.question.options
                    if item.id == submission.option_id
                ),
                None,
            )
            if option is None:
                raise WorkflowFailure(
                    WorkflowErrorCode.INVALID_OPTION,
                    "That choice does not belong to this question.",
                    status_code=422,
                    current_agreement_version_id=version.id,
                )
            if option.kind == UnderstandingOptionKind.OTHER:
                if submission.other_text is None:
                    raise WorkflowFailure(
                        WorkflowErrorCode.INVALID_OPTION,
                        "Add a short explanation after choosing Something else.",
                        status_code=422,
                        current_agreement_version_id=version.id,
                    )
                normalized_other = normalize_meaning_text(submission.other_text)
                if sum(character.isalnum() for character in normalized_other) < 2:
                    raise WorkflowFailure(
                        WorkflowErrorCode.INVALID_OPTION,
                        "Add at least two letters or numbers after choosing "
                        "Something else.",
                        status_code=422,
                        current_agreement_version_id=version.id,
                    )
                semantic_value = submission.other_text
            else:
                if submission.other_text is not None:
                    raise WorkflowFailure(
                        WorkflowErrorCode.INVALID_OPTION,
                        "A written explanation is accepted only for Something else.",
                        status_code=422,
                        current_agreement_version_id=version.id,
                    )
                semantic_value = question.option_semantics[option.id]
            selection = ParticipantSelection(
                id=_id("selection"),
                participant_id=submission.participant_id,
                question_id=question.question.id,
                agreement_version_id=version.id,
                option_id=option.id,
                option_kind=option.kind,
                semantic_value=semantic_value,
                other_text=submission.other_text,
                submitted_at=_now(),
                request_id=submission.request_id,
            )
            snapshot = _deep_copy(record)
            question.selections[submission.participant_id] = selection
            answered = list(question.selections)
            if len(answered) < len(question.question.addressed_participant_ids):
                question.question = question.question.model_copy(
                    update={
                        "answered_participant_ids": answered,
                        "status": UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
                    }
                )
                record.active_participant_id = next(
                    role
                    for role in question.question.addressed_participant_ids
                    if role not in question.selections
                )
                self._mark_processed(record, submission.request_id, digest)
                return self._view(record)

            try:
                self._complete_question(record, version, question)
            except Exception:
                # Completion can derive an immutable version and append synthetic
                # evidence. Restore the entire session if any part fails so the
                # second private choice and its request ID are never half-stored.
                self._sessions[session_id] = snapshot
                raise
            self._mark_processed(record, submission.request_id, digest)
            return self._view(record)

    def leave_question_unresolved(
        self,
        session_id: str,
        question_id: str,
        submission: LeaveQuestionUnresolvedSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("leave-unresolved", question_id, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            question = self._question(record, question_id)
            if question.question.kind != UnderstandingQuestionKind.CLARIFICATION:
                raise self._invalid_state(
                    record, "Only an active clarification can be left unresolved."
                )
            if question.question.status not in {
                UnderstandingQuestionStatus.PENDING,
                UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
                UnderstandingQuestionStatus.NEEDS_CLARIFICATION,
                UnderstandingQuestionStatus.UNSURE,
            }:
                raise self._invalid_state(
                    record, "This question has already been closed."
                )
            self._require_stage(record, LiveSessionStage.NEEDS_CLARIFICATION)
            self._require_actor(record, submission.participant_id)
            snapshot = _deep_copy(record)
            question.unresolved_acknowledgments.add(submission.participant_id)
            if len(question.unresolved_acknowledgments) < len(PartyRole):
                record.active_participant_id = next(
                    role
                    for role in PartyRole
                    if role not in question.unresolved_acknowledgments
                )
                self._mark_processed(record, submission.request_id, digest)
                return self._view(record)

            try:
                current = version
                term = self._term(version, question.question.agreement_item_id)
                if term.state == MeaningState.ALIGNED:
                    current = self._derive_version_from_selections(
                        record,
                        version,
                        question,
                        aligned=False,
                        meaning=f"{term.label} remains explicitly unresolved.",
                    )
                question.question = question.question.model_copy(
                    update={
                        "answered_participant_ids": [],
                        "responses_revealed": True,
                        "status": UnderstandingQuestionStatus.LEFT_UNRESOLVED,
                        "outcome": UnderstandingQuestionOutcome(
                            state=UnderstandingOutcomeState.LEFT_UNRESOLVED,
                            positions=[],
                            resulting_agreement_version_id=(
                                current.id if current.id != version.id else None
                            ),
                        ),
                    }
                )
                record.active_participant_id = None
                self._record_question_evidence(record, current, question)
                self._select_next_stage(record)
            except Exception:
                # The final unresolved acknowledgment can derive a new version.
                # Roll back the acknowledgment and request ID together on failure.
                self._sessions[session_id] = snapshot
                raise
            self._mark_processed(record, submission.request_id, digest)
            return self._view(record)

    async def add_statements(
        self, session_id: str, submission: AdditionalStatementsSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("add-statements", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            self._require_modifiable(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            active = self._active_question(record)
            if active is not None and active.question.status == (
                UnderstandingQuestionStatus.PARTIALLY_ANSWERED
            ):
                raise self._invalid_state(
                    record, "Finish the private handoff before adding statements."
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
            new_version = self._build_analysis_version(record, response)
            self._commit_version(record, new_version)
            self._invalidate_review(record)
            self._mark_processed(record, submission.request_id, digest)
            self._record_conversation_evidence(record, new_version)
            self._select_next_stage(record)
            return self._view(record)

    def propose_not_applicable(
        self, session_id: str, submission: NotApplicableProposalSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("not-applicable", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            self._require_modifiable(record)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if self._active_question(record) is not None:
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
                self._mark_processed(record, submission.request_id, digest)
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
            self._commit_version(record, derived)
            self._invalidate_review(record)
            record.stage = LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
            self._mark_processed(record, submission.request_id, digest)
            return self._view(record)

    def mark_optional_details_reviewed(
        self,
        session_id: str,
        submission: OptionalDetailsReviewedSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("optional-reviewed", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if self._active_question(record) is not None:
                raise self._invalid_state(
                    record, "Finish or leave the current required clarification first."
                )
            if record.stage not in {
                LiveSessionStage.NEEDS_CLARIFICATION,
                LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK,
            }:
                raise self._invalid_state(
                    record, "Optional details cannot be reviewed during this step."
                )
            record.optional_details_reviewed = True
            record.stage = LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
            self._mark_processed(record, submission.request_id, digest)
            return self._view(record)

    def start_understanding_check(
        self,
        session_id: str,
        submission: StartUnderstandingCheckSubmission,
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("start-understanding", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            if record.stage not in {
                LiveSessionStage.NEEDS_CLARIFICATION,
                LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK,
            }:
                raise self._invalid_state(
                    record, "This agreement is not ready for an understanding check."
                )
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            if self._active_question(record) is not None:
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
                    record,
                    "Review the optional missing details before checking "
                    "understanding.",
                )
            self._require_acknowledgments(
                version, submission.acknowledged_unresolved_item_keys
            )
            existing_checks = [
                item
                for item in record.questions
                if item.question.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
            ]
            remaining = MAX_UNDERSTANDING_QUESTIONS - len(existing_checks)
            has_completed_clarification = self._has_current_completed_clarification(
                record, version
            )
            if has_completed_clarification:
                remaining = min(remaining, 1)
            excluded_meanings = self._independently_answered_meanings(record)
            candidates = select_understanding_terms(
                version.terms,
                excluded_meanings=excluded_meanings,
                max_questions=remaining,
            )
            completed_prior_ids = [
                item.question.id
                for item in existing_checks
                if item.question.status == UnderstandingQuestionStatus.COMPLETED
                and self._completed_check_is_current(record, version, item)
            ]
            created_at = _now()
            record.understanding_reviews = {
                role: ParticipantUnderstandingReview(
                    id=_id("review"),
                    participant_id=role,
                    agreement_version_id=version.id,
                    status=(
                        ParticipantReviewStatus.CHECKING
                        if candidates and role == PartyRole.HIRER
                        else (
                            ParticipantReviewStatus.NOT_STARTED
                            if candidates
                            else (
                                ParticipantReviewStatus.COMPLETED
                                if completed_prior_ids
                                else ParticipantReviewStatus.SKIPPED
                            )
                        )
                    ),
                    completed_question_ids=completed_prior_ids,
                    created_at=created_at,
                    completed_at=None if candidates else created_at,
                )
                for role in PartyRole
            }
            total_questions = len(existing_checks) + len(candidates)
            for index, term in enumerate(candidates, start=len(existing_checks) + 1):
                self._append_question(
                    record,
                    version,
                    term,
                    kind=UnderstandingQuestionKind.UNDERSTANDING_CHECK,
                    addressed=list(PartyRole),
                    question_number=index,
                    question_count=total_questions,
                )
            self._mark_processed(record, submission.request_id, digest)
            if not candidates:
                record.stage = LiveSessionStage.AWAITING_CONFIRMATIONS
                record.active_participant_id = PartyRole.HIRER
            else:
                record.stage = LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS
                record.active_participant_id = PartyRole.HIRER
            return self._view(record)

    def submit_confirmation(
        self, session_id: str, submission: ConfirmationSubmission
    ) -> LiveSessionView:
        with self._lock:
            record = self._record(session_id)
            digest = self._request_digest("confirmation", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                return self._view(record)
            self._require_stage(record, LiveSessionStage.AWAITING_CONFIRMATIONS)
            version = self._require_current_version(
                record, submission.expected_agreement_version_id
            )
            self._require_actor(record, submission.participant_id)
            review = record.understanding_reviews.get(submission.participant_id)
            if (
                review is None
                or review.id != submission.understanding_review_id
                or review.agreement_version_id != version.id
                or review.status
                not in {
                    ParticipantReviewStatus.COMPLETED,
                    ParticipantReviewStatus.SKIPPED,
                    ParticipantReviewStatus.READY_TO_CONFIRM,
                }
            ):
                raise WorkflowFailure(
                    WorkflowErrorCode.UNDERSTANDING_INCOMPLETE,
                    "Confirmation must use this participant's current "
                    "understanding review.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            if submission.decision == ConfirmationDecision.CONFIRM:
                self._require_acknowledgments(
                    version, submission.unresolved_item_acknowledgments
                )
            if submission.decision == ConfirmationDecision.REQUEST_CHANGE:
                term = self._term(version, submission.change_item_key or "")
                self._mark_processed(record, submission.request_id, digest)
                self._invalidate_all_confirmations(record)
                self._invalidate_review(record)
                self._append_question(
                    record,
                    version,
                    term,
                    kind=UnderstandingQuestionKind.CLARIFICATION,
                    addressed=list(PartyRole),
                )
                record.stage = LiveSessionStage.NEEDS_CLARIFICATION
                record.active_participant_id = PartyRole.HIRER
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
                record.confirmations.append(
                    ConfirmationRecord(
                        id=_id("confirmation"),
                        participant_id=submission.participant_id,
                        agreement_version_id=version.id,
                        understanding_review_id=review.id,
                        unresolved_item_acknowledgments=(
                            submission.unresolved_item_acknowledgments
                        ),
                        confirmed_at=_now(),
                        language=participant.language,
                        request_id=submission.request_id,
                    )
                )
                self._record_confirmation_evidence(record, version, submission)
            self._mark_processed(record, submission.request_id, digest)
            record.understanding_reviews[submission.participant_id] = review.model_copy(
                update={"status": ParticipantReviewStatus.CONFIRMED}
            )
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
            digest = self._request_digest("issue-receipt", None, submission)
            if self._is_replay(record, submission.request_id, digest):
                if record.receipt is None:
                    raise self._invalid_state(
                        record, "The receipt request is incomplete."
                    )
                return _deep_copy(record.receipt)
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
            reviews = [record.understanding_reviews.get(role) for role in PartyRole]
            if any(
                item is None
                or item.agreement_version_id != version.id
                or item.status != ParticipantReviewStatus.CONFIRMED
                for item in reviews
            ):
                raise WorkflowFailure(
                    WorkflowErrorCode.RECEIPT_NOT_READY,
                    "Both participants need a current understanding review.",
                    status_code=409,
                    current_agreement_version_id=version.id,
                )
            issued_at = _now()
            payload = self._receipt_payload(
                record,
                version,
                confirmations,
                [item for item in reviews if item is not None],
                issued_at,
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
            self._mark_processed(record, submission.request_id, digest)
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

    def _complete_question(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        question: _QuestionRecord,
    ) -> None:
        selections = [
            question.selections[role]
            for role in question.question.addressed_participant_ids
        ]
        positions = [
            UnderstandingOutcomePosition(
                participant_id=selection.participant_id,
                option_id=selection.option_id,
                label=next(
                    item.label
                    for item in question.question.options
                    if item.id == selection.option_id
                ),
                other_text=selection.other_text,
            )
            for selection in selections
        ]
        option_kinds = {selection.option_kind for selection in selections}
        normalized = {
            normalize_meaning_text(selection.semantic_value) for selection in selections
        }
        term = self._term(version, question.question.agreement_item_id)

        if UnderstandingOptionKind.UNSURE in option_kinds:
            question.question = question.question.model_copy(
                update={
                    "answered_participant_ids": list(question.selections),
                    "responses_revealed": True,
                    "status": UnderstandingQuestionStatus.UNSURE,
                    "outcome": UnderstandingQuestionOutcome(
                        state=UnderstandingOutcomeState.UNSURE,
                        positions=positions,
                    ),
                }
            )
            self._return_item_to_clarification(record, version, question, term)
            return

        one_sided_other = (
            len(question.question.addressed_participant_ids) == 1
            and UnderstandingOptionKind.OTHER in option_kinds
        )
        if len(normalized) != 1 or one_sided_other:
            changed = self._derive_version_from_selections(
                record,
                version,
                question,
                aligned=False,
                meaning=(f"The selected meanings for {term.label.lower()} differ."),
            )
            question.question = question.question.model_copy(
                update={
                    "answered_participant_ids": list(question.selections),
                    "responses_revealed": True,
                    "status": UnderstandingQuestionStatus.NEEDS_CLARIFICATION,
                    "outcome": UnderstandingQuestionOutcome(
                        state=UnderstandingOutcomeState.DIFFERENT,
                        positions=positions,
                        resulting_agreement_version_id=(
                            changed.id if changed.id != version.id else None
                        ),
                    ),
                }
            )
            self._record_question_evidence(record, changed, question)
            self._return_item_to_clarification(record, changed, question, term)
            return

        shared_meaning = selections[0].semantic_value
        matches_current = (
            term.state == MeaningState.ALIGNED
            and len(normalized) == 1
            and next(iter(normalized)) == normalize_meaning_text(term.summary)
        )
        changed = version
        if not matches_current:
            changed = self._derive_version_from_selections(
                record,
                version,
                question,
                aligned=True,
                meaning=shared_meaning,
            )
        outcome_state = (
            UnderstandingOutcomeState.ALIGNED
            if changed.id == version.id
            else UnderstandingOutcomeState.MEANING_CHANGED
        )
        question.question = question.question.model_copy(
            update={
                "answered_participant_ids": list(question.selections),
                "responses_revealed": True,
                "status": UnderstandingQuestionStatus.COMPLETED,
                "outcome": UnderstandingQuestionOutcome(
                    state=outcome_state,
                    positions=positions,
                    resulting_agreement_version_id=(
                        changed.id if changed.id != version.id else None
                    ),
                ),
            }
        )
        self._record_question_evidence(record, changed, question)
        if (
            question.question.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
            and changed.id != version.id
        ):
            self._invalidate_review(record)
            record.stage = LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
            record.active_participant_id = None
            return
        if question.question.kind == UnderstandingQuestionKind.CLARIFICATION:
            self._select_next_stage(record)
            return
        self._advance_understanding_checks(record, version)

    def _return_item_to_clarification(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        source_question: _QuestionRecord,
        old_term: AgreementTerm,
    ) -> None:
        current_term = self._term(version, old_term.analysis_item_key)
        attempts = (
            source_question.attempt_number
            if source_question.question.kind == UnderstandingQuestionKind.CLARIFICATION
            else 0
        )
        if attempts >= self._clarification_attempt_limit:
            if source_question.question.agreement_version_id != version.id:
                marker = self._append_question(
                    record,
                    version,
                    current_term,
                    kind=UnderstandingQuestionKind.CLARIFICATION,
                    addressed=list(PartyRole),
                    attempt_number=attempts,
                )
                marker.question = marker.question.model_copy(
                    update={"status": UnderstandingQuestionStatus.NEEDS_CLARIFICATION}
                )
            record.stage = LiveSessionStage.NEEDS_CLARIFICATION
            record.active_participant_id = PartyRole.HIRER
            return
        self._append_question(
            record,
            version,
            current_term,
            kind=UnderstandingQuestionKind.CLARIFICATION,
            addressed=list(PartyRole),
            attempt_number=attempts + 1,
        )
        if source_question.question.agreement_version_id != version.id:
            self._invalidate_review(record)
        record.stage = LiveSessionStage.NEEDS_CLARIFICATION
        record.active_participant_id = PartyRole.HIRER

    def _advance_understanding_checks(
        self, record: _LiveSessionRecord, version: AgreementVersion
    ) -> None:
        pending = [
            item
            for item in record.questions
            if item.question.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
            and item.question.agreement_version_id == version.id
            and item.question.status
            in {
                UnderstandingQuestionStatus.PENDING,
                UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
            }
        ]
        if pending:
            record.active_participant_id = PartyRole.HIRER
            return
        completed_ids = list(
            dict.fromkeys(
                [
                    question_id
                    for review in record.understanding_reviews.values()
                    for question_id in review.completed_question_ids
                ]
                + [
                    item.question.id
                    for item in record.questions
                    if item.question.kind
                    == UnderstandingQuestionKind.UNDERSTANDING_CHECK
                    and item.question.agreement_version_id == version.id
                    and item.question.status == UnderstandingQuestionStatus.COMPLETED
                ]
            )
        )
        completed_at = _now()
        record.understanding_reviews = {
            role: review.model_copy(
                update={
                    "status": ParticipantReviewStatus.COMPLETED,
                    "completed_question_ids": completed_ids,
                    "completed_at": completed_at,
                }
            )
            for role, review in record.understanding_reviews.items()
        }
        record.stage = LiveSessionStage.AWAITING_CONFIRMATIONS
        record.active_participant_id = PartyRole.HIRER

    def _derive_version_from_selections(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        question: _QuestionRecord,
        *,
        aligned: bool,
        meaning: str,
    ) -> AgreementVersion:
        messages = self._selection_messages(record, question)
        record.messages.extend(messages)
        question.response_message_ids = {
            PartyRole(message.speaker_id): message.message_id for message in messages
        }
        message_by_role = {
            PartyRole(message.speaker_id): message for message in messages
        }
        target_item_key = question.question.agreement_item_id
        terms: list[AgreementTerm] = []
        for term in version.terms:
            if term.analysis_item_key != target_item_key:
                terms.append(_deep_copy(term))
                continue
            new_evidence = [*term.evidence]
            new_evidence_ids = list(term.evidence_message_ids)
            for role, message in message_by_role.items():
                selection = question.selections[role]
                new_evidence.append(
                    EvidenceReference(
                        source=(
                            "clarification"
                            if question.question.kind
                            == UnderstandingQuestionKind.CLARIFICATION
                            else "understanding_check"
                        ),
                        reference_id=selection.id,
                        participant_id=role.value,
                        role=role,
                        speaker_name=(
                            "Homeowner" if role == PartyRole.HIRER else "Electrician"
                        ),
                        message_id=message.message_id,
                        original_text=message.original_text,
                        original_language=message.original_language,
                        order=message.order,
                        timestamp=message.timestamp,
                    )
                )
                new_evidence_ids.append(message.message_id)
            if aligned:
                positions = []
                existing_by_role = {
                    item.role: item for item in term.participant_positions
                }
                for role in PartyRole:
                    if role in message_by_role:
                        positions.append(
                            ParticipantPosition(
                                participant_id=role.value,
                                role=role,
                                summary=meaning,
                                evidence_message_ids=[message_by_role[role].message_id],
                            )
                        )
                    elif role in existing_by_role:
                        positions.append(existing_by_role[role])
                terms.append(
                    term.model_copy(
                        update={
                            "summary": meaning,
                            "state": MeaningState.ALIGNED,
                            "participant_positions": positions,
                            "participant_confirmations": {
                                role: ParticipantTermStatus.CONFIRMED
                                for role in PartyRole
                            },
                            "evidence_message_ids": list(
                                dict.fromkeys(new_evidence_ids)
                            ),
                            "evidence": new_evidence,
                            "clarification_target": None,
                        },
                        deep=True,
                    )
                )
            else:
                existing_by_role = {
                    item.role: item for item in term.participant_positions
                }
                positions = []
                for role in PartyRole:
                    if role in message_by_role:
                        positions.append(
                            ParticipantPosition(
                                participant_id=role.value,
                                role=role,
                                summary=question.selections[role].semantic_value,
                                evidence_message_ids=[message_by_role[role].message_id],
                            )
                        )
                    elif role in existing_by_role:
                        positions.append(existing_by_role[role])
                roles = {item.role for item in positions}
                state = (
                    MeaningState.CONFLICTING
                    if roles == set(PartyRole)
                    else MeaningState.STATED_BY_ONE
                )
                statuses = {
                    role: (
                        ParticipantTermStatus.CONFLICTING
                        if state == MeaningState.CONFLICTING
                        else (
                            ParticipantTermStatus.STATED
                            if role in roles
                            else ParticipantTermStatus.NOT_STATED
                        )
                    )
                    for role in PartyRole
                }
                terms.append(
                    term.model_copy(
                        update={
                            "summary": meaning,
                            "state": state,
                            "participant_positions": positions,
                            "participant_confirmations": statuses,
                            "evidence_message_ids": list(
                                dict.fromkeys(new_evidence_ids)
                            ),
                            "evidence": new_evidence,
                            "clarification_target": term.analysis_item_key,
                        },
                        deep=True,
                    )
                )
        derived = self._build_derived_version(record, version, terms)
        self._commit_version(record, derived)
        return derived

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
            questions=[_deep_copy(item.question) for item in record.questions],
            understanding_reviews={
                role: _deep_copy(item)
                for role, item in record.understanding_reviews.items()
            },
            active_participant_id=record.active_participant_id,
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
        has_completed_clarification = bool(
            version and self._has_current_completed_clarification(record, version)
        )
        active = self._active_question(record)
        active_clarification = (
            active
            if active is not None
            and active.question.kind == UnderstandingQuestionKind.CLARIFICATION
            else None
        )
        common = {
            "required_issue_count": len(required_keys),
            "optional_missing_count": len(optional_keys),
            "acting_participant": record.active_participant_id,
            "active_question_id": active.question.id if active else None,
            "active_clarification_id": (
                active_clarification.question.id if active_clarification else None
            ),
            "target_item_key": (active.question.agreement_item_id if active else None),
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
                explanation="MeaningSync is comparing the two stated understandings.",
                primary_action=LiveGuidanceAction.START_UNDERSTANDING_CHECK,
                primary_label="Preparing agreement map",
                **common,
            )
        if active_clarification is not None:
            attempts = active_clarification.attempt_number
            if (
                active_clarification.question.status
                in {
                    UnderstandingQuestionStatus.NEEDS_CLARIFICATION,
                    UnderstandingQuestionStatus.UNSURE,
                }
                and attempts >= self._clarification_attempt_limit
            ):
                return LiveWorkflowGuidance(
                    user_stage=LiveUserStage.CLARIFY,
                    headline="This point is still different",
                    explanation=(
                        "Both people can keep this point explicitly unresolved "
                        "to continue."
                    ),
                    primary_action=LiveGuidanceAction.LEAVE_UNRESOLVED,
                    primary_label="Leave this unresolved",
                    **common,
                )
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CLARIFY,
                headline="Clarify one required meaning",
                explanation=(
                    "Choose privately. The first choice stays hidden until both "
                    "people answer."
                ),
                primary_action=LiveGuidanceAction.SUBMIT_SELECTION,
                primary_label="Submit my choice",
                secondary_action=LiveGuidanceAction.LEAVE_UNRESOLVED,
                secondary_label="Leave this unresolved",
                **common,
            )
        if record.stage in {
            LiveSessionStage.NEEDS_CLARIFICATION,
            LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK,
        }:
            if optional_keys and not record.optional_details_reviewed:
                return LiveWorkflowGuidance(
                    user_stage=LiveUserStage.CHECK_UNDERSTANDING,
                    headline=(
                        "One final understanding check"
                        if has_completed_clarification
                        else "Check the important meanings"
                    ),
                    explanation=(
                        "The important difference is already clarified. Review "
                        "optional details, then MeaningSync will ask at most one "
                        "final question."
                        if has_completed_clarification
                        else "Optional details were not discussed. Continue with them "
                        "open, or add any that matter first."
                    ),
                    primary_action=LiveGuidanceAction.START_UNDERSTANDING_CHECK,
                    primary_label=(
                        "One final understanding check"
                        if has_completed_clarification
                        else "Check understanding"
                    ),
                    secondary_action=LiveGuidanceAction.REVIEW_OPTIONAL_DETAILS,
                    secondary_label="Add optional details",
                    **common,
                )
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CHECK_UNDERSTANDING,
                headline=(
                    "One final understanding check"
                    if has_completed_clarification
                    else "Check the important meanings"
                ),
                explanation=(
                    "The important difference is already clarified. MeaningSync will "
                    "ask at most one final question before separate confirmation."
                    if has_completed_clarification
                    else "Choose the meaning you understood. Your choice stays private "
                    "until both people answer."
                ),
                primary_action=LiveGuidanceAction.START_UNDERSTANDING_CHECK,
                primary_label=(
                    "One final understanding check"
                    if has_completed_clarification
                    else "Check understanding"
                ),
                **common,
            )
        if record.stage == LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS:
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CHECK_UNDERSTANDING,
                headline=(
                    "One final understanding check"
                    if has_completed_clarification
                    else "Choose the meaning you understood"
                ),
                explanation=(
                    "One final understanding check remains. Your choice stays private "
                    "until both people answer."
                    if has_completed_clarification
                    else "Your choice stays private until both people answer."
                ),
                primary_action=LiveGuidanceAction.SUBMIT_SELECTION,
                primary_label="Submit my choice",
                **common,
            )
        if record.stage == LiveSessionStage.AWAITING_CONFIRMATIONS:
            skipped = bool(record.understanding_reviews) and all(
                item.status
                in {
                    ParticipantReviewStatus.SKIPPED,
                    ParticipantReviewStatus.CONFIRMED,
                }
                and not item.completed_question_ids
                for item in record.understanding_reviews.values()
            )
            clarification_covered_difference = skipped and has_completed_clarification
            return LiveWorkflowGuidance(
                user_stage=LiveUserStage.CONFIRM,
                headline=(
                    "The important difference is already clarified"
                    if clarification_covered_difference
                    else (
                        "No additional understanding question was needed"
                        if skipped
                        else "Confirm each understanding separately"
                    )
                ),
                explanation=(
                    "The completed clarification already covered the important "
                    "difference, so no additional understanding question was needed. "
                    "Each person can now confirm this exact version."
                    if clarification_covered_difference
                    else (
                        "The recorded meanings already had sufficient independent "
                        "evidence. Each person can now confirm this exact version."
                        if skipped
                        else "The acting participant confirms this exact agreement "
                        "version."
                    )
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

    def _active_question(self, record: _LiveSessionRecord) -> _QuestionRecord | None:
        clarification_statuses = {
            UnderstandingQuestionStatus.PENDING,
            UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
            UnderstandingQuestionStatus.NEEDS_CLARIFICATION,
            UnderstandingQuestionStatus.UNSURE,
        }
        clarification = next(
            (
                item
                for item in reversed(record.questions)
                if item.question.agreement_version_id == record.current_version_id
                and item.question.kind == UnderstandingQuestionKind.CLARIFICATION
                and item.question.status in clarification_statuses
            ),
            None,
        )
        if clarification is not None:
            return clarification
        checks = [
            item
            for item in record.questions
            if item.question.agreement_version_id == record.current_version_id
            and item.question.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
            and item.question.status
            in {
                UnderstandingQuestionStatus.PENDING,
                UnderstandingQuestionStatus.PARTIALLY_ANSWERED,
            }
        ]
        return min(checks, key=lambda item: item.question.question_number, default=None)

    def _question(
        self, record: _LiveSessionRecord, question_id: str
    ) -> _QuestionRecord:
        question = next(
            (item for item in record.questions if item.question.id == question_id), None
        )
        if question is None:
            raise WorkflowFailure(
                WorkflowErrorCode.QUESTION_NOT_FOUND,
                "That question does not belong to this session.",
                status_code=404,
                current_agreement_version_id=record.current_version_id,
            )
        if question.question.agreement_version_id != record.current_version_id:
            raise self._stale(record)
        return question

    def _require_question_stage(
        self, record: _LiveSessionRecord, question: _QuestionRecord
    ) -> None:
        required = (
            LiveSessionStage.NEEDS_CLARIFICATION
            if question.question.kind == UnderstandingQuestionKind.CLARIFICATION
            else LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS
        )
        self._require_stage(record, required)
        active = self._active_question(record)
        if active is None or active.question.id != question.question.id:
            raise self._invalid_state(record, "Answer the current question first.")

    def _select_next_stage(self, record: _LiveSessionRecord) -> None:
        version = self._current_version(record)
        if version is None:
            record.stage = LiveSessionStage.CONVERSATION_DRAFT
            record.active_participant_id = None
            return
        active = self._active_question(record)
        if active is not None:
            record.stage = (
                LiveSessionStage.NEEDS_CLARIFICATION
                if active.question.kind == UnderstandingQuestionKind.CLARIFICATION
                else LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS
            )
            if active.question.status == UnderstandingQuestionStatus.PARTIALLY_ANSWERED:
                record.active_participant_id = next(
                    role
                    for role in active.question.addressed_participant_ids
                    if role not in active.selections
                )
            elif active.question.kind == UnderstandingQuestionKind.CLARIFICATION and (
                active.question.status
                in {
                    UnderstandingQuestionStatus.NEEDS_CLARIFICATION,
                    UnderstandingQuestionStatus.UNSURE,
                }
            ):
                record.active_participant_id = PartyRole.HIRER
            else:
                record.active_participant_id = (
                    active.question.addressed_participant_ids[0]
                )
            return

        provider_question = version.primary_clarification
        completed_meanings = self._independently_answered_meanings(record)
        for term in ordered_clarification_candidates(version.terms):
            target = semantic_target(term)
            meaning_fingerprint = semantic_meaning_fingerprint(term, version.terms)
            if (target, meaning_fingerprint) in completed_meanings:
                continue
            fingerprint = meaning_fingerprint
            if any(
                item.semantic_fingerprint == fingerprint
                and item.question.kind == UnderstandingQuestionKind.CLARIFICATION
                and item.question.status
                in {
                    UnderstandingQuestionStatus.COMPLETED,
                    UnderstandingQuestionStatus.LEFT_UNRESOLVED,
                }
                for item in record.questions
            ):
                continue
            attempts = self._clarification_attempts(record, target, meaning_fingerprint)
            if attempts >= self._clarification_attempt_limit:
                continue
            prompt_override = None
            if (
                provider_question is not None
                and provider_question.target_item_key == term.analysis_item_key
            ):
                prompt_override = provider_question.prompt
            addressed = addressed_participants(term)
            if not addressed:
                continue
            self._append_question(
                record,
                version,
                term,
                kind=UnderstandingQuestionKind.CLARIFICATION,
                addressed=addressed,
                prompt_override=prompt_override,
                attempt_number=attempts + 1,
            )
            record.stage = LiveSessionStage.NEEDS_CLARIFICATION
            record.active_participant_id = addressed[0]
            return
        record.stage = LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK
        record.active_participant_id = None

    def _append_question(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        term: AgreementTerm,
        *,
        kind: UnderstandingQuestionKind,
        addressed: list[PartyRole],
        prompt_override: str | None = None,
        question_number: int = 1,
        question_count: int = 1,
        attempt_number: int = 1,
    ) -> _QuestionRecord:
        definition = build_question_definition(
            term,
            version.terms,
            kind=kind,
            prompt_override=prompt_override,
        )
        question = UnderstandingQuestion(
            id=_id("question"),
            session_id=record.id,
            agreement_version_id=version.id,
            agreement_item_id=term.analysis_item_key,
            kind=kind,
            prompt=definition.prompt,
            options=[item.option for item in definition.options],
            evidence_reference_ids=list(definition.evidence_reference_ids),
            addressed_participant_ids=addressed,
            status=UnderstandingQuestionStatus.PENDING,
            question_number=question_number,
            question_count=question_count,
        )
        stored = _QuestionRecord(
            question=question,
            semantic_target=definition.semantic_target,
            semantic_fingerprint=definition.meaning_fingerprint,
            option_semantics={
                item.option.id: item.semantic_value for item in definition.options
            },
            attempt_number=attempt_number,
        )
        record.questions.append(stored)
        return stored

    def _outstanding_required_item_keys(
        self, record: _LiveSessionRecord, version: AgreementVersion
    ) -> list[str]:
        active = self._active_question(record)
        outstanding = (
            [active.question.agreement_item_id]
            if active is not None
            and active.question.kind == UnderstandingQuestionKind.CLARIFICATION
            else []
        )
        active_target = active.semantic_target if active else None
        completed = self._independently_answered_meanings(record)
        for term in ordered_clarification_candidates(version.terms):
            target = semantic_target(term)
            if (
                target == active_target
                or (
                    target,
                    semantic_meaning_fingerprint(term, version.terms),
                )
                in completed
            ):
                continue
            if self._clarification_attempts(
                record,
                target,
                semantic_meaning_fingerprint(term, version.terms),
            ) >= (self._clarification_attempt_limit):
                continue
            outstanding.append(term.analysis_item_key)
        return outstanding

    def _analysis_request(
        self, record: _LiveSessionRecord, messages: list[AnalysisMessage]
    ) -> AgreementAnalysisRequest:
        message_ids = {message.message_id for message in messages}
        contexts = [
            AnalysisClarificationContext(
                clarification_id=item.question.id,
                target_item_key=item.question.agreement_item_id,
                question=item.question.prompt,
                response_message_ids=item.response_message_ids,
            )
            for item in record.questions
            if item.question.kind == UnderstandingQuestionKind.CLARIFICATION
            and item.response_message_ids
            and set(item.response_message_ids.values()).issubset(message_ids)
        ]
        return AgreementAnalysisRequest(
            session_id=record.id,
            mode=SessionMode.LIVE,
            participants=record.participants,
            messages=messages,
            clarification_contexts=contexts,
        )

    def _build_analysis_version(
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
            unresolved_item_keys=[
                item.analysis_item_key
                for item in terms
                if item.state != MeaningState.ALIGNED
                and item.analysis_item_key not in mutual
            ],
            not_applicable_proposals=proposals,
            prompt_version=response.prompt_version,
            model=response.model,
            analysis_status=response.status,
            warnings=response.warnings,
            primary_clarification=response.primary_clarification,
            changes=self._changes(parent, terms) if parent else [],
        )

    def _build_derived_version(
        self,
        record: _LiveSessionRecord,
        parent: AgreementVersion,
        terms: list[AgreementTerm],
    ) -> AgreementVersion:
        valid_not_discussed = {
            item.analysis_item_key
            for item in terms
            if item.state == MeaningState.NOT_DISCUSSED
        }
        proposals = [
            item
            for item in parent.not_applicable_proposals
            if item.item_key in valid_not_discussed
        ]
        mutual = self._mutually_not_applicable(proposals)
        semantic_fingerprint = agreement_semantic_fingerprint(terms, mutual)
        meaningful = semantic_fingerprint != parent.semantic_fingerprint
        return AgreementVersion(
            id=_id("agreement"),
            version_number=parent.version_number + 1,
            meaningful_version_number=(
                parent.meaningful_version_number + (1 if meaningful else 0)
            ),
            has_meaningful_change=meaningful,
            semantic_fingerprint=semantic_fingerprint,
            parent_version_id=parent.id,
            session_id=record.id,
            created_at=_now(),
            source_message_ids=[item.message_id for item in record.messages],
            terms=terms,
            unresolved_item_keys=[
                item.analysis_item_key
                for item in terms
                if item.state != MeaningState.ALIGNED
                and item.analysis_item_key not in mutual
            ],
            not_applicable_proposals=proposals,
            prompt_version="choice-resolution-v1",
            model="deterministic-choice-resolution",
            analysis_status=AnalysisStatus.COMPLETE,
            warnings=parent.warnings,
            primary_clarification=None,
            changes=self._changes(parent, terms),
        )

    def _with_evidence_provenance(self, term: AgreementTerm) -> AgreementTerm:
        def evidence_with_source(item: EvidenceReference) -> EvidenceReference:
            if item.message_id is None:
                return _deep_copy(item)
            if item.message_id.startswith("clarification-"):
                return item.model_copy(update={"source": "clarification"})
            if item.message_id.startswith("understanding-"):
                return item.model_copy(update={"source": "understanding_check"})
            return _deep_copy(item)

        return term.model_copy(
            update={"evidence": [evidence_with_source(item) for item in term.evidence]},
            deep=True,
        )

    def _commit_version(
        self, record: _LiveSessionRecord, version: AgreementVersion
    ) -> None:
        previous_version_id = record.current_version_id
        if previous_version_id is not None and previous_version_id != version.id:
            record.questions = [
                item
                for item in record.questions
                if not (
                    item.question.kind == UnderstandingQuestionKind.UNDERSTANDING_CHECK
                    and item.question.agreement_version_id == previous_version_id
                    and item.question.status == UnderstandingQuestionStatus.PENDING
                    and not item.selections
                    and not item.question.answered_participant_ids
                )
            ]
        record.versions.append(_deep_copy(version))
        record.current_version_id = version.id
        record.optional_details_reviewed = False
        self._invalidate_confirmations(record, version.id)

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
                        item.reference_id
                        for item in term.evidence
                        if old is None
                        or item.reference_id
                        not in {evidence.reference_id for evidence in old.evidence}
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

    def _selection_messages(
        self, record: _LiveSessionRecord, question: _QuestionRecord
    ) -> list[AnalysisMessage]:
        if not question.selections:
            return []
        if len(record.messages) + len(question.selections) > 40:
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_STATE,
                "This in-memory session has reached the statement limit.",
                status_code=422,
                current_agreement_version_id=record.current_version_id,
            )
        start = max(item.order for item in record.messages) + 1
        timestamp = _now()
        return [
            AnalysisMessage(
                message_id=_id(
                    "clarification"
                    if question.question.kind == UnderstandingQuestionKind.CLARIFICATION
                    else "understanding"
                ),
                speaker_id=role.value,
                original_text=selection.semantic_value,
                original_language=next(
                    item.language for item in record.participants if item.role == role
                ),
                order=start + offset,
                timestamp=timestamp,
            )
            for offset, (role, selection) in enumerate(question.selections.items())
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

    def _record_conversation_evidence(
        self, record: _LiveSessionRecord, version: AgreementVersion
    ) -> None:
        for term in version.terms:
            roles = list(
                dict.fromkeys(item.role for item in term.participant_positions)
            )
            if not roles:
                continue
            self._append_evidence(
                record,
                version,
                term,
                source=UnderstandingEvidenceSource.CONVERSATION,
                participant_ids=roles,
                evidence_reference_ids=[item.reference_id for item in term.evidence],
            )

    def _record_question_evidence(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        question: _QuestionRecord,
    ) -> None:
        term = self._term(version, question.question.agreement_item_id)
        roles = set(question.selections)
        if question.question.kind == UnderstandingQuestionKind.CLARIFICATION:
            roles.update(item.role for item in term.participant_positions)
        self._append_evidence(
            record,
            version,
            term,
            source=(
                UnderstandingEvidenceSource.CLARIFICATION
                if question.question.kind == UnderstandingQuestionKind.CLARIFICATION
                else UnderstandingEvidenceSource.UNDERSTANDING_CHECK
            ),
            participant_ids=list(sorted(roles, key=lambda item: item.value)),
            evidence_reference_ids=[item.id for item in question.selections.values()],
        )

    def _record_confirmation_evidence(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        submission: ConfirmationSubmission,
    ) -> None:
        for term in version.terms:
            if term.state == MeaningState.NOT_DISCUSSED:
                continue
            self._append_evidence(
                record,
                version,
                term,
                source=UnderstandingEvidenceSource.FINAL_CONFIRMATION,
                participant_ids=[submission.participant_id],
                evidence_reference_ids=[submission.request_id],
            )

    def _append_evidence(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        term: AgreementTerm,
        *,
        source: UnderstandingEvidenceSource,
        participant_ids: list[PartyRole],
        evidence_reference_ids: list[str],
    ) -> None:
        record.evidence_ledger.append(
            IndependentMeaningEvidence(
                id=_id("meaning-evidence"),
                session_id=record.id,
                agreement_version_id=version.id,
                agreement_item_id=term.analysis_item_key,
                semantic_target=semantic_target(term),
                semantic_fingerprint=semantic_meaning_fingerprint(term, version.terms),
                source=source,
                participant_ids=participant_ids,
                evidence_reference_ids=evidence_reference_ids,
                created_at=_now(),
            )
        )

    def _independently_answered_meanings(
        self, record: _LiveSessionRecord
    ) -> set[tuple[str, str]]:
        by_meaning: dict[tuple[str, str], set[PartyRole]] = {}
        for item in record.evidence_ledger:
            if item.source not in {
                UnderstandingEvidenceSource.CLARIFICATION,
                UnderstandingEvidenceSource.UNDERSTANDING_CHECK,
            }:
                continue
            key = (item.semantic_target, item.semantic_fingerprint)
            by_meaning.setdefault(key, set()).update(item.participant_ids)
        return {key for key, roles in by_meaning.items() if roles == set(PartyRole)}

    def _has_current_completed_clarification(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
    ) -> bool:
        current_meanings = {
            (
                semantic_target(term),
                semantic_meaning_fingerprint(term, version.terms),
            )
            for term in version.terms
        }
        completed = [
            question
            for question in record.questions
            if question.question.kind == UnderstandingQuestionKind.CLARIFICATION
            and question.question.status == UnderstandingQuestionStatus.COMPLETED
            and question.selections
        ]
        for question in completed:
            selection_ids = {item.id for item in question.selections.values()}
            if any(
                item.source == UnderstandingEvidenceSource.CLARIFICATION
                and (item.semantic_target, item.semantic_fingerprint)
                in current_meanings
                and item.semantic_target == question.semantic_target
                and set(item.participant_ids) == set(PartyRole)
                and selection_ids.issubset(set(item.evidence_reference_ids))
                for item in record.evidence_ledger
            ):
                return True
        return False

    def _completed_check_is_current(
        self,
        record: _LiveSessionRecord,
        version: AgreementVersion,
        question: _QuestionRecord,
    ) -> bool:
        outcome = question.question.outcome
        if outcome is not None and outcome.resulting_agreement_version_id == version.id:
            return True
        current_term = next(
            (
                term
                for term in version.terms
                if semantic_target(term) == question.semantic_target
            ),
            None,
        )
        if current_term is None or not question.selections:
            return False
        current_fingerprint = semantic_meaning_fingerprint(
            current_term,
            version.terms,
        )
        selection_ids = {item.id for item in question.selections.values()}
        return any(
            item.source == UnderstandingEvidenceSource.UNDERSTANDING_CHECK
            and item.semantic_target == question.semantic_target
            and item.semantic_fingerprint == current_fingerprint
            and set(item.participant_ids) == set(PartyRole)
            and selection_ids.issubset(set(item.evidence_reference_ids))
            for item in record.evidence_ledger
        )

    def _clarification_attempts(
        self,
        record: _LiveSessionRecord,
        target: str,
        meaning_fingerprint: str,
    ) -> int:
        return sum(
            item.question.kind == UnderstandingQuestionKind.CLARIFICATION
            and item.semantic_target == target
            and item.semantic_fingerprint == meaning_fingerprint
            for item in record.questions
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
                record, "This action is not available at the current step."
            )

    def _require_modifiable(self, record: _LiveSessionRecord) -> None:
        if record.stage not in {
            LiveSessionStage.NEEDS_CLARIFICATION,
            LiveSessionStage.READY_FOR_UNDERSTANDING_CHECK,
            LiveSessionStage.AWAITING_UNDERSTANDING_CHECKS,
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
        name = (
            "Homeowner"
            if expected == PartyRole.HIRER
            else "Electrician"
            if expected == PartyRole.WORKER
            else "the active participant"
        )
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
                WorkflowErrorCode.UNDERSTANDING_INCOMPLETE,
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

    def _request_digest(self, operation: str, target: str | None, submission) -> str:
        payload = {
            "operation": operation,
            "target": target,
            "submission": submission.model_dump(mode="json"),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _is_replay(
        self, record: _LiveSessionRecord, request_id: str, digest: str
    ) -> bool:
        previous = record.processed_requests.get(request_id)
        if previous is None:
            return False
        if previous != digest:
            raise WorkflowFailure(
                WorkflowErrorCode.IDEMPOTENCY_CONFLICT,
                "That request ID was already used for a different action.",
                status_code=409,
                current_agreement_version_id=record.current_version_id,
            )
        return True

    @staticmethod
    def _mark_processed(
        record: _LiveSessionRecord, request_id: str, digest: str
    ) -> None:
        record.processed_requests[request_id] = digest

    @staticmethod
    def _mutually_not_applicable(
        proposals: list[NotApplicableProposal],
    ) -> set[str]:
        all_roles = set(PartyRole)
        return {
            item.item_key for item in proposals if set(item.proposed_by) == all_roles
        }

    def _invalidate_review(self, record: _LiveSessionRecord) -> None:
        record.understanding_reviews = {}
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
        reviews: list[ParticipantUnderstandingReview],
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
                    clarification_id=item.question.id,
                    target_item_key=item.question.agreement_item_id,
                    target_agreement_version_id=item.question.agreement_version_id,
                    resulting_agreement_version_id=(
                        item.question.outcome.resulting_agreement_version_id
                        if item.question.outcome
                        else None
                    ),
                    status=self._clarification_history_status(item),
                    response_message_ids=item.response_message_ids,
                    fingerprint=item.semantic_fingerprint,
                    semantic_target=item.semantic_target,
                )
                for item in record.questions
                if item.question.kind == UnderstandingQuestionKind.CLARIFICATION
            ],
            "understanding_status": [
                ReceiptUnderstandingStatus(
                    participant_id=item.participant_id,
                    review_id=item.id,
                    result=(
                        UnderstandingReviewResult.COMPLETED
                        if item.completed_question_ids
                        else UnderstandingReviewResult.SKIPPED
                    ),
                    completed_at=item.completed_at or issued_at,
                    question_ids=item.completed_question_ids,
                )
                for item in reviews
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

    @staticmethod
    def _clarification_history_status(
        item: _QuestionRecord,
    ) -> ClarificationWorkflowStatus:
        mapping = {
            UnderstandingQuestionStatus.PENDING: ClarificationWorkflowStatus.PENDING,
            UnderstandingQuestionStatus.PARTIALLY_ANSWERED: (
                ClarificationWorkflowStatus.ANSWERED
            ),
            UnderstandingQuestionStatus.COMPLETED: (
                ClarificationWorkflowStatus.RESOLVED
            ),
            UnderstandingQuestionStatus.NEEDS_CLARIFICATION: (
                ClarificationWorkflowStatus.STILL_UNRESOLVED
            ),
            UnderstandingQuestionStatus.UNSURE: (
                ClarificationWorkflowStatus.STILL_UNRESOLVED
            ),
            UnderstandingQuestionStatus.LEFT_UNRESOLVED: (
                ClarificationWorkflowStatus.LEFT_UNRESOLVED
            ),
        }
        return mapping[item.question.status]
