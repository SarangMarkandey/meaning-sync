import json
from typing import Any

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.prompts.agreement_analysis_v1 import (
    AGREEMENT_ANALYSIS_SYSTEM_PROMPT,
    PROMPT_VERSION,
)
from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AnalysisErrorCode,
)
from app.services.analyzers.base import AnalysisFailure
from app.services.analyzers.validation import build_analysis_response


class OpenAIAgreementAnalyzer:
    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._injected_client = client

    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        try:
            client = self._injected_client or self._create_client()
            response = await client.responses.parse(
                model=self._settings.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": AGREEMENT_ANALYSIS_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": _serialize_conversation(request),
                    },
                ],
                text_format=AgreementAnalysisModelOutput,
                store=False,
            )
            if _contains_refusal(response):
                raise AnalysisFailure(
                    AnalysisErrorCode.REFUSED,
                    "The analysis could not be completed for this conversation.",
                    retryable=False,
                    status_code=422,
                )
            parsed = response.output_parsed
            if parsed is None:
                raise AnalysisFailure(
                    AnalysisErrorCode.INVALID_MODEL_OUTPUT,
                    "The analysis returned no usable structured result.",
                    retryable=True,
                    status_code=502,
                )
            return build_analysis_response(
                request,
                parsed,
                prompt_version=PROMPT_VERSION,
                model=self._settings.openai_model,
            )
        except AnalysisFailure:
            raise
        except openai.AuthenticationError as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.INVALID_API_KEY,
                "Live analysis is not configured with a valid API key.",
                retryable=False,
                status_code=503,
            ) from exc
        except openai.RateLimitError as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.RATE_LIMITED,
                "Live analysis is temporarily busy. Please try again shortly.",
                retryable=True,
                status_code=429,
            ) from exc
        except openai.APITimeoutError as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.TIMEOUT,
                "Live analysis took too long. Please try again.",
                retryable=True,
                status_code=504,
            ) from exc
        except openai.APIConnectionError as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.CONNECTION_ERROR,
                "Live analysis could not reach the analysis service.",
                retryable=True,
                status_code=503,
            ) from exc
        except ValidationError as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.INVALID_MODEL_OUTPUT,
                "The analysis returned an invalid structured result.",
                retryable=True,
                status_code=502,
            ) from exc
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500
            raise AnalysisFailure(
                AnalysisErrorCode.PROVIDER_ERROR,
                "Live analysis is temporarily unavailable.",
                retryable=retryable,
                status_code=503 if retryable else 502,
            ) from exc
        except Exception as exc:
            raise AnalysisFailure(
                AnalysisErrorCode.PROVIDER_ERROR,
                "Live analysis could not be completed.",
                retryable=True,
                status_code=502,
            ) from exc

    def _create_client(self) -> AsyncOpenAI:
        key = self._settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise AnalysisFailure(
                AnalysisErrorCode.CONFIGURATION_ERROR,
                "Live analysis is not configured yet.",
                retryable=False,
                status_code=503,
            )
        return AsyncOpenAI(
            api_key=key.get_secret_value(),
            timeout=self._settings.openai_request_timeout_seconds,
            max_retries=0,
        )


def _serialize_conversation(request: AgreementAnalysisRequest) -> str:
    return json.dumps(
        {
            "session_id": request.session_id,
            "participants": [
                participant.model_dump(mode="json")
                for participant in request.participants
            ],
            "messages": [
                message.model_dump(mode="json") for message in request.messages
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _contains_refusal(response: Any) -> bool:
    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                return True
    return False
