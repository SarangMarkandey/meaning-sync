from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.schemas.analysis import AgreementAnalysisRequest
from app.services.analyzers import OpenAIAgreementAnalyzer

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "agreement_evaluations.json"
EVALUATION_CASES: list[dict[str, Any]] = json.loads(FIXTURE_PATH.read_text())
REQUIRED_CASES = {
    "complete_agreement",
    "materials_conflict",
    "price_conflict",
    "completion_date_conflict",
    "one_sided_payment_timing",
    "missing_warranty",
    "additional_work_conflict",
    "cancellation_conflict",
    "self_correction",
    "paraphrased_alignment",
    "no_agreement",
    "prompt_injection_like",
}


def request_for(case: dict[str, Any]) -> AgreementAnalysisRequest:
    started_at = datetime(2026, 7, 16, 9, tzinfo=UTC)
    return AgreementAnalysisRequest.model_validate(
        {
            "session_id": f"eval-{case['name']}",
            "mode": "live",
            "participants": [
                {"id": "hirer", "role": "hirer", "language": "en"},
                {"id": "worker", "role": "worker", "language": "en"},
            ],
            "messages": [
                {
                    "message_id": f"message-{index}",
                    "speaker_id": speaker,
                    "original_text": text,
                    "original_language": "en",
                    "order": index,
                    "timestamp": started_at + timedelta(minutes=index - 1),
                }
                for index, (speaker, text) in enumerate(case["messages"], start=1)
            ],
        }
    )


def test_evaluation_corpus_covers_required_semantic_cases() -> None:
    assert len(EVALUATION_CASES) == 12
    assert {case["name"] for case in EVALUATION_CASES} == REQUIRED_CASES

    valid_states = {"aligned", "conflicting", "stated_by_one", "not_discussed"}
    for case in EVALUATION_CASES:
        request = request_for(case)
        assert {message.speaker_id for message in request.messages} == {
            "hirer",
            "worker",
        }
        assert set(case["expected_states"].values()) <= valid_states


@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_INTEGRATION") != "1",
    reason="real OpenAI evaluation is opt-in and consumes API credits",
)
@pytest.mark.anyio
@pytest.mark.parametrize("case", EVALUATION_CASES, ids=lambda case: case["name"])
async def test_real_model_evaluation_semantics(case: dict[str, Any]) -> None:
    response = await OpenAIAgreementAnalyzer().analyze(request_for(case))
    states_by_topic = {term.topic.value: term.state.value for term in response.terms}

    for topic, expected_state in case["expected_states"].items():
        assert states_by_topic[topic] == expected_state

    expected_target = case["clarification_target"]
    if expected_target is None:
        assert response.primary_clarification is None
    else:
        assert response.primary_clarification is not None
        assert response.primary_clarification.target_item_key == expected_target

    message_by_id = {
        message.message_id: message for message in request_for(case).messages
    }
    for term in response.terms:
        for evidence in term.evidence:
            original = message_by_id[evidence.message_id]
            assert evidence.original_text == original.original_text
            assert evidence.participant_id == original.speaker_id
