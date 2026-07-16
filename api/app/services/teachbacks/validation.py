from collections.abc import Sequence

from app.schemas.analysis import AgreementTerm
from app.schemas.teachback import (
    ModelTeachbackItemResult,
    TeachbackComparisonState,
    TeachbackErrorCode,
    TeachbackEvaluation,
    TeachbackEvaluationRequest,
    TeachbackItemResult,
    TeachbackModelOutput,
)
from app.services.teachbacks.base import TeachbackFailure


def invalid_teachback_output(message: str) -> TeachbackFailure:
    return TeachbackFailure(
        TeachbackErrorCode.INVALID_MODEL_OUTPUT,
        message,
        retryable=True,
        status_code=502,
    )


def build_teachback_evaluation(
    request: TeachbackEvaluationRequest,
    output: TeachbackModelOutput,
    *,
    prompt_version: str,
    model: str,
) -> TeachbackEvaluation:
    term_by_key = {term.analysis_item_key: term for term in request.reviewed_terms}
    model_keys = [item.item_key for item in output.items]
    if len(model_keys) != len(set(model_keys)):
        raise invalid_teachback_output(
            "The teach-back comparison returned a duplicate agreement item."
        )

    expected_keys = set(request.required_item_keys)
    returned_keys = set(model_keys)
    if returned_keys - expected_keys:
        raise invalid_teachback_output(
            "The teach-back comparison referenced an unknown agreement item."
        )
    if expected_keys - returned_keys:
        raise invalid_teachback_output(
            "The teach-back comparison omitted a required agreement item."
        )

    model_by_key = {item.item_key: item for item in output.items}
    item_results = [
        _build_item_result(term_by_key[item_key], model_by_key[item_key])
        for item_key in request.required_item_keys
    ]
    overall_state = _overall_state(item_results)
    covered_item_keys = [
        item.analysis_item_key
        for item in item_results
        if item.state != TeachbackComparisonState.INSUFFICIENT
    ]
    issue_results = [
        item for item in item_results if item.state != TeachbackComparisonState.MATCHES
    ]

    return TeachbackEvaluation(
        participant_id=request.participant_id,
        agreement_version_id=request.agreement_version_id,
        original_language=request.original_language,
        prompt_version=prompt_version,
        model=model,
        overall_state=overall_state,
        covered_item_keys=covered_item_keys,
        item_results=item_results,
        missing_or_contradictory_summary=_issue_summary(issue_results),
        follow_up_question=_focused_followup(item_results, term_by_key),
    )


def _build_item_result(
    term: AgreementTerm,
    model_result: ModelTeachbackItemResult,
) -> TeachbackItemResult:
    state = model_result.state
    if state == TeachbackComparisonState.MATCHES:
        feedback = f"Your explanation matches the recorded meaning for {term.label}."
    elif state == TeachbackComparisonState.PARTIALLY_MATCHES:
        feedback = (
            f"Your explanation only partly covers {term.label}. "
            f"Reviewed meaning: {term.summary}"
        )
    elif state == TeachbackComparisonState.CONTRADICTS:
        feedback = (
            f"Your explanation differs from {term.label}. "
            f"Reviewed meaning: {term.summary}"
        )
    else:
        feedback = (
            f"Your explanation does not give enough detail for {term.label}. "
            f"Reviewed meaning: {term.summary}"
        )
    return TeachbackItemResult(
        analysis_item_key=term.analysis_item_key,
        state=state,
        agreement_summary=term.summary,
        feedback=feedback,
    )


def _overall_state(
    results: Sequence[TeachbackItemResult],
) -> TeachbackComparisonState:
    states = {result.state for result in results}
    if TeachbackComparisonState.CONTRADICTS in states:
        return TeachbackComparisonState.CONTRADICTS
    if states == {TeachbackComparisonState.MATCHES}:
        return TeachbackComparisonState.MATCHES
    if states == {TeachbackComparisonState.INSUFFICIENT}:
        return TeachbackComparisonState.INSUFFICIENT
    return TeachbackComparisonState.PARTIALLY_MATCHES


def _issue_summary(results: Sequence[TeachbackItemResult]) -> str | None:
    if not results:
        return None
    summaries = [f"{result.analysis_item_key}: {result.feedback}" for result in results]
    joined = " ".join(summaries)
    if len(joined) <= 600:
        return joined
    return f"{joined[:597].rstrip()}..."


def _focused_followup(
    results: Sequence[TeachbackItemResult],
    term_by_key: dict[str, AgreementTerm],
) -> str | None:
    for desired_state in (
        TeachbackComparisonState.PARTIALLY_MATCHES,
        TeachbackComparisonState.INSUFFICIENT,
    ):
        result = next((item for item in results if item.state == desired_state), None)
        if result is None:
            continue
        term = term_by_key[result.analysis_item_key]
        if desired_state == TeachbackComparisonState.PARTIALLY_MATCHES:
            return f"Please explain {term.label.lower()} more fully in your own words."
        return f"Please explain {term.label.lower()} in your own words."
    return None
