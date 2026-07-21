from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict, Field, model_validator

from app.schemas.analysis import Identifier, LanguageCode, PartyRole, StrictModel


class FrozenUnderstandingModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )


class UnderstandingQuestionKind(StrEnum):
    CLARIFICATION = "clarification"
    UNDERSTANDING_CHECK = "understanding_check"


class UnderstandingOptionKind(StrEnum):
    RECORDED_POSITION = "recorded_position"
    RECORDED_MEANING = "recorded_meaning"
    OTHER = "other"
    UNSURE = "unsure"


class UnderstandingQuestionStatus(StrEnum):
    PENDING = "pending"
    PARTIALLY_ANSWERED = "partially_answered"
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSURE = "unsure"
    LEFT_UNRESOLVED = "left_unresolved"


class UnderstandingOutcomeState(StrEnum):
    ALIGNED = "aligned"
    MEANING_CHANGED = "meaning_changed"
    DIFFERENT = "different"
    UNSURE = "unsure"
    LEFT_UNRESOLVED = "left_unresolved"


class UnderstandingEvidenceSource(StrEnum):
    CONVERSATION = "conversation"
    CLARIFICATION = "clarification"
    UNDERSTANDING_CHECK = "understanding_check"
    FINAL_CONFIRMATION = "final_confirmation"


class UnderstandingReviewResult(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"


class UnderstandingOption(FrozenUnderstandingModel):
    id: Identifier
    label: str = Field(min_length=1, max_length=600)
    kind: UnderstandingOptionKind
    localizations: dict[LanguageCode, str] = Field(default_factory=dict, max_length=2)


class UnderstandingOutcomePosition(FrozenUnderstandingModel):
    participant_id: PartyRole
    option_id: Identifier
    label: str = Field(min_length=1, max_length=600)
    other_text: str | None = Field(default=None, min_length=2, max_length=280)


class UnderstandingQuestionOutcome(FrozenUnderstandingModel):
    state: UnderstandingOutcomeState
    positions: list[UnderstandingOutcomePosition] = Field(
        default_factory=list, max_length=2
    )
    resulting_agreement_version_id: Identifier | None = None


class UnderstandingQuestion(FrozenUnderstandingModel):
    id: Identifier
    session_id: Identifier
    agreement_version_id: Identifier
    agreement_item_id: Identifier
    kind: UnderstandingQuestionKind
    prompt: str = Field(min_length=1, max_length=500)
    options: list[UnderstandingOption] = Field(min_length=3, max_length=4)
    evidence_reference_ids: list[str] = Field(default_factory=list, max_length=40)
    addressed_participant_ids: list[PartyRole] = Field(min_length=1, max_length=2)
    answered_participant_ids: list[PartyRole] = Field(
        default_factory=list, max_length=2
    )
    responses_revealed: bool = False
    status: UnderstandingQuestionStatus
    question_number: int = Field(ge=1, le=3)
    question_count: int = Field(ge=1, le=3)
    outcome: UnderstandingQuestionOutcome | None = None
    prompt_localizations: dict[LanguageCode, str] = Field(
        default_factory=dict, max_length=2
    )

    @model_validator(mode="after")
    def validate_question(self) -> UnderstandingQuestion:
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("understanding option IDs must be unique")
        option_kinds = [option.kind for option in self.options]
        if option_kinds.count(UnderstandingOptionKind.OTHER) != 1:
            raise ValueError("every question requires one other option")
        if option_kinds.count(UnderstandingOptionKind.UNSURE) != 1:
            raise ValueError("every question requires one unsure option")
        if len(self.addressed_participant_ids) != len(
            set(self.addressed_participant_ids)
        ):
            raise ValueError("addressed participant IDs must be unique")
        if not set(self.answered_participant_ids).issubset(
            set(self.addressed_participant_ids)
        ):
            raise ValueError("only addressed participants may answer a question")
        if self.question_number > self.question_count:
            raise ValueError("question number cannot exceed question count")
        if self.responses_revealed and self.outcome is None:
            raise ValueError("revealed responses require an outcome")
        if not self.responses_revealed and self.outcome is not None:
            raise ValueError("a hidden response cannot include an outcome")
        return self


class ParticipantSelection(FrozenUnderstandingModel):
    id: Identifier
    participant_id: PartyRole
    question_id: Identifier
    agreement_version_id: Identifier
    option_id: Identifier
    option_kind: UnderstandingOptionKind
    semantic_value: str = Field(min_length=1, max_length=600)
    other_text: str | None = Field(default=None, min_length=2, max_length=280)
    submitted_at: datetime
    request_id: Identifier

    @model_validator(mode="after")
    def validate_other_text(self) -> ParticipantSelection:
        if self.option_kind == UnderstandingOptionKind.OTHER:
            if self.other_text is None:
                raise ValueError("the other option requires a short explanation")
        elif self.other_text is not None:
            raise ValueError("other text is allowed only for the other option")
        return self


class IndependentMeaningEvidence(FrozenUnderstandingModel):
    id: Identifier
    session_id: Identifier
    agreement_version_id: Identifier
    agreement_item_id: Identifier
    semantic_target: Identifier
    semantic_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: UnderstandingEvidenceSource
    participant_ids: list[PartyRole] = Field(min_length=1, max_length=2)
    evidence_reference_ids: list[str] = Field(default_factory=list, max_length=40)
    created_at: datetime


class UnderstandingSelectionSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    option_id: Identifier
    other_text: str | None = Field(default=None, min_length=2, max_length=280)
    request_id: Identifier


class LeaveQuestionUnresolvedSubmission(StrictModel):
    expected_agreement_version_id: Identifier
    participant_id: PartyRole
    request_id: Identifier
