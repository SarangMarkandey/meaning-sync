from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.prompts.teachback_comparison_v1 import PROMPT_VERSION
from app.schemas.analysis import (
    AgreementFacet,
    AgreementTerm,
    AgreementTopic,
    EvidenceReference,
    MeaningState,
    ParticipantPosition,
    ParticipantTermStatus,
    PartyRole,
)
from app.schemas.teachback import (
    ModelTeachbackItemResult,
    TeachbackComparisonState,
    TeachbackErrorCode,
    TeachbackEvaluationRequest,
    TeachbackModelOutput,
)
from app.services.teachbacks import (
    DeterministicTeachbackEvaluator,
    OpenAITeachbackEvaluator,
    TeachbackFailure,
)
from app.services.teachbacks.validation import build_teachback_evaluation


class FakeResponses:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: Any) -> None:
        self.responses = FakeResponses(response)


def configured_settings(**overrides: Any) -> Settings:
    values = {
        "openai_api_key": SecretStr("test-key"),
        "openai_model": "gpt-5.6-test",
        "openai_store_responses": False,
        "openai_request_timeout_seconds": 17,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def reviewed_term(
    *,
    item_key: str,
    topic: AgreementTopic,
    facet: AgreementFacet,
    label: str,
    summary: str,
    state: MeaningState = MeaningState.ALIGNED,
) -> AgreementTerm:
    if state == MeaningState.NOT_DISCUSSED:
        return AgreementTerm(
            id=f"term-{topic.value}",
            analysis_item_key=item_key,
            topic=topic,
            facet=facet,
            label=label,
            summary=summary,
            state=state,
            participant_confirmations={
                PartyRole.HIRER: ParticipantTermStatus.NOT_STATED,
                PartyRole.WORKER: ParticipantTermStatus.NOT_STATED,
            },
        )

    statuses = {
        PartyRole.HIRER: (
            ParticipantTermStatus.CONFIRMED
            if state == MeaningState.ALIGNED
            else ParticipantTermStatus.CONFLICTING
        ),
        PartyRole.WORKER: (
            ParticipantTermStatus.CONFIRMED
            if state == MeaningState.ALIGNED
            else ParticipantTermStatus.CONFLICTING
        ),
    }
    timestamp = datetime(2026, 7, 16, 9, tzinfo=UTC)
    evidence = [
        EvidenceReference(
            source="transcript",
            reference_id=f"message-{index}",
            participant_id=role.value,
            role=role,
            speaker_name=name,
            message_id=f"message-{index}",
            original_text=f"Trusted statement {index}.",
            original_language="en",
            order=index,
            timestamp=timestamp,
        )
        for index, (role, name) in enumerate(
            ((PartyRole.HIRER, "Homeowner"), (PartyRole.WORKER, "Electrician")),
            start=1,
        )
    ]
    return AgreementTerm(
        id=f"term-{topic.value}",
        analysis_item_key=item_key,
        topic=topic,
        facet=facet,
        label=label,
        summary=summary,
        state=state,
        participant_positions=[
            ParticipantPosition(
                participant_id=role.value,
                role=role,
                summary=f"Trusted {role.value} position.",
                evidence_message_ids=[f"message-{index}"],
            )
            for index, role in enumerate(PartyRole, start=1)
        ],
        participant_confirmations=statuses,
        evidence_message_ids=[item.message_id for item in evidence if item.message_id],
        evidence=evidence,
    )


def reviewed_terms() -> list[AgreementTerm]:
    return [
        reviewed_term(
            item_key="scope.work",
            topic=AgreementTopic.SCOPE,
            facet=AgreementFacet.WORK,
            label="Scope of work",
            summary="Repair one fan and two switches.",
        ),
        reviewed_term(
            item_key="price.amount",
            topic=AgreementTopic.PRICE,
            facet=AgreementFacet.AMOUNT,
            label="Labour price",
            summary="The labour price is ₹1,200.",
        ),
        reviewed_term(
            item_key="materials.inclusion",
            topic=AgreementTopic.MATERIALS,
            facet=AgreementFacet.INCLUSION,
            label="Materials and replacement parts",
            summary="Whether replacement parts are included remains unresolved.",
            state=MeaningState.CONFLICTING,
        ),
        reviewed_term(
            item_key="completion.deadline",
            topic=AgreementTopic.COMPLETION,
            facet=AgreementFacet.DEADLINE,
            label="Completion date or time",
            summary="No completion date or time was discussed.",
            state=MeaningState.NOT_DISCUSSED,
        ),
    ]


def evaluation_request(
    *,
    text: str = "Repair one fan and two switches.",
    required: list[str] | None = None,
    acknowledged: list[str] | None = None,
) -> TeachbackEvaluationRequest:
    return TeachbackEvaluationRequest(
        participant_id="hirer",
        agreement_version_id="agreement-v2",
        teachback_text=text,
        original_language="en",
        reviewed_terms=reviewed_terms(),
        required_item_keys=required or ["scope.work"],
        acknowledged_unresolved_item_keys=acknowledged or [],
    )


def test_request_requires_exact_trusted_reviewed_items() -> None:
    with pytest.raises(ValidationError, match="exist in the reviewed version"):
        evaluation_request(required=["invented.policy"])

    with pytest.raises(ValidationError, match="aligned items cannot"):
        evaluation_request(acknowledged=["scope.work"])

    with pytest.raises(ValidationError, match="English only"):
        TeachbackEvaluationRequest(
            **{
                **evaluation_request().model_dump(),
                "original_language": "hi",
            }
        )


def test_model_contract_cannot_return_invented_meaning() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TeachbackModelOutput.model_validate(
            {
                "items": [
                    {
                        "item_key": "scope.work",
                        "state": "matches",
                        "new_agreement_meaning": "The worker also gives a warranty.",
                    }
                ]
            }
        )


def test_validation_rejects_unknown_duplicate_and_missing_item_keys() -> None:
    request = evaluation_request(required=["scope.work", "price.amount"])

    with pytest.raises(TeachbackFailure, match="unknown agreement item"):
        build_teachback_evaluation(
            request,
            TeachbackModelOutput(
                items=[
                    ModelTeachbackItemResult(
                        item_key="invented.policy", state="matches"
                    ),
                    ModelTeachbackItemResult(item_key="scope.work", state="matches"),
                ]
            ),
            prompt_version="test",
            model="mock",
        )

    with pytest.raises(TeachbackFailure, match="duplicate agreement item"):
        build_teachback_evaluation(
            request,
            TeachbackModelOutput(
                items=[
                    ModelTeachbackItemResult(item_key="scope.work", state="matches"),
                    ModelTeachbackItemResult(item_key="scope.work", state="matches"),
                ]
            ),
            prompt_version="test",
            model="mock",
        )

    with pytest.raises(TeachbackFailure, match="omitted a required"):
        build_teachback_evaluation(
            request,
            TeachbackModelOutput(
                items=[ModelTeachbackItemResult(item_key="scope.work", state="matches")]
            ),
            prompt_version="test",
            model="mock",
        )


@pytest.mark.anyio
async def test_deterministic_match_succeeds_without_openai() -> None:
    request = evaluation_request(
        text=(
            "My understanding is that they will repair the fan plus two switches, "
            "and the labour costs ₹1200."
        ),
        required=["scope.work", "price.amount"],
    )

    result = await DeterministicTeachbackEvaluator().evaluate(request)

    assert result.overall_state == TeachbackComparisonState.MATCHES
    assert result.covered_item_keys == ["scope.work", "price.amount"]
    assert result.follow_up_question is None
    assert result.missing_or_contradictory_summary is None


@pytest.mark.anyio
async def test_partial_teachback_gets_smallest_item_specific_followup() -> None:
    result = await DeterministicTeachbackEvaluator().evaluate(
        evaluation_request(text="The fan.")
    )

    assert result.overall_state == TeachbackComparisonState.PARTIALLY_MATCHES
    assert result.item_results[0].state == TeachbackComparisonState.PARTIALLY_MATCHES
    assert result.follow_up_question == (
        "Please explain scope of work more fully in your own words."
    )
    assert "Repair one fan and two switches" in (
        result.missing_or_contradictory_summary or ""
    )


@pytest.mark.anyio
async def test_contradiction_identifies_exact_item_and_does_not_add_meaning() -> None:
    request = evaluation_request(
        text="The labour price is ₹1,500.", required=["price.amount"]
    )

    result = await DeterministicTeachbackEvaluator().evaluate(request)

    assert result.overall_state == TeachbackComparisonState.CONTRADICTS
    assert result.item_results[0].analysis_item_key == "price.amount"
    assert result.item_results[0].agreement_summary == "The labour price is ₹1,200."
    assert result.follow_up_question is None


@pytest.mark.anyio
async def test_insufficient_teachback_is_never_treated_as_match() -> None:
    result = await DeterministicTeachbackEvaluator().evaluate(
        evaluation_request(text="I understand.")
    )

    assert result.overall_state == TeachbackComparisonState.INSUFFICIENT
    assert result.covered_item_keys == []
    assert result.follow_up_question == (
        "Please explain scope of work in your own words."
    )


@pytest.mark.anyio
async def test_explicit_unresolved_acknowledgment_is_not_changed_to_alignment() -> None:
    request = evaluation_request(
        text="I acknowledge that replacement-parts responsibility is unresolved.",
        required=["materials.inclusion"],
        acknowledged=["materials.inclusion"],
    )

    result = await DeterministicTeachbackEvaluator().evaluate(request)

    assert result.overall_state == TeachbackComparisonState.MATCHES
    assert request.reviewed_terms[2].state == MeaningState.CONFLICTING
    assert result.item_results[0].agreement_summary.endswith("remains unresolved.")


@pytest.mark.anyio
async def test_openai_evaluator_uses_mocked_structured_outputs_and_store_false() -> (
    None
):
    response = SimpleNamespace(
        output=[],
        output_parsed=TeachbackModelOutput(
            items=[ModelTeachbackItemResult(item_key="scope.work", state="matches")]
        ),
    )
    client = FakeClient(response)
    evaluator = OpenAITeachbackEvaluator(configured_settings(), client)

    result = await evaluator.evaluate(evaluation_request())

    assert result.overall_state == TeachbackComparisonState.MATCHES
    assert result.prompt_version == PROMPT_VERSION
    assert client.responses.kwargs["model"] == "gpt-5.6-test"
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text_format"] is TeachbackModelOutput
    assert "Repair one fan" in client.responses.kwargs["input"][1]["content"]


@pytest.mark.anyio
async def test_openai_invalid_output_and_refusal_are_safe() -> None:
    bad_output = SimpleNamespace(
        output=[],
        output_parsed=TeachbackModelOutput(
            items=[
                ModelTeachbackItemResult(item_key="invented.policy", state="matches")
            ]
        ),
    )
    with pytest.raises(TeachbackFailure) as caught:
        await OpenAITeachbackEvaluator(
            configured_settings(), FakeClient(bad_output)
        ).evaluate(evaluation_request())
    assert caught.value.code == TeachbackErrorCode.INVALID_MODEL_OUTPUT
    assert "invented.policy" not in caught.value.message

    refusal = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal", refusal="raw refusal")],
            )
        ],
        output_parsed=None,
    )
    with pytest.raises(TeachbackFailure) as caught:
        await OpenAITeachbackEvaluator(
            configured_settings(), FakeClient(refusal)
        ).evaluate(evaluation_request())
    assert caught.value.code == TeachbackErrorCode.REFUSED
    assert "raw refusal" not in caught.value.message


@pytest.mark.anyio
async def test_openai_missing_key_fails_before_any_network_request() -> None:
    evaluator = OpenAITeachbackEvaluator(configured_settings(openai_api_key=None))

    with pytest.raises(TeachbackFailure) as caught:
        await evaluator.evaluate(evaluation_request())

    assert caught.value.code == TeachbackErrorCode.CONFIGURATION_ERROR
    assert caught.value.retryable is False
