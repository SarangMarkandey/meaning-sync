from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.analysis import (
    AnalysisMessage,
    AnalysisParticipant,
    PartyRole,
    StrictModel,
)
from app.schemas.understanding import (
    IndependentMeaningEvidence,
    ParticipantSelection,
    UnderstandingQuestion,
)
from app.schemas.workflow import (
    AgreementVersion,
    AudioConsent,
    ConfirmationRecord,
    CurrencyCode,
    LiveClarityReceipt,
    LiveParticipationMode,
    LiveSessionStage,
    ParticipantUnderstandingReview,
)


class PersistedQuestionRecord(StrictModel):
    question: UnderstandingQuestion
    semantic_target: str = Field(min_length=1, max_length=240)
    semantic_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    option_semantics: dict[str, str] = Field(default_factory=dict)
    selections: dict[PartyRole, ParticipantSelection] = Field(default_factory=dict)
    unresolved_acknowledgments: set[PartyRole] = Field(default_factory=set)
    response_message_ids: dict[PartyRole, str] = Field(default_factory=dict)
    attempt_number: int = Field(default=1, ge=1, le=10)


class PersistedLiveSessionState(StrictModel):
    state_schema_version: Literal[1, 2, 3, 4] = 4
    id: str = Field(min_length=1, max_length=120)
    created_at: datetime
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(default_factory=list, max_length=80)
    participation_mode: LiveParticipationMode = LiveParticipationMode.SAME_DEVICE
    currency: CurrencyCode = CurrencyCode.INR
    creator_role: PartyRole = PartyRole.HIRER
    participant_readiness: dict[PartyRole, bool] = Field(
        default_factory=lambda: {role: False for role in PartyRole}
    )
    audio_consents: dict[PartyRole, AudioConsent] = Field(default_factory=dict)
    audio_duration_seconds: dict[PartyRole, float] = Field(
        default_factory=lambda: {role: 0.0 for role in PartyRole}
    )
    conversation_reentry_item_key: str | None = None
    stage: LiveSessionStage = LiveSessionStage.CONVERSATION_DRAFT
    versions: list[AgreementVersion] = Field(default_factory=list)
    current_version_id: str | None = None
    questions: list[PersistedQuestionRecord] = Field(default_factory=list)
    understanding_reviews: dict[PartyRole, ParticipantUnderstandingReview] = Field(
        default_factory=dict
    )
    active_participant_id: PartyRole | None = None
    confirmations: list[ConfirmationRecord] = Field(default_factory=list)
    evidence_ledger: list[IndependentMeaningEvidence] = Field(default_factory=list)
    receipt: LiveClarityReceipt | None = None
    processed_requests: dict[str, str] = Field(default_factory=dict)
    optional_details_reviewed: bool = False
