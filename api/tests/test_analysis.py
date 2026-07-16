from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr, ValidationError

from app.api.analysis import analyze_agreement
from app.config import Settings
from app.main import app, controlled_request_validation
from app.prompts.agreement_analysis_v1 import PROMPT_VERSION
from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementTopic,
    AnalysisErrorCode,
    AnalysisMessage,
    AnalysisParticipant,
    AnalysisStatus,
    AnalysisWarningCode,
    MeaningState,
    ModelAgreementTerm,
    ModelParticipantPosition,
    SessionMode,
)
from app.services.analyzers import (
    AnalysisFailure,
    DeterministicAgreementAnalyzer,
    OpenAIAgreementAnalyzer,
)
from app.services.analyzers.validation import (
    build_analysis_response,
    normalize_legacy_model_output,
    resolve_legacy_clarification_owner,
)


def conversation_request(mode: SessionMode = SessionMode.LIVE):
    started_at = datetime(2026, 7, 16, 9, tzinfo=UTC)
    texts = [
        (
            "hirer",
            "I will pay ₹1,200 for repairing the fan and two switches, "
            "including replacement parts.",
        ),
        (
            "worker",
            "₹1,200 covers my labour. Replacement parts are separate.",
        ),
        ("hirer", "The work can start today."),
        ("worker", "Yes, I can start today."),
    ]
    return AgreementAnalysisRequest(
        session_id="live-session-1",
        mode=mode,
        participants=[
            AnalysisParticipant(id="hirer", role="hirer", language="en"),
            AnalysisParticipant(id="worker", role="worker", language="en"),
        ],
        messages=[
            AnalysisMessage(
                message_id=f"message-{index}",
                speaker_id=speaker,
                original_text=text,
                original_language="en",
                order=index,
                timestamp=started_at + timedelta(minutes=index - 1),
            )
            for index, (speaker, text) in enumerate(texts, start=1)
        ],
    )


def required_example_output() -> AgreementAnalysisModelOutput:
    return AgreementAnalysisModelOutput(
        terms=[
            ModelAgreementTerm(
                item_key="price.amount",
                topic="price",
                facet="amount",
                neutral_summary="Both participants state the labour amount as ₹1,200.",
                state="aligned",
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id="hirer",
                        summary="The amount is ₹1,200.",
                        evidence_message_ids=["message-1"],
                    ),
                    ModelParticipantPosition(
                        participant_id="worker",
                        summary="The labour amount is ₹1,200.",
                        evidence_message_ids=["message-2"],
                    ),
                ],
                evidence_message_ids=["message-1", "message-2"],
            ),
            ModelAgreementTerm(
                item_key="materials.inclusion",
                topic="materials",
                facet="inclusion",
                neutral_summary="The participants disagree about parts coverage.",
                state="conflicting",
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id="hirer",
                        summary="Parts are included.",
                        evidence_message_ids=["message-1"],
                    ),
                    ModelParticipantPosition(
                        participant_id="worker",
                        summary="Parts are separate.",
                        evidence_message_ids=["message-2"],
                    ),
                ],
                evidence_message_ids=["message-1", "message-2"],
                clarification_question="Does ₹1,200 include replacement parts?",
            ),
            ModelAgreementTerm(
                item_key="timing.start",
                topic="timing",
                facet="start",
                neutral_summary="Both participants agree work can start today.",
                state="aligned",
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id="hirer",
                        summary="Work can start today.",
                        evidence_message_ids=["message-3"],
                    ),
                    ModelParticipantPosition(
                        participant_id="worker",
                        summary="The electrician can start today.",
                        evidence_message_ids=["message-4"],
                    ),
                ],
                evidence_message_ids=["message-3", "message-4"],
            ),
            *[
                ModelAgreementTerm(
                    item_key=f"{topic}.{facet}",
                    topic=topic,
                    facet=facet,
                    neutral_summary=summary,
                    state="not_discussed",
                )
                for topic, facet, summary in [
                    ("completion", "deadline", "Completion time was not discussed."),
                    ("payment", "timing", "Payment timing was not discussed."),
                    ("warranty", "coverage", "Warranty was not discussed."),
                    ("cancellation", "policy", "Cancellation was not discussed."),
                    (
                        "additional_work",
                        "policy",
                        "Additional-work policy was not discussed.",
                    ),
                ]
            ],
        ],
    )


class FakeResponses:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def configured_settings(**overrides: Any) -> Settings:
    values = {
        "openai_api_key": SecretStr("test-key"),
        "openai_model": "gpt-5.6",
        "openai_store_responses": False,
        "openai_request_timeout_seconds": 30,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_model_schema_nests_clarification_without_detached_references() -> None:
    schema = AgreementAnalysisModelOutput.model_json_schema()
    properties = schema["$defs"]["ModelAgreementTerm"]["properties"]

    assert "clarification_question" in properties
    assert "clarification_target" not in properties
    assert "clarification_evidence_message_ids" not in properties
    assert "primary_clarification" not in schema["properties"]


@pytest.mark.anyio
async def test_deterministic_mode_works_without_api_key() -> None:
    response = await DeterministicAgreementAnalyzer().analyze(
        conversation_request(SessionMode.DEMO)
    )
    assert response.model == "deterministic"
    assert response.primary_clarification is not None
    assert any(term.state == MeaningState.ALIGNED for term in response.terms)


@pytest.mark.anyio
async def test_openai_uses_structured_outputs_configured_model_and_store_false() -> (
    None
):
    fake_responses = FakeResponses(
        SimpleNamespace(output_parsed=required_example_output(), output=[])
    )
    analyzer = OpenAIAgreementAnalyzer(
        configured_settings(openai_model="gpt-5.6-test"),
        FakeClient(fake_responses),
    )

    response = await analyzer.analyze(conversation_request())

    assert response.prompt_version == PROMPT_VERSION
    assert fake_responses.kwargs["model"] == "gpt-5.6-test"
    assert fake_responses.kwargs["store"] is False
    assert fake_responses.kwargs["text_format"] is AgreementAnalysisModelOutput
    assert "replacement parts" in fake_responses.kwargs["input"][1]["content"]


@pytest.mark.anyio
async def test_required_semantics_and_original_evidence_are_preserved() -> None:
    fake_responses = FakeResponses(
        SimpleNamespace(output_parsed=required_example_output(), output=[])
    )
    response = await OpenAIAgreementAnalyzer(
        configured_settings(), FakeClient(fake_responses)
    ).analyze(conversation_request())
    terms = {term.topic: term for term in response.terms}

    assert terms[AgreementTopic.PRICE].state == MeaningState.ALIGNED
    assert terms[AgreementTopic.PRICE].analysis_item_key == "price.amount"
    assert terms[AgreementTopic.TIMING].state == MeaningState.ALIGNED
    assert terms[AgreementTopic.MATERIALS].state == MeaningState.CONFLICTING
    assert terms[AgreementTopic.MATERIALS].analysis_item_key == ("materials.inclusion")
    assert terms[AgreementTopic.COMPLETION].state == MeaningState.NOT_DISCUSSED
    assert terms[AgreementTopic.PAYMENT].state == MeaningState.NOT_DISCUSSED
    assert terms[AgreementTopic.WARRANTY].state == MeaningState.NOT_DISCUSSED
    assert terms[AgreementTopic.CANCELLATION].state == MeaningState.NOT_DISCUSSED
    assert terms[AgreementTopic.ADDITIONAL_WORK].state == (MeaningState.NOT_DISCUSSED)
    assert response.primary_clarification is not None
    assert response.primary_clarification.target == AgreementTopic.MATERIALS
    assert response.primary_clarification.facet == "inclusion"
    assert response.primary_clarification.target_item_key == "materials.inclusion"
    assert set(response.primary_clarification.evidence_message_ids) == {
        "message-1",
        "message-2",
    }
    assert (
        terms[AgreementTopic.MATERIALS]
        .evidence[0]
        .original_text.startswith("I will pay ₹1,200")
    )
    assert terms[AgreementTopic.MATERIALS].evidence[1].speaker_name == "Electrician"


def test_unknown_or_wrong_speaker_evidence_is_rejected() -> None:
    request = conversation_request()
    unknown = required_example_output()
    unknown.terms[0].evidence_message_ids[0] = "made-up-message"
    with pytest.raises(AnalysisFailure, match="unknown message") as caught:
        build_analysis_response(request, unknown, prompt_version="test", model="mock")
    assert caught.value.code == AnalysisErrorCode.INVALID_MODEL_OUTPUT
    assert caught.value.status_code == 502

    wrong_speaker = required_example_output()
    wrong_speaker.terms[0].participant_positions[0].evidence_message_ids = ["message-2"]
    with pytest.raises(AnalysisFailure, match="claimed participant"):
        build_analysis_response(
            request, wrong_speaker, prompt_version="test", model="mock"
        )


def test_conflicts_need_both_sides_and_one_sided_terms_are_not_aligned() -> None:
    request = conversation_request()
    conflict = required_example_output()
    conflict.terms[0].evidence_message_ids = ["message-1"]
    conflict.terms[0].participant_positions = [
        conflict.terms[0].participant_positions[0]
    ]
    with pytest.raises(AnalysisFailure, match="both participants"):
        build_analysis_response(request, conflict, prompt_version="test", model="mock")

    one_sided = AgreementAnalysisModelOutput(
        terms=[
            ModelAgreementTerm(
                item_key="payment.timing",
                topic="payment",
                facet="timing",
                neutral_summary="Only the homeowner states payment timing.",
                state="stated_by_one",
                participant_positions=[
                    ModelParticipantPosition(
                        participant_id="hirer",
                        summary="Payment is due after the work.",
                        evidence_message_ids=["message-1"],
                    )
                ],
                evidence_message_ids=["message-1"],
            )
        ]
    )
    response = build_analysis_response(
        request, one_sided, prompt_version="test", model="mock"
    )
    assert response.terms[0].state == MeaningState.STATED_BY_ONE
    assert response.terms[0].participant_confirmations["worker"] == "not_stated"


def test_duplicate_atomic_items_are_rejected() -> None:
    output = required_example_output()
    output.terms.append(output.terms[0].model_copy(deep=True))

    with pytest.raises(AnalysisFailure, match="same atomic agreement item"):
        build_analysis_response(
            conversation_request(), output, prompt_version="test", model="mock"
        )


def test_nested_materials_clarification_inherits_exact_owner_and_evidence() -> None:
    output = required_example_output()
    response = build_analysis_response(
        conversation_request(), output, prompt_version="test", model="mock"
    )

    assert response.status == AnalysisStatus.COMPLETE
    assert response.warnings == []
    assert response.primary_clarification is not None
    assert response.primary_clarification.target_item_key == "materials.inclusion"
    assert response.primary_clarification.target == AgreementTopic.MATERIALS
    assert response.primary_clarification.facet == "inclusion"
    assert response.primary_clarification.evidence_message_ids == [
        "message-1",
        "message-2",
    ]
    materials = next(term for term in response.terms if term.topic == "materials")
    assert materials.clarification_target == materials.analysis_item_key


def test_clarification_on_aligned_item_returns_partial_map() -> None:
    output = required_example_output()
    materials = next(term for term in output.terms if term.topic == "materials")
    price = next(term for term in output.terms if term.topic == "price")
    materials.clarification_question = None
    price.clarification_question = "What amount did both people state?"

    response = build_analysis_response(
        conversation_request(), output, prompt_version="test", model="mock"
    )

    assert response.status == AnalysisStatus.PARTIAL
    assert response.primary_clarification is None
    assert response.warnings[0].code == (AnalysisWarningCode.CLARIFICATION_UNAVAILABLE)
    assert {term.analysis_item_key for term in response.terms} >= {
        "price.amount",
        "materials.inclusion",
    }


def test_multiple_nested_clarifications_return_partial_without_guessing() -> None:
    output = required_example_output()
    timing = next(term for term in output.terms if term.topic == "timing")
    timing.clarification_question = "When should the work start?"

    response = build_analysis_response(
        conversation_request(), output, prompt_version="test", model="mock"
    )

    assert response.status == AnalysisStatus.PARTIAL
    assert response.primary_clarification is None
    assert len(response.warnings) == 1


def test_legacy_resolution_uses_exact_topic_and_facet() -> None:
    terms = _two_unresolved_price_terms()

    owner = resolve_legacy_clarification_owner(
        terms,
        target="price",
        facet="inclusion",
    )

    assert owner == 1


def test_legacy_resolution_does_not_use_ambiguous_broad_topic() -> None:
    terms = _two_unresolved_price_terms()

    owner = resolve_legacy_clarification_owner(terms, target="price")

    assert owner is None


def test_legacy_resolution_uses_unique_evidence_overlap() -> None:
    output = required_example_output()
    materials = next(term for term in output.terms if term.topic == "materials")
    timing = next(term for term in output.terms if term.topic == "timing")
    timing.state = MeaningState.STATED_BY_ONE
    timing.participant_positions = [timing.participant_positions[0]]
    timing.evidence_message_ids = ["message-3"]
    terms = [materials, timing]

    owner = resolve_legacy_clarification_owner(
        terms,
        target_item_key="invented.key",
        evidence_message_ids=["message-3"],
    )

    assert owner == 1


def test_legacy_resolution_does_not_guess_on_ambiguous_evidence() -> None:
    terms = _two_unresolved_price_terms()

    owner = resolve_legacy_clarification_owner(
        terms,
        target_item_key="invented.key",
        evidence_message_ids=["message-1"],
    )

    assert owner is None


def test_sanitized_problematic_output_returns_partial_success_offline() -> None:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "problematic_price_materials_output.json"
    )
    payload = json.loads(fixture_path.read_text())
    output, clarification_unavailable = normalize_legacy_model_output(payload)

    response = build_analysis_response(
        conversation_request(),
        output,
        prompt_version="test",
        model="mock",
        clarification_unavailable=clarification_unavailable,
    )

    assert response.status == AnalysisStatus.PARTIAL
    assert response.primary_clarification is None
    assert response.warnings[0].code == "clarification_unavailable"
    assert len(response.terms) == 2
    assert all(term.evidence for term in response.terms)


def _two_unresolved_price_terms() -> list[ModelAgreementTerm]:
    price = required_example_output().terms[0].model_copy(deep=True)
    price.state = MeaningState.CONFLICTING
    second = price.model_copy(
        deep=True,
        update={
            "item_key": "price.inclusion",
            "facet": "inclusion",
            "clarification_question": None,
        },
    )
    return [price, second]


def test_request_validation_rejects_unsupported_or_invalid_conversations() -> None:
    request_data = conversation_request().model_dump(mode="json")
    request_data["participants"][1]["language"] = "hi"
    with pytest.raises(ValidationError, match="English participants only"):
        AgreementAnalysisRequest.model_validate(request_data)

    request_data = conversation_request().model_dump(mode="json")
    request_data["messages"] = [request_data["messages"][0]]
    with pytest.raises(ValidationError):
        AgreementAnalysisRequest.model_validate(request_data)

    request_data = conversation_request().model_dump(mode="json")
    request_data["messages"][0]["speaker_id"] = "unknown"
    with pytest.raises(ValidationError, match="speaker must be a participant"):
        AgreementAnalysisRequest.model_validate(request_data)


@pytest.mark.anyio
async def test_missing_key_is_controlled_and_never_falls_back() -> None:
    analyzer = OpenAIAgreementAnalyzer(configured_settings(openai_api_key=None))
    with pytest.raises(AnalysisFailure) as caught:
        await analyzer.analyze(conversation_request())
    assert caught.value.code == AnalysisErrorCode.CONFIGURATION_ERROR
    assert caught.value.retryable is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "expected_code", "retryable"),
    [
        (
            openai.APITimeoutError(request=httpx.Request("POST", "https://api")),
            AnalysisErrorCode.TIMEOUT,
            True,
        ),
        (
            openai.RateLimitError(
                "rate limited",
                response=httpx.Response(
                    429, request=httpx.Request("POST", "https://api")
                ),
                body=None,
            ),
            AnalysisErrorCode.RATE_LIMITED,
            True,
        ),
    ],
)
async def test_provider_failures_return_safe_codes(
    error: Exception, expected_code: AnalysisErrorCode, retryable: bool
) -> None:
    analyzer = OpenAIAgreementAnalyzer(
        configured_settings(), FakeClient(FakeResponses(error=error))
    )
    with pytest.raises(AnalysisFailure) as caught:
        await analyzer.analyze(conversation_request())
    assert caught.value.code == expected_code
    assert caught.value.retryable is retryable
    assert "rate limited" not in caught.value.message.casefold()


@pytest.mark.anyio
async def test_refusal_and_missing_parsed_output_are_controlled() -> None:
    refusal = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal", refusal="raw refusal")],
            )
        ],
        output_parsed=None,
    )
    analyzer = OpenAIAgreementAnalyzer(
        configured_settings(), FakeClient(FakeResponses(refusal))
    )
    with pytest.raises(AnalysisFailure) as caught:
        await analyzer.analyze(conversation_request())
    assert caught.value.code == AnalysisErrorCode.REFUSED
    assert "raw refusal" not in caught.value.message

    analyzer = OpenAIAgreementAnalyzer(
        configured_settings(),
        FakeClient(FakeResponses(SimpleNamespace(output=[], output_parsed=None))),
    )
    with pytest.raises(AnalysisFailure) as caught:
        await analyzer.analyze(conversation_request())
    assert caught.value.code == AnalysisErrorCode.INVALID_MODEL_OUTPUT


@pytest.mark.anyio
async def test_live_api_returns_explicit_response_schema() -> None:
    class StaticAnalyzer:
        async def analyze(self, request: AgreementAnalysisRequest):
            return build_analysis_response(
                request,
                required_example_output(),
                prompt_version="test-v1",
                model="mock-model",
            )

    response = await analyze_agreement(conversation_request(), StaticAnalyzer())
    payload = response.model_dump(mode="json")
    assert payload["session_id"] == "live-session-1"
    assert payload["status"] == "complete"
    assert payload["warnings"] == []
    assert payload["terms"][0]["evidence"][0]["original_text"]
    assert payload["primary_clarification"]["target"] == "materials"

    operation = app.openapi()["paths"]["/api/v1/agreements/analyze"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith("AgreementAnalysisResponse")


@pytest.mark.anyio
async def test_live_api_returns_partial_map_instead_of_502_for_bad_clarification() -> (
    None
):
    output = required_example_output()
    materials = next(term for term in output.terms if term.topic == "materials")
    price = next(term for term in output.terms if term.topic == "price")
    materials.clarification_question = None
    price.clarification_question = "Who is right about the price?"

    class PartialAnalyzer:
        async def analyze(self, request: AgreementAnalysisRequest):
            return build_analysis_response(
                request,
                output,
                prompt_version="test-v1",
                model="mock-model",
            )

    response = await analyze_agreement(conversation_request(), PartialAnalyzer())

    assert response.status == AnalysisStatus.PARTIAL
    assert response.primary_clarification is None
    assert response.terms
    assert response.warnings[0].code == "clarification_unavailable"
    operation = app.openapi()["paths"]["/api/v1/agreements/analyze"]["post"]
    assert "200" in operation["responses"]


@pytest.mark.anyio
async def test_live_api_request_validation_uses_safe_error_contract() -> None:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/agreements/analyze",
            "raw_path": b"/api/v1/agreements/analyze",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )
    response = await controlled_request_validation(request, RequestValidationError([]))
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": {
            "code": "invalid_request",
            "message": "The agreement-analysis request is invalid.",
            "retryable": False,
        }
    }
