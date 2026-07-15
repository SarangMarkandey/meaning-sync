from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SessionMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class PartyRole(StrEnum):
    HIRER = "hirer"
    WORKER = "worker"


class LanguageCode(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"


class ConsentStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class TermStatus(StrEnum):
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"
    MISSING = "missing"


class ParticipantTermStatus(StrEnum):
    CONFIRMED = "confirmed"
    CONFLICTING = "conflicting"
    NOT_STATED = "not_stated"


class MaterialsPolicy(StrEnum):
    INCLUDED = "included"
    CHARGED_SEPARATELY = "charged_separately"


class SessionStage(StrEnum):
    CREATED = "created"
    CONSENT_PENDING = "consent_pending"
    DISCUSSION = "discussion"
    ANALYZED = "analyzed"
    CLARIFICATION = "clarification"
    TEACHBACK = "teachback"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


class ParticipantLanguages(BaseModel):
    hirer: LanguageCode = LanguageCode.ENGLISH
    worker: LanguageCode = LanguageCode.ENGLISH


class DemoSessionCreate(BaseModel):
    participant_languages: ParticipantLanguages = Field(
        default_factory=ParticipantLanguages
    )


class SessionParticipant(BaseModel):
    id: PartyRole
    role: PartyRole
    display_name: str
    language: LanguageCode
    requested_display_language: LanguageCode


class TranscriptTurn(BaseModel):
    id: str
    session_id: str
    participant_id: PartyRole
    speaker: PartyRole
    speaker_name: str
    original_text: str
    original_language: LanguageCode
    timestamp: datetime
    translations: dict[LanguageCode, str] = Field(default_factory=dict)


class EvidenceReference(BaseModel):
    source: Literal["transcript", "clarification"]
    reference_id: str
    participant_id: PartyRole
    message_id: str | None = None
    original_text: str

    @model_validator(mode="after")
    def transcript_evidence_requires_message(self) -> EvidenceReference:
        if self.source == "transcript" and not self.message_id:
            raise ValueError("transcript evidence requires a supporting message ID")
        return self


class AgreementTerm(BaseModel):
    id: str
    label: str
    status: TermStatus
    value: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    participant_confirmations: dict[PartyRole, ParticipantTermStatus]

    @model_validator(mode="after")
    def validate_provenance(self) -> AgreementTerm:
        if set(self.participant_confirmations) != set(PartyRole):
            raise ValueError("term status is required for both participants")
        if self.status != TermStatus.MISSING and not self.evidence:
            raise ValueError("non-missing agreement terms require evidence")
        if self.status == TermStatus.MISSING and self.evidence:
            raise ValueError("missing agreement terms cannot cite evidence")
        return self


class ClarificationQuestion(BaseModel):
    id: str
    term_id: str
    prompt: str
    options: list[str]


class ClarificationAnswer(BaseModel):
    question_id: str
    party: PartyRole
    answer: str
    meaning: MaterialsPolicy
    submitted_at: datetime


class PartyConfirmation(BaseModel):
    party: PartyRole
    confirmed: bool
    teachback: str = Field(min_length=1, max_length=500)
    submitted_at: datetime


class ClarityReceipt(BaseModel):
    session_id: str
    title: str = "MeaningSync Clarity Receipt"
    disclaimer: str = "MeaningSync Clarity Receipt — not a legal contract."
    terms: list[AgreementTerm]
    confirmations: list[PartyConfirmation]
    completed_at: datetime


class ConsentSubmission(BaseModel):
    party: PartyRole
    accepted: bool


class ClarificationAnswerSubmission(BaseModel):
    party: PartyRole
    answer: str = Field(min_length=1, max_length=200)


class ConfirmationSubmission(BaseModel):
    party: PartyRole
    confirmed: bool
    teachback: str = Field(min_length=1, max_length=500)


class ClarificationResult(BaseModel):
    question: ClarificationQuestion
    revealed: bool
    answers: list[ClarificationAnswer] = Field(default_factory=list)
    resolved: bool = False
    term: AgreementTerm | None = None


class SessionView(BaseModel):
    id: str
    mode: SessionMode
    stage: SessionStage
    created_at: datetime
    participants: list[SessionParticipant]
    consent: dict[PartyRole, ConsentStatus]
    transcript: list[TranscriptTurn]
    terms: list[AgreementTerm]
    clarification_questions: list[ClarificationQuestion]
    confirmations: list[PartyConfirmation]
