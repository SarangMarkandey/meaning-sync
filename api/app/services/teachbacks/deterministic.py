import re

from app.prompts.teachback_comparison_v1 import PROMPT_VERSION
from app.schemas.analysis import AgreementTerm
from app.schemas.teachback import (
    ModelTeachbackItemResult,
    TeachbackComparisonState,
    TeachbackEvaluation,
    TeachbackEvaluationRequest,
    TeachbackModelOutput,
)
from app.services.teachbacks.validation import build_teachback_evaluation

DETERMINISTIC_TEACHBACK_MODEL = "deterministic-teachback"

_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "below",
    "both",
    "by",
    "can",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "participants",
    "recorded",
    "states",
    "stated",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "were",
    "while",
    "with",
}


class DeterministicTeachbackEvaluator:
    async def evaluate(
        self, request: TeachbackEvaluationRequest
    ) -> TeachbackEvaluation:
        term_by_key = {term.analysis_item_key: term for term in request.reviewed_terms}
        acknowledged = set(request.acknowledged_unresolved_item_keys)
        items = [
            ModelTeachbackItemResult(
                item_key=item_key,
                state=(
                    TeachbackComparisonState.MATCHES
                    if item_key in acknowledged
                    else _compare_term(request.teachback_text, term_by_key[item_key])
                ),
            )
            for item_key in request.required_item_keys
        ]
        return build_teachback_evaluation(
            request,
            TeachbackModelOutput(items=items),
            prompt_version=PROMPT_VERSION,
            model=DETERMINISTIC_TEACHBACK_MODEL,
        )


def _compare_term(text: str, term: AgreementTerm) -> TeachbackComparisonState:
    normalized_text = _normalize(text)
    normalized_summary = _normalize(term.summary)
    if _contradicts(normalized_text, normalized_summary):
        return TeachbackComparisonState.CONTRADICTS

    provided_tokens = _tokens(normalized_text)
    expected_tokens = _tokens(f"{term.label} {normalized_summary}")
    overlap = provided_tokens.intersection(expected_tokens)
    expected_numbers = set(re.findall(r"\b\d[\d,]*\b", normalized_summary))
    provided_numbers = set(re.findall(r"\b\d[\d,]*\b", normalized_text))

    if not overlap and not expected_numbers.intersection(provided_numbers):
        return TeachbackComparisonState.INSUFFICIENT
    if normalized_summary in normalized_text:
        return TeachbackComparisonState.MATCHES
    if expected_numbers and expected_numbers.issubset(provided_numbers) and overlap:
        return TeachbackComparisonState.MATCHES
    if len(overlap) >= 3:
        return TeachbackComparisonState.MATCHES
    return TeachbackComparisonState.PARTIALLY_MATCHES


def _contradicts(text: str, summary: str) -> bool:
    expected_numbers = set(re.findall(r"\b\d[\d,]*\b", summary))
    provided_numbers = set(re.findall(r"\b\d[\d,]*\b", text))
    if (
        expected_numbers
        and provided_numbers
        and not expected_numbers.intersection(provided_numbers)
    ):
        return True

    expected_separate = any(word in summary for word in ("separate", "extra"))
    provided_included = "included" in text and "not included" not in text
    if expected_separate and provided_included and "separate" not in text:
        return True
    expected_included = "included" in summary and "not included" not in summary
    provided_separate = any(
        phrase in text for phrase in ("separate", "not included", "extra")
    )
    if expected_included and provided_separate and "included" not in text:
        return True
    if "today" in summary and "tomorrow" in text and "today" not in text:
        return True
    if "after" in summary and any(word in text for word in ("before", "upfront")):
        return "after" not in text
    return "repair" in summary and "replace" in text and "repair" not in text


def _normalize(value: str) -> str:
    return " ".join(
        value.casefold().replace("labour", "labor").replace(",", "").split()
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value)
        if len(token) > 1 and token not in _STOP_WORDS
    }
