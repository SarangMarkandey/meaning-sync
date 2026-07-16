from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.analysis import (
    AgreementTerm,
    Identifier,
    LanguageCode,
    MeaningState,
    StrictModel,
)

__all__ = [
    "TeachbackComparisonState",
    "TeachbackErrorCode",
    "TeachbackEvaluation",
    "TeachbackEvaluationRequest",
    "TeachbackItemResult",
]


class TeachbackComparisonState(StrEnum):
    MATCHES = "matches"
    PARTIALLY_MATCHES = "partially_matches"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"


class TeachbackErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    CONFIGURATION_ERROR = "configuration_error"
    INVALID_API_KEY = "invalid_api_key"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    REFUSED = "refused"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    PROVIDER_ERROR = "provider_error"


class TeachbackItemResult(StrictModel):
    analysis_item_key: Identifier
    state: TeachbackComparisonState
    agreement_summary: str = Field(min_length=1, max_length=600)
    feedback: str = Field(min_length=1, max_length=800)


class TeachbackEvaluationRequest(StrictModel):
    participant_id: Identifier
    agreement_version_id: Identifier
    teachback_text: str = Field(min_length=2, max_length=40000)
    original_language: LanguageCode
    reviewed_terms: list[AgreementTerm] = Field(min_length=1, max_length=20)
    required_item_keys: list[Identifier] = Field(min_length=1, max_length=20)
    acknowledged_unresolved_item_keys: list[Identifier] = Field(
        default_factory=list, max_length=20
    )

    @model_validator(mode="after")
    def validate_reviewed_version(self) -> TeachbackEvaluationRequest:
        if self.original_language != LanguageCode.ENGLISH:
            raise ValueError("teach-back comparison currently supports English only")

        reviewed_keys = [term.analysis_item_key for term in self.reviewed_terms]
        if len(reviewed_keys) != len(set(reviewed_keys)):
            raise ValueError("reviewed agreement item keys must be unique")
        if len(self.required_item_keys) != len(set(self.required_item_keys)):
            raise ValueError("required agreement item keys must be unique")
        if len(self.acknowledged_unresolved_item_keys) != len(
            set(self.acknowledged_unresolved_item_keys)
        ):
            raise ValueError("acknowledged unresolved item keys must be unique")

        reviewed_key_set = set(reviewed_keys)
        required_key_set = set(self.required_item_keys)
        acknowledged_key_set = set(self.acknowledged_unresolved_item_keys)
        if not required_key_set.issubset(reviewed_key_set):
            raise ValueError("every required item must exist in the reviewed version")
        if not acknowledged_key_set.issubset(required_key_set):
            raise ValueError(
                "acknowledged unresolved items must also be required items"
            )

        term_by_key = {term.analysis_item_key: term for term in self.reviewed_terms}
        if any(
            term_by_key[item_key].state == MeaningState.ALIGNED
            for item_key in acknowledged_key_set
        ):
            raise ValueError("aligned items cannot be acknowledged as unresolved")
        return self


class TeachbackEvaluation(StrictModel):
    participant_id: Identifier
    agreement_version_id: Identifier
    original_language: LanguageCode
    prompt_version: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    overall_state: TeachbackComparisonState
    covered_item_keys: list[Identifier] = Field(default_factory=list, max_length=20)
    item_results: list[TeachbackItemResult] = Field(min_length=1, max_length=20)
    missing_or_contradictory_summary: str | None = Field(default=None, max_length=600)
    follow_up_question: str | None = Field(default=None, max_length=500)


class ModelTeachbackItemResult(StrictModel):
    item_key: Identifier
    state: TeachbackComparisonState


class TeachbackModelOutput(StrictModel):
    items: list[ModelTeachbackItemResult] = Field(min_length=1, max_length=20)
