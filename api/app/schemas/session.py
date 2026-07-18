from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.analysis import (
    AgreementTerm,
    ClarificationQuestion,
    LanguageCode,
    PartyRole,
    SessionMode,
)
from app.schemas.workflow import CurrencyCode


class ConsentStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


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
    currency: CurrencyCode = CurrencyCode.INR


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
    order: int = Field(ge=1)
    timestamp: datetime
    translations: dict[LanguageCode, str] = Field(default_factory=dict)


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
    currency: CurrencyCode = CurrencyCode.INR


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
    currency: CurrencyCode = CurrencyCode.INR
    participants: list[SessionParticipant]
    consent: dict[PartyRole, ConsentStatus]
    transcript: list[TranscriptTurn]
    terms: list[AgreementTerm]
    clarification_questions: list[ClarificationQuestion]
    confirmations: list[PartyConfirmation]
