from __future__ import annotations

from datetime import datetime
from enum import StrEnum

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
from app.schemas.teachback import TeachbackComparisonState, TeachbackItemResult


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
    READY_FOR_REVIEW = "ready_for_review"
    AWAITING_TEACHBACKS = "awaiting_teachbacks"
    AWAITING_CONFIRMATIONS = "awaiting_confirmations"
    CONFIRMED = "confirmed"
    RECEIPT_ISSUED = "receipt_issued"


class ClarificationWorkflowStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    STILL_UNRESOLVED = "still_unresolved"
    LEFT_UNRESOLVED = "left_unresolved"


class LiveUserStage(StrEnum):
    CONVERSATION = "conversation"
    CLARIFY = "clarify"
    REVIEW = "review"
    CONFIRM = "confirm"
    RECEIPT = "receipt"


class LiveGuidanceAction(StrEnum):
    ANSWER_CLARIFICATION = "answer_clarification"
    LEAVE_UNRESOLVED = "leave_unresolved"
    REVIEW_OPTIONAL_DETAILS = "review_optional_details"
    REVIEW_FINAL_UNDERSTANDING = "review_final_understanding"
    SUBMIT_TEACHBACK = "submit_teachback"
    SUBMIT_CONFIRMATION = "submit_confirmation"
    ISSUE_RECEIPT = "issue_receipt"
    VIEW_RECEIPT = "view_receipt"


class ParticipantReviewStatus(StrEnum):
    NOT_STARTED = "not_started"
    REVIEWING = "reviewing"
    TEACHBACK_SUBMITTED = "teachback_submitted"
    NEEDS_CLARIFICATION = "needs_clarification"
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
    STALE_AGREEMENT_VERSION = "stale_agreement_version"
    CLARIFICATION_TARGET_MISSING = "clarification_target_missing"
    CLARIFICATION_LIMIT_REACHED = "clarification_limit_reached"
    PARTICIPANT_MISMATCH = "participant_mismatch"
    TEACHBACK_INCOMPLETE = "teachback_incomplete"
    TEACHBACK_MISMATCH = "teachback_mismatch"
    CONFIRMATION_MISSING = "confirmation_missing"
    CONFIRMATION_VERSION_MISMATCH = "confirmation_version_mismatch"
    RECEIPT_NOT_READY = "receipt_not_ready"


class WorkflowErrorDetail(StrictModel):
    code: WorkflowErrorCode
    message: str = Field(min_length=1, max_length=400)
    retryable: bool = False
    current_agreement_version_id: Identifier | None = None


class WorkflowErrorResponse(StrictModel):
    detail: WorkflowErrorDetail


class LiveSessionCreate(StrictModel):
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(min_length=2, max_length=40)


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


class ClarificationWorkflowRecord(FrozenWorkflowModel):
    id: Identifier
    target_item_key: Identifier
    target_agreement_version_id: Identifier
    term_id: Identifier
    question: str = Field(min_length=1, max_length=500)
    answer_options: list[str] = Field(default_factory=list, max_length=8)
    fingerprint: str = Field(default="legacy", min_length=1, max_length=80)
    semantic_target: Identifier = "legacy.target"
    addressed_participant_ids: list[PartyRole] = Field(min_length=1, max_length=2)
    response_message_ids: dict[PartyRole, Identifier] = Field(default_factory=dict)
    answers_received_from: list[PartyRole] = Field(default_factory=list, max_length=2)
    responses_revealed: bool = False
    status: ClarificationWorkflowStatus
    attempt_number: int = Field(ge=1, le=20)
    created_at: datetime
    resolved_at: datetime | None = None
    resulting_agreement_version_id: Identifier | None = None


class ParticipantReview(FrozenWorkflowModel):
    participant_id: PartyRole
    agreement_version_id: Identifier
    status: ParticipantReviewStatus
    teachback_id: Identifier | None = None


class TeachbackRecord(FrozenWorkflowModel):
    id: Identifier
    participant_id: PartyRole
    agreement_version_id: Identifier
    original_text: str = Field(min_length=1, max_length=40000, exclude=True)
    original_language: LanguageCode
    covered_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)
    item_results: list[TeachbackItemResult] = Field(default_factory=list, max_length=20)
    overall_state: TeachbackComparisonState
    missing_or_contradictory_summary: str | None = Field(default=None, max_length=600)
    follow_up_question: str | None = Field(default=None, max_length=500)
    acknowledged_unresolved_item_keys: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    created_at: datetime


class ConfirmationRecord(FrozenWorkflowModel):
    id: Identifier
    participant_id: PartyRole
    agreement_version_id: Identifier
    teachback_id: Identifier
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


class ReceiptTeachbackStatus(FrozenWorkflowModel):
    participant_id: PartyRole
    teachback_id: Identifier
    result: TeachbackComparisonState
    completed_at: datetime


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
    participants: list[ReceiptParticipant] = Field(min_length=2, max_length=2)
    aligned_terms: list[AgreementTerm]
    unresolved_terms: list[AgreementTerm]
    one_sided_terms: list[AgreementTerm]
    not_applicable_terms: list[NotApplicableProposal]
    not_discussed_terms: list[AgreementTerm]
    clarification_history: list[ClarificationHistoryEntry]
    teachback_status: list[ReceiptTeachbackStatus] = Field(min_length=2, max_length=2)
    confirmations: list[ReceiptConfirmation] = Field(min_length=2, max_length=2)
    status: ReceiptStatus
    application_version: str = "0.3.0"
    schema_version: str = "clarity-receipt-v1"
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
    active_clarification_id: Identifier | None = None
    target_item_key: Identifier | None = None
    required_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)
    optional_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)


class LiveSessionView(StrictModel):
    id: Identifier
    stage: LiveSessionStage
    created_at: datetime
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(min_length=2, max_length=80)
    agreement_versions: list[AgreementVersion] = Field(default_factory=list)
    current_agreement_version_id: Identifier | None = None
    clarifications: list[ClarificationWorkflowRecord] = Field(default_factory=list)
    reviews: dict[PartyRole, ParticipantReview] = Field(default_factory=dict)
    active_participant_id: PartyRole | None = None
    teachbacks: list[TeachbackRecord] = Field(default_factory=list)
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


class ConfirmationStatusView(StrictModel):
    session_id: Identifier
    stage: LiveSessionStage
    current_agreement_version_id: Identifier | None = None
    confirmations: list[ConfirmationRecord] = Field(default_factory=list, max_length=2)
    receipt_ready: bool = False


class AnalyzeLiveSessionSubmission(StrictModel):
    expected_agreement_version_id: Identifier | None = None


class ClarificationAnswerSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    answer: str = Field(min_length=2, max_length=2000)
    request_id: Identifier


class AdditionalStatementsSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    messages: list[AnalysisMessage] = Field(min_length=1, max_length=20)
    request_id: Identifier


class NotApplicableProposalSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    item_key: Identifier
    request_id: Identifier


class LeaveClarificationUnresolvedSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    request_id: Identifier


class OptionalDetailsReviewedSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    request_id: Identifier


class StartReviewSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    acknowledged_unresolved_item_keys: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    request_id: Identifier


class TeachbackSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    text: str = Field(min_length=2, max_length=4000)
    original_language: LanguageCode = LanguageCode.ENGLISH
    acknowledged_unresolved_item_keys: list[Identifier] = Field(
        default_factory=list, max_length=20
    )
    request_id: Identifier


class ConfirmationSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    teachback_id: Identifier
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
