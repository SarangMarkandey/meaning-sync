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


class ConsentStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class TermStatus(StrEnum):
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"
    MISSING = "missing"


class SessionStage(StrEnum):
    CREATED = "created"
    CONSENT_PENDING = "consent_pending"
    DISCUSSION = "discussion"
    ANALYZED = "analyzed"
    CLARIFICATION = "clarification"
    TEACHBACK = "teachback"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


class TranscriptTurn(BaseModel):
    id: str
    speaker: PartyRole
    speaker_name: str
    language: Literal["en", "hi", "hinglish"]
    text: str


class EvidenceReference(BaseModel):
    source: Literal["transcript", "clarification"]
    reference_id: str
    excerpt: str


class AgreementTerm(BaseModel):
    id: str
    label: str
    status: TermStatus
    value: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_for_non_missing_term(self) -> AgreementTerm:
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
    consent: dict[PartyRole, ConsentStatus]
    transcript: list[TranscriptTurn]
    terms: list[AgreementTerm]
    clarification_questions: list[ClarificationQuestion]
    confirmations: list[PartyConfirmation]
