import json
from typing import Any

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.prompts.teachback_comparison_v1 import (
    PROMPT_VERSION,
    TEACHBACK_COMPARISON_SYSTEM_PROMPT,
)
from app.schemas.teachback import (
    TeachbackErrorCode,
    TeachbackEvaluation,
    TeachbackEvaluationRequest,
    TeachbackModelOutput,
)
from app.services.teachbacks.base import TeachbackFailure
from app.services.teachbacks.validation import build_teachback_evaluation


class OpenAITeachbackEvaluator:
    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._injected_client = client

    async def evaluate(
        self, request: TeachbackEvaluationRequest
    ) -> TeachbackEvaluation:
        try:
            client = self._injected_client or self._create_client()
            response = await client.responses.parse(
                model=self._settings.openai_model,
                input=[
                    {"role": "system", "content": TEACHBACK_COMPARISON_SYSTEM_PROMPT},
                    {"role": "user", "content": _serialize_request(request)},
                ],
                text_format=TeachbackModelOutput,
                store=False,
            )
            if _contains_refusal(response):
                raise TeachbackFailure(
                    TeachbackErrorCode.REFUSED,
                    "The teach-back could not be compared.",
                    retryable=False,
                    status_code=422,
                )
            parsed = response.output_parsed
            if parsed is None:
                raise TeachbackFailure(
                    TeachbackErrorCode.INVALID_MODEL_OUTPUT,
                    "The teach-back comparison returned no usable result.",
                    retryable=True,
                    status_code=502,
                )
            parsed = TeachbackModelOutput.model_validate(parsed)
            return build_teachback_evaluation(
                request,
                parsed,
                prompt_version=PROMPT_VERSION,
                model=self._settings.openai_model,
            )
        except TeachbackFailure:
            raise
        except openai.AuthenticationError as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.INVALID_API_KEY,
                "Teach-back comparison is not configured with a valid API key.",
                retryable=False,
                status_code=503,
            ) from exc
        except openai.RateLimitError as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.RATE_LIMITED,
                "Teach-back comparison is temporarily busy. Please try again shortly.",
                retryable=True,
                status_code=429,
            ) from exc
        except openai.APITimeoutError as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.TIMEOUT,
                "Teach-back comparison took too long. Please try again.",
                retryable=True,
                status_code=504,
            ) from exc
        except openai.APIConnectionError as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.CONNECTION_ERROR,
                "Teach-back comparison could not reach the analysis service.",
                retryable=True,
                status_code=503,
            ) from exc
        except ValidationError as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.INVALID_MODEL_OUTPUT,
                "The teach-back comparison returned an invalid structured result.",
                retryable=True,
                status_code=502,
            ) from exc
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500
            raise TeachbackFailure(
                TeachbackErrorCode.PROVIDER_ERROR,
                "Teach-back comparison is temporarily unavailable.",
                retryable=retryable,
                status_code=503 if retryable else 502,
            ) from exc
        except Exception as exc:
            raise TeachbackFailure(
                TeachbackErrorCode.PROVIDER_ERROR,
                "Teach-back comparison could not be completed.",
                retryable=True,
                status_code=502,
            ) from exc

    def _create_client(self) -> AsyncOpenAI:
        key = self._settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise TeachbackFailure(
                TeachbackErrorCode.CONFIGURATION_ERROR,
                "Teach-back comparison is not configured yet.",
                retryable=False,
                status_code=503,
            )
        return AsyncOpenAI(
            api_key=key.get_secret_value(),
            timeout=self._settings.openai_request_timeout_seconds,
            max_retries=0,
        )


def _serialize_request(request: TeachbackEvaluationRequest) -> str:
    term_by_key = {term.analysis_item_key: term for term in request.reviewed_terms}
    acknowledged = set(request.acknowledged_unresolved_item_keys)
    return json.dumps(
        {
            "participant_id": request.participant_id,
            "agreement_version_id": request.agreement_version_id,
            "original_language": request.original_language,
            "teachback_text": request.teachback_text,
            "required_items": [
                {
                    "item_key": item_key,
                    "label": term_by_key[item_key].label,
                    "reviewed_meaning": term_by_key[item_key].summary,
                    "meaning_state": term_by_key[item_key].state,
                    "participant_positions": [
                        {
                            "participant_id": position.participant_id,
                            "summary": position.summary,
                        }
                        for position in term_by_key[item_key].participant_positions
                    ],
                    "acknowledged_unresolved": item_key in acknowledged,
                }
                for item_key in request.required_item_keys
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _contains_refusal(response: Any) -> bool:
    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                return True
    return False
