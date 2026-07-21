from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class MessageInputSource(StrEnum):
    TEXT = "text"
    AUDIO_TRANSCRIPT = "audio_transcript"


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


class TranslationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class SemanticEquivalenceStatus(StrEnum):
    EQUIVALENT = "equivalent"
    REVIEW_REQUIRED = "review_required"


class AnalysisWarningCode(StrEnum):
    CLARIFICATION_UNAVAILABLE = "clarification_unavailable"


Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[\w.-]+$")]


class AnalysisParticipant(StrictModel):
    id: Identifier
    role: PartyRole
    language: LanguageCode
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class MessageTranslation(StrictModel):
    source_language: LanguageCode
    target_language: LanguageCode
    status: TranslationStatus
    translated_text: str | None = Field(default=None, min_length=1, max_length=2000)
    semantic_equivalence_status: SemanticEquivalenceStatus | None = None
    preserved_amounts: list[str] = Field(default_factory=list, max_length=20)
    preserved_currencies: list[str] = Field(default_factory=list, max_length=20)
    preserved_dates: list[str] = Field(default_factory=list, max_length=20)
    preserved_quantities: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    model: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=80)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_state(self) -> MessageTranslation:
        if self.source_language == self.target_language:
            if self.status != TranslationStatus.NOT_REQUIRED:
                raise ValueError("same-language translation must be not required")
        elif self.status == TranslationStatus.READY:
            if (
                self.translated_text is None
                or self.semantic_equivalence_status
                != SemanticEquivalenceStatus.EQUIVALENT
            ):
                raise ValueError(
                    "ready translation requires equivalent translated text"
                )
        elif self.translated_text is not None:
            raise ValueError("unready translation cannot publish translated text")
        return self


class AnalysisMessage(StrictModel):
    message_id: Identifier
    speaker_id: Identifier
    original_text: str = Field(min_length=2, max_length=2000)
    original_language: LanguageCode
    order: int = Field(ge=1, le=40)
    timestamp: datetime
    input_source: MessageInputSource = MessageInputSource.TEXT
    raw_transcript: str | None = Field(default=None, min_length=2, max_length=2000)
    corrected_text: str | None = Field(default=None, min_length=2, max_length=2000)
    effective_text: str | None = Field(default=None, min_length=2, max_length=2000)
    transcription_model: str | None = Field(default=None, min_length=1, max_length=120)
    transcription_request_id: Identifier | None = None
    consent_id: Identifier | None = None
    audio_started_at: datetime | None = None
    audio_completed_at: datetime | None = None
    audio_duration_seconds: float | None = Field(default=None, gt=0, le=3600)
    translations: dict[LanguageCode, MessageTranslation] = Field(
        default_factory=dict, max_length=1
    )

    @model_validator(mode="after")
    def validate_provenance(self) -> AnalysisMessage:
        effective = self.corrected_text or self.raw_transcript or self.original_text
        if self.effective_text is None:
            self.effective_text = effective
        if self.original_text != effective or self.effective_text != effective:
            raise ValueError("original and effective text must match the analyzed text")
        audio_fields = (
            self.raw_transcript,
            self.transcription_model,
            self.transcription_request_id,
            self.consent_id,
            self.audio_started_at,
            self.audio_completed_at,
            self.audio_duration_seconds,
        )
        if self.input_source == MessageInputSource.TEXT:
            if self.corrected_text is not None or any(
                item is not None for item in audio_fields
            ):
                raise ValueError("typed messages cannot contain audio provenance")
        elif any(item is None for item in audio_fields):
            raise ValueError("audio transcripts require complete provenance")
        elif self.audio_completed_at <= self.audio_started_at:
            raise ValueError("audio completion must follow its start")
        if any(
            target != translation.target_language
            or translation.source_language != self.original_language
            for target, translation in self.translations.items()
        ):
            raise ValueError("translation keys and languages must match the message")
        return self


class ParticipantPosition(StrictModel):
    participant_id: Identifier
    role: PartyRole
    summary: str = Field(min_length=1, max_length=500)
    evidence_message_ids: list[Identifier] = Field(min_length=1, max_length=20)


class LocalizedParticipantPosition(StrictModel):
    participant_id: Identifier
    summary: str = Field(min_length=1, max_length=500)


class AgreementTermLocalization(StrictModel):
    language: LanguageCode
    label: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=600)
    participant_positions: list[LocalizedParticipantPosition] = Field(
        default_factory=list, max_length=2
    )
    provenance: str = Field(default="deterministic", min_length=1, max_length=120)


class EvidenceReference(StrictModel):
    source: Literal["transcript", "clarification", "understanding_check"]
    reference_id: str = Field(min_length=1, max_length=160)
    participant_id: Identifier
    role: PartyRole
    speaker_name: str = Field(min_length=1, max_length=80)
    message_id: Identifier | None = None
    original_text: str = Field(min_length=1, max_length=2000)
    original_language: LanguageCode
    order: int | None = Field(default=None, ge=1, le=40)
    timestamp: datetime | None = None
    input_source: MessageInputSource = MessageInputSource.TEXT
    raw_transcript: str | None = Field(default=None, min_length=2, max_length=2000)
    corrected_text: str | None = Field(default=None, min_length=2, max_length=2000)
    transcription_model: str | None = Field(default=None, min_length=1, max_length=120)
    consent_id: Identifier | None = None

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
    localizations: dict[LanguageCode, AgreementTermLocalization] = Field(
        default_factory=dict, max_length=2
    )

    @model_validator(mode="after")
    def validate_contract(self) -> AgreementTerm:
        if self.analysis_item_key != f"{self.topic.value}.{self.facet.value}":
            raise ValueError("analysis item key must match the term topic and facet")
        if self.clarification_target not in {None, self.analysis_item_key}:
            raise ValueError("clarification target must identify this exact term")
        if set(self.participant_confirmations) != set(PartyRole):
            raise ValueError("term status is required for both participant roles")

        referenced_message_ids = {
            item.message_id for item in self.evidence if item.message_id is not None
        }
        if referenced_message_ids != set(self.evidence_message_ids):
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
        if any(
            language != localization.language
            for language, localization in self.localizations.items()
        ):
            raise ValueError("localization keys must match their language")
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


class AnalysisClarificationContext(StrictModel):
    clarification_id: Identifier
    target_item_key: Identifier
    question: str = Field(min_length=1, max_length=500)
    response_message_ids: dict[PartyRole, Identifier] = Field(
        min_length=1, max_length=2
    )


class AgreementAnalysisRequest(StrictModel):
    session_id: Identifier
    mode: SessionMode
    participants: list[AnalysisParticipant] = Field(min_length=2, max_length=2)
    messages: list[AnalysisMessage] = Field(min_length=2, max_length=40)
    clarification_contexts: list[AnalysisClarificationContext] = Field(
        default_factory=list, max_length=10
    )

    @model_validator(mode="after")
    def validate_conversation(self) -> AgreementAnalysisRequest:
        participant_ids = [participant.id for participant in self.participants]
        roles = [participant.role for participant in self.participants]
        if len(set(participant_ids)) != 2:
            raise ValueError("participant IDs must be unique")
        if set(roles) != set(PartyRole):
            raise ValueError("participants must include one hirer and one worker")
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

        seen_clarification_ids: set[str] = set()
        for context in self.clarification_contexts:
            if context.clarification_id in seen_clarification_ids:
                raise ValueError("clarification context IDs must be unique")
            seen_clarification_ids.add(context.clarification_id)
            for role, message_id in context.response_message_ids.items():
                message = messages_by_id.get(message_id)
                if message is None:
                    raise ValueError(
                        "clarification context must reference a supplied message"
                    )
                participant = participant_by_id[message.speaker_id]
                if participant.role != role:
                    raise ValueError(
                        "clarification context response must match its participant"
                    )
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


class ModelLocalizedParticipantPosition(StrictModel):
    participant_id: Identifier
    summary: str = Field(min_length=1, max_length=500)


class ModelAgreementTermLocalization(StrictModel):
    language: LanguageCode
    summary: str = Field(min_length=1, max_length=600)
    participant_positions: list[ModelLocalizedParticipantPosition] = Field(
        default_factory=list, max_length=2
    )


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
    localizations: list[ModelAgreementTermLocalization] = Field(
        default_factory=list, max_length=2
    )


class AgreementAnalysisModelOutput(StrictModel):
    terms: list[ModelAgreementTerm] = Field(min_length=1, max_length=20)
