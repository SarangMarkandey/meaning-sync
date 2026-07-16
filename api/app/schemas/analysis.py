from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SessionMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class PartyRole(StrEnum):
    HIRER = "hirer"
    WORKER = "worker"


class LanguageCode(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"


class AgreementTopic(StrEnum):
    SCOPE = "scope"
    PRICE = "price"
    MATERIALS = "materials"
    TIMING = "timing"
    COMPLETION = "completion"
    PAYMENT = "payment"
    RESPONSIBILITIES = "responsibilities"
    WARRANTY = "warranty"
    CANCELLATION = "cancellation"
    ADDITIONAL_WORK = "additional_work"
    OTHER = "other"


class AgreementFacet(StrEnum):
    WORK = "work"
    AMOUNT = "amount"
    INCLUSION = "inclusion"
    START = "start"
    DEADLINE = "deadline"
    TIMING = "timing"
    ASSIGNMENT = "assignment"
    COVERAGE = "coverage"
    POLICY = "policy"
    DETAIL = "detail"


class MeaningState(StrEnum):
    ALIGNED = "aligned"
    CONFLICTING = "conflicting"
    STATED_BY_ONE = "stated_by_one"
    NOT_DISCUSSED = "not_discussed"


class ParticipantTermStatus(StrEnum):
    CONFIRMED = "confirmed"
    CONFLICTING = "conflicting"
    STATED = "stated"
    NOT_STATED = "not_stated"


class AnalysisErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    CONFIGURATION_ERROR = "configuration_error"
    INVALID_API_KEY = "invalid_api_key"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    REFUSED = "refused"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    PROVIDER_ERROR = "provider_error"


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class AnalysisWarningCode(StrEnum):
    CLARIFICATION_UNAVAILABLE = "clarification_unavailable"


Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[\w.-]+$")]


class AnalysisParticipant(StrictModel):
    id: Identifier
    role: PartyRole
    language: LanguageCode


class AnalysisMessage(StrictModel):
    message_id: Identifier
    speaker_id: Identifier
    original_text: str = Field(min_length=2, max_length=2000)
    original_language: LanguageCode
    order: int = Field(ge=1, le=40)
    timestamp: datetime


class ParticipantPosition(StrictModel):
    participant_id: Identifier
    role: PartyRole
    summary: str = Field(min_length=1, max_length=500)
    evidence_message_ids: list[Identifier] = Field(min_length=1, max_length=20)


class EvidenceReference(StrictModel):
    source: Literal["transcript", "clarification"]
    reference_id: str = Field(min_length=1, max_length=160)
    participant_id: Identifier
    role: PartyRole
    speaker_name: str = Field(min_length=1, max_length=80)
    message_id: Identifier | None = None
    original_text: str = Field(min_length=1, max_length=2000)
    original_language: LanguageCode
    order: int | None = Field(default=None, ge=1, le=40)
    timestamp: datetime | None = None

    @model_validator(mode="after")
    def transcript_evidence_requires_message(self) -> EvidenceReference:
        if self.source == "transcript" and (
            self.message_id is None or self.order is None or self.timestamp is None
        ):
            raise ValueError(
                "transcript evidence requires message ID, order, and timestamp"
            )
        return self


class AgreementTerm(StrictModel):
    id: Identifier
    analysis_item_key: Identifier
    topic: AgreementTopic
    facet: AgreementFacet
    label: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=600)
    state: MeaningState
    participant_positions: list[ParticipantPosition] = Field(
        default_factory=list, max_length=2
    )
    participant_confirmations: dict[PartyRole, ParticipantTermStatus]
    evidence_message_ids: list[Identifier] = Field(default_factory=list, max_length=40)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=40)
    clarification_target: Identifier | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> AgreementTerm:
        if self.analysis_item_key != f"{self.topic.value}.{self.facet.value}":
            raise ValueError("analysis item key must match the term topic and facet")
        if self.clarification_target not in {None, self.analysis_item_key}:
            raise ValueError("clarification target must identify this exact term")
        if set(self.participant_confirmations) != set(PartyRole):
            raise ValueError("term status is required for both participant roles")

        transcript_ids = {
            item.message_id
            for item in self.evidence
            if item.source == "transcript" and item.message_id is not None
        }
        if transcript_ids != set(self.evidence_message_ids):
            raise ValueError("evidence message IDs must match hydrated evidence")

        if self.state == MeaningState.NOT_DISCUSSED:
            if self.evidence or self.evidence_message_ids or self.participant_positions:
                raise ValueError(
                    "not-discussed terms cannot contain evidence or positions"
                )
        elif not self.evidence_message_ids or not self.evidence:
            raise ValueError("discussed terms require transcript evidence")

        if self.state == MeaningState.ALIGNED and any(
            status != ParticipantTermStatus.CONFIRMED
            for status in self.participant_confirmations.values()
        ):
            raise ValueError("aligned terms require both participants to be confirmed")
        return self


class ClarificationQuestion(StrictModel):
    id: Identifier
    term_id: Identifier
    target_item_key: Identifier
    target: AgreementTopic
    facet: AgreementFacet
    evidence_message_ids: list[Identifier] = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=8)


class AgreementAnalysisRequest(StrictModel):
    session_id: Identifier
    mode: SessionMode
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(min_length=2, max_length=40)

    @model_validator(mode="after")
    def validate_conversation(self) -> AgreementAnalysisRequest:
        participant_ids = [participant.id for participant in self.participants]
        roles = [participant.role for participant in self.participants]
        if len(set(participant_ids)) != 2:
            raise ValueError("participant IDs must be unique")
        if set(roles) != set(PartyRole):
            raise ValueError("participants must include one hirer and one worker")
        if any(
            participant.language != LanguageCode.ENGLISH
            for participant in self.participants
        ):
            raise ValueError("this milestone supports English participants only")

        messages_by_id = {message.message_id: message for message in self.messages}
        if len(messages_by_id) != len(self.messages):
            raise ValueError("message IDs must be unique")
        orders = [message.order for message in self.messages]
        if orders != sorted(orders) or len(set(orders)) != len(orders):
            raise ValueError("messages must have unique chronological order values")

        participant_by_id = {
            participant.id: participant for participant in self.participants
        }
        speakers = set()
        for message in self.messages:
            participant = participant_by_id.get(message.speaker_id)
            if participant is None:
                raise ValueError("every message speaker must be a participant")
            if message.original_language != participant.language:
                raise ValueError("message language must match its participant language")
            speakers.add(message.speaker_id)
        if speakers != set(participant_ids):
            raise ValueError("each participant must provide at least one statement")
        return self


class AnalysisWarning(StrictModel):
    code: AnalysisWarningCode
    message: str = Field(min_length=1, max_length=300)


class AgreementAnalysisResponse(StrictModel):
    session_id: Identifier
    mode: SessionMode
    prompt_version: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    status: AnalysisStatus = AnalysisStatus.COMPLETE
    warnings: list[AnalysisWarning] = Field(default_factory=list, max_length=4)
    terms: list[AgreementTerm] = Field(min_length=1, max_length=20)
    primary_clarification: ClarificationQuestion | None = None


class AnalysisErrorDetail(StrictModel):
    code: AnalysisErrorCode
    message: str
    retryable: bool


class AnalysisErrorResponse(StrictModel):
    detail: AnalysisErrorDetail


class ModelParticipantPosition(StrictModel):
    participant_id: Identifier
    summary: str = Field(min_length=1, max_length=500)
    evidence_message_ids: list[Identifier] = Field(min_length=1, max_length=20)


class ModelAgreementTerm(StrictModel):
    item_key: Identifier
    topic: AgreementTopic
    facet: AgreementFacet
    neutral_summary: str = Field(min_length=1, max_length=600)
    state: MeaningState
    participant_positions: list[ModelParticipantPosition] = Field(
        default_factory=list, max_length=2
    )
    evidence_message_ids: list[Identifier] = Field(default_factory=list, max_length=40)
    clarification_question: str | None = Field(default=None, max_length=500)


class AgreementAnalysisModelOutput(StrictModel):
    terms: list[ModelAgreementTerm] = Field(min_length=1, max_length=20)
