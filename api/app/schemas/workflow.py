from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.analysis import (
    AgreementTerm,
    AnalysisMessage,
    AnalysisParticipant,
    AnalysisStatus,
    AnalysisWarning,
    ClarificationQuestion,
    Identifier,
    LanguageCode,
    MeaningState,
    PartyRole,
    SessionMode,
    StrictModel,
)
from app.schemas.understanding import (
    UnderstandingQuestion,
    UnderstandingReviewResult,
)


class FrozenWorkflowModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )


class LiveSessionStage(StrEnum):
    CONVERSATION_DRAFT = "conversation_draft"
    ANALYZING = "analyzing"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_UNDERSTANDING_CHECK = "ready_for_understanding_check"
    AWAITING_UNDERSTANDING_CHECKS = "awaiting_understanding_checks"
    AWAITING_CONFIRMATIONS = "awaiting_confirmations"
    CONFIRMED = "confirmed"
    RECEIPT_ISSUED = "receipt_issued"


class LiveParticipationMode(StrEnum):
    SAME_DEVICE = "same_device"
    SEPARATE_DEVICES = "separate_devices"


class CurrencyCode(StrEnum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"


class ClarificationWorkflowStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    STILL_UNRESOLVED = "still_unresolved"
    LEFT_UNRESOLVED = "left_unresolved"


class LiveUserStage(StrEnum):
    PREFERENCES = "preferences"
    PARTICIPATION = "participation"
    CONVERSATION = "conversation"
    CLARIFY = "clarify"
    CHECK_UNDERSTANDING = "check_understanding"
    CONFIRM = "confirm"
    RECEIPT = "receipt"


class LiveGuidanceAction(StrEnum):
    SUBMIT_SELECTION = "submit_selection"
    LEAVE_UNRESOLVED = "leave_unresolved"
    REVIEW_OPTIONAL_DETAILS = "review_optional_details"
    START_UNDERSTANDING_CHECK = "start_understanding_check"
    SUBMIT_CONFIRMATION = "submit_confirmation"
    ISSUE_RECEIPT = "issue_receipt"
    VIEW_RECEIPT = "view_receipt"


class ParticipantReviewStatus(StrEnum):
    NOT_STARTED = "not_started"
    CHECKING = "checking"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    READY_TO_CONFIRM = "ready_to_confirm"
    CONFIRMED = "confirmed"


class ConfirmationDecision(StrEnum):
    CONFIRM = "confirm"
    REQUEST_CHANGE = "request_change"


class ReceiptStatus(StrEnum):
    FULLY_ALIGNED = "fully_aligned"
    CONTAINS_UNRESOLVED_ITEMS = "contains_unresolved_items"


class WorkflowErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_STATE = "invalid_state"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    CONCURRENT_UPDATE = "concurrent_update"
    STORED_STATE_INVALID = "stored_state_invalid"
    STALE_AGREEMENT_VERSION = "stale_agreement_version"
    CLARIFICATION_TARGET_MISSING = "clarification_target_missing"
    CLARIFICATION_LIMIT_REACHED = "clarification_limit_reached"
    PARTICIPANT_MISMATCH = "participant_mismatch"
    QUESTION_NOT_FOUND = "question_not_found"
    INVALID_OPTION = "invalid_option"
    QUESTION_INCOMPLETE = "question_incomplete"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    UNDERSTANDING_INCOMPLETE = "understanding_incomplete"
    CONFIRMATION_MISSING = "confirmation_missing"
    CONFIRMATION_VERSION_MISMATCH = "confirmation_version_mismatch"
    RECEIPT_NOT_READY = "receipt_not_ready"
    ACCESS_REQUIRED = "access_required"
    ACCESS_INVALID = "access_invalid"
    ACCESS_EXPIRED = "access_expired"
    ACCESS_REVOKED = "access_revoked"
    ROLE_FORBIDDEN = "role_forbidden"
    INVITATION_INVALID = "invitation_invalid"
    INVITATION_EXPIRED = "invitation_expired"
    INVITATION_USED = "invitation_used"
    INVITATION_REVOKED = "invitation_revoked"
    AUDIO_CONSENT_REQUIRED = "audio_consent_required"
    AUDIO_LIMIT_REACHED = "audio_limit_reached"
    TRANSCRIPTION_UNAVAILABLE = "transcription_unavailable"


class WorkflowErrorDetail(StrictModel):
    code: WorkflowErrorCode
    message: str = Field(min_length=1, max_length=400)
    retryable: bool = False
    current_agreement_version_id: Identifier | None = None


class WorkflowErrorResponse(StrictModel):
    detail: WorkflowErrorDetail


class LiveSessionCreate(StrictModel):
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(default_factory=list, max_length=40)
    participation_mode: LiveParticipationMode = LiveParticipationMode.SAME_DEVICE
    currency: CurrencyCode = CurrencyCode.INR
    creator_role: PartyRole = PartyRole.HIRER

    @model_validator(mode="after")
    def validate_initial_messages(self) -> LiveSessionCreate:
        if len(self.messages) == 1:
            raise ValueError("initial messages must be empty or include both people")
        return self


class LiveAccessCredential(StrictModel):
    role: PartyRole
    access_token: str = Field(min_length=32, max_length=200)
    expires_at: datetime


class LiveInvitation(StrictModel):
    role: PartyRole
    invitation: str = Field(min_length=32, max_length=200)
    expires_at: datetime


class LiveInvitationExchange(StrictModel):
    invitation: str = Field(min_length=32, max_length=200)
    privacy_notice_accepted: bool

    @model_validator(mode="after")
    def require_notice(self) -> LiveInvitationExchange:
        if not self.privacy_notice_accepted:
            raise ValueError("the privacy notice must be accepted")
        return self


class LiveInvitationExchangeResult(StrictModel):
    session_id: Identifier
    role: PartyRole
    access_token: str = Field(min_length=32, max_length=200)
    expires_at: datetime


class LiveInvitationResult(StrictModel):
    session_id: Identifier
    invitation: LiveInvitation


class ParticipantPresence(StrictModel):
    role: PartyRole
    status: Literal["waiting", "connected", "offline"]
    last_seen_at: datetime | None = None


class AudioConsent(FrozenWorkflowModel):
    id: Identifier
    session_id: Identifier
    participant_role: PartyRole
    notice_version: str = Field(min_length=1, max_length=80)
    consented_at: datetime
    request_id: Identifier


class AudioTranscriptionConfiguration(StrictModel):
    model: str = Field(min_length=1, max_length=120)
    consent_notice_version: str = Field(min_length=1, max_length=80)
    max_turn_duration_seconds: int = Field(ge=5, le=3600)
    max_session_duration_seconds_per_participant: int = Field(ge=5, le=86400)
    initialization_timeout_seconds: float = Field(gt=0, le=120)
    idle_timeout_seconds: int = Field(ge=5, le=600)
    max_transcript_length: int = Field(ge=2, le=20000)
    max_concurrent_sessions_per_participant: int = Field(ge=1, le=5)


class AgreementVersionChange(FrozenWorkflowModel):
    item_key: Identifier
    label: str = Field(min_length=1, max_length=100)
    previous_state: MeaningState | None = None
    current_state: MeaningState | None = None
    resulting_meaning: str = Field(min_length=1, max_length=600)
    new_evidence_reference_ids: list[str] = Field(default_factory=list, max_length=40)


class NotApplicableProposal(FrozenWorkflowModel):
    item_key: Identifier
    label: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=600)
    proposed_by: list[PartyRole] = Field(default_factory=list, max_length=2)


class AgreementVersion(FrozenWorkflowModel):
    id: Identifier
    version_number: int = Field(ge=1)
    meaningful_version_number: int = Field(default=1, ge=1)
    has_meaningful_change: bool = True
    semantic_fingerprint: str = Field(default="0" * 64, pattern=r"^[a-f0-9]{64}$")
    parent_version_id: Identifier | None = None
    session_id: Identifier
    mode: SessionMode = SessionMode.LIVE
    created_at: datetime
    source_message_ids: list[Identifier] = Field(min_length=2, max_length=80)
    terms: list[AgreementTerm] = Field(min_length=1, max_length=20)
    unresolved_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)
    not_applicable_proposals: list[NotApplicableProposal] = Field(
        default_factory=list, max_length=20
    )
    prompt_version: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    schema_version: str = "agreement-version-v1"
    analysis_status: AnalysisStatus
    warnings: list[AnalysisWarning] = Field(default_factory=list, max_length=4)
    primary_clarification: ClarificationQuestion | None = None
    changes: list[AgreementVersionChange] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_snapshot(self) -> AgreementVersion:
        item_keys = [term.analysis_item_key for term in self.terms]
        if len(item_keys) != len(set(item_keys)):
            raise ValueError("agreement version item keys must be unique")
        if not set(self.unresolved_item_keys).issubset(set(item_keys)):
            raise ValueError("unresolved items must exist in this agreement version")
        if any(
            proposal.item_key not in item_keys
            for proposal in self.not_applicable_proposals
        ):
            raise ValueError("not-applicable proposals must target version items")
        return self


class ParticipantUnderstandingReview(FrozenWorkflowModel):
    id: Identifier
    participant_id: PartyRole
    agreement_version_id: Identifier
    status: ParticipantReviewStatus
    completed_question_ids: list[Identifier] = Field(default_factory=list, max_length=3)
    created_at: datetime
    completed_at: datetime | None = None


class ConfirmationRecord(FrozenWorkflowModel):
    id: Identifier
    participant_id: PartyRole
    agreement_version_id: Identifier
    understanding_review_id: Identifier
    unresolved_item_acknowledgments: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    confirmed_at: datetime
    language: LanguageCode
    request_id: Identifier
    invalidated_at: datetime | None = None


class ClarificationHistoryEntry(FrozenWorkflowModel):
    clarification_id: Identifier
    target_item_key: Identifier
    target_agreement_version_id: Identifier
    resulting_agreement_version_id: Identifier | None = None
    status: ClarificationWorkflowStatus
    response_message_ids: dict[PartyRole, Identifier] = Field(default_factory=dict)
    fingerprint: str = Field(default="legacy", min_length=1, max_length=80)
    semantic_target: Identifier = "legacy.target"


class ReceiptParticipant(FrozenWorkflowModel):
    participant_id: PartyRole
    role: PartyRole
    display_name: str
    language: LanguageCode


class ReceiptUnderstandingStatus(FrozenWorkflowModel):
    participant_id: PartyRole
    review_id: Identifier
    result: UnderstandingReviewResult
    completed_at: datetime
    question_ids: list[Identifier] = Field(default_factory=list, max_length=3)


class ReceiptConfirmation(FrozenWorkflowModel):
    participant_id: PartyRole
    confirmation_id: Identifier
    confirmed_at: datetime
    language: LanguageCode


class LiveClarityReceipt(FrozenWorkflowModel):
    id: Identifier
    session_id: Identifier
    agreement_version_id: Identifier
    agreement_version_number: int = Field(ge=1)
    issued_at: datetime
    session_created_at: datetime | None = None
    currency: CurrencyCode = CurrencyCode.INR
    participants: list[ReceiptParticipant] = Field(min_length=2, max_length=2)
    aligned_terms: list[AgreementTerm]
    unresolved_terms: list[AgreementTerm]
    one_sided_terms: list[AgreementTerm]
    not_applicable_terms: list[NotApplicableProposal]
    not_discussed_terms: list[AgreementTerm]
    clarification_history: list[ClarificationHistoryEntry]
    agreement_history: list[AgreementVersionChange] = Field(default_factory=list)
    understanding_status: list[ReceiptUnderstandingStatus] = Field(
        min_length=2, max_length=2
    )
    confirmations: list[ReceiptConfirmation] = Field(min_length=2, max_length=2)
    status: ReceiptStatus
    application_version: str = "0.4.0"
    schema_version: str = "clarity-receipt-v2"
    disclaimer: str = (
        "This clarity receipt records the participants’ stated understanding. "
        "MeaningSync does not provide legal advice, and this receipt is not "
        "presented as a legally enforceable contract."
    )
    integrity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LiveWorkflowGuidance(StrictModel):
    user_stage: LiveUserStage
    headline: str = Field(min_length=1, max_length=160)
    explanation: str = Field(min_length=1, max_length=400)
    primary_action: LiveGuidanceAction
    primary_label: str = Field(min_length=1, max_length=100)
    secondary_action: LiveGuidanceAction | None = None
    secondary_label: str | None = Field(default=None, min_length=1, max_length=100)
    required_issue_count: int = Field(ge=0, le=20)
    optional_missing_count: int = Field(ge=0, le=20)
    acting_participant: PartyRole | None = None
    active_question_id: Identifier | None = None
    active_clarification_id: Identifier | None = None
    target_item_key: Identifier | None = None
    required_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)
    optional_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)


class LiveSessionView(StrictModel):
    id: Identifier
    stage: LiveSessionStage
    created_at: datetime
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(default_factory=list, max_length=80)
    revision: int = Field(default=0, ge=0)
    participation_mode: LiveParticipationMode = LiveParticipationMode.SAME_DEVICE
    currency: CurrencyCode = CurrencyCode.INR
    creator_role: PartyRole = PartyRole.HIRER
    participant_readiness: dict[PartyRole, bool] = Field(default_factory=dict)
    conversation_reentry_item_key: Identifier | None = None
    viewer_role: PartyRole | None = None
    participant_presence: list[ParticipantPresence] = Field(default_factory=list)
    audio_consents: dict[PartyRole, AudioConsent] = Field(default_factory=dict)
    audio_duration_seconds: dict[PartyRole, float] = Field(default_factory=dict)
    audio_configuration: AudioTranscriptionConfiguration
    agreement_versions: list[AgreementVersion] = Field(default_factory=list)
    current_agreement_version_id: Identifier | None = None
    questions: list[UnderstandingQuestion] = Field(default_factory=list)
    understanding_reviews: dict[PartyRole, ParticipantUnderstandingReview] = Field(
        default_factory=dict
    )
    active_participant_id: PartyRole | None = None
    confirmations: list[ConfirmationRecord] = Field(default_factory=list)
    receipt_id: Identifier | None = None
    receipt_ready: bool = False
    clarification_attempt_limit: int = Field(ge=1, le=10)
    guidance: LiveWorkflowGuidance

    @property
    def current_version(self) -> AgreementVersion | None:
        return next(
            (
                version
                for version in self.agreement_versions
                if version.id == self.current_agreement_version_id
            ),
            None,
        )


class LiveSessionCreateResult(LiveSessionView):
    access_credentials: list[LiveAccessCredential] = Field(min_length=1, max_length=2)
    invitation: LiveInvitation | None = None


class DraftStatementSubmission(StrictModel):
    original_text: str = Field(min_length=2, max_length=2000)
    request_id: Identifier


class AudioConsentSubmission(StrictModel):
    accepted: bool
    notice_version: str = Field(min_length=1, max_length=80)
    expected_revision: int = Field(ge=1)
    request_id: Identifier

    @model_validator(mode="after")
    def require_acceptance(self) -> AudioConsentSubmission:
        if not self.accepted:
            raise ValueError("audio transcription consent must be accepted")
        return self


class FinalizedAudioTranscriptSubmission(StrictModel):
    raw_transcript: str = Field(min_length=2, max_length=20000)
    corrected_text: str | None = Field(default=None, min_length=2, max_length=20000)
    started_at: datetime
    completed_at: datetime
    duration_seconds: float = Field(gt=0, le=3600)
    transcription_model: str = Field(min_length=1, max_length=120)
    consent_id: Identifier
    expected_revision: int = Field(ge=1)
    request_id: Identifier

    @model_validator(mode="after")
    def validate_timing(self) -> FinalizedAudioTranscriptSubmission:
        if self.completed_at <= self.started_at:
            raise ValueError("audio completion must follow its start")
        return self


class ParticipantReadinessSubmission(StrictModel):
    ready: bool
    request_id: Identifier


class ConversationReentrySubmission(StrictModel):
    expected_agreement_version_id: Identifier
    item_key: Identifier | None = None
    request_id: Identifier


class ConfirmationStatusView(StrictModel):
    session_id: Identifier
    stage: LiveSessionStage
    current_agreement_version_id: Identifier | None = None
    confirmations: list[ConfirmationRecord] = Field(default_factory=list, max_length=2)
    receipt_ready: bool = False


class AnalyzeLiveSessionSubmission(StrictModel):
    expected_agreement_version_id: Identifier | None = None


class AdditionalStatementsSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    messages: list[AnalysisMessage] = Field(min_length=1, max_length=20)
    request_id: Identifier


class NotApplicableProposalSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    item_key: Identifier
    request_id: Identifier


class OptionalDetailsReviewedSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    request_id: Identifier


class StartUnderstandingCheckSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    acknowledged_unresolved_item_keys: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    request_id: Identifier


class ConfirmationSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    understanding_review_id: Identifier
    decision: ConfirmationDecision
    unresolved_item_acknowledgments: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    change_item_key: Identifier | None = None
    request_id: Identifier

    @model_validator(mode="after")
    def change_requires_item(self) -> ConfirmationSubmission:
        if self.decision == ConfirmationDecision.REQUEST_CHANGE:
            if self.change_item_key is None:
                raise ValueError("change requests require an agreement item")
        elif self.change_item_key is not None:
            raise ValueError("confirmed understanding cannot include a change item")
        return self


class IssueReceiptSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    request_id: Identifier
