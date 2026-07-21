from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import Field

from app.config import Settings, get_settings
from app.schemas.analysis import (
    LanguageCode as AnalysisLanguageCode,
)
from app.schemas.analysis import (
    SemanticEquivalenceStatus,
    StrictModel,
)
from app.schemas.session import LanguageCode, TranscriptTurn

TRANSLATION_PROMPT_VERSION = "meaning-preserving-translation-v1"


class TranslationOutput(StrictModel):
    source_language: AnalysisLanguageCode
    target_language: AnalysisLanguageCode
    translated_text: str = Field(min_length=1, max_length=2000)
    preserved_amounts: list[str] = Field(default_factory=list, max_length=20)
    preserved_currencies: list[str] = Field(default_factory=list, max_length=20)
    preserved_dates: list[str] = Field(default_factory=list, max_length=20)
    preserved_quantities: list[str] = Field(default_factory=list, max_length=20)
    semantic_equivalence_status: SemanticEquivalenceStatus
    warnings: list[str] = Field(default_factory=list, max_length=10)
    model: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=80)


class LiveTranslationService(Protocol):
    model: str
    prompt_version: str

    async def translate_message(
        self,
        original_text: str,
        source_language: AnalysisLanguageCode,
        target_language: AnalysisLanguageCode,
    ) -> TranslationOutput: ...


def translation_fingerprint(
    text: str,
    source_language: AnalysisLanguageCode,
    target_language: AnalysisLanguageCode,
    model: str,
    prompt_version: str,
) -> str:
    payload = json.dumps(
        {
            "text": text,
            "source": source_language.value,
            "target": target_language.value,
            "model": model,
            "prompt_version": prompt_version,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


_FIXTURES = {
    (
        "मैं पंखे और दो स्विच की मरम्मत के लिए ₹1,200 दूँगा, जिसमें बदलने वाले पुर्जे शामिल हैं।",
        AnalysisLanguageCode.ENGLISH,
    ): (
        "I will pay ₹1,200 to repair the fan and two switches, including "
        "replacement parts."
    ),
    (
        "₹1,200 covers my labour. Replacement parts are separate.",
        AnalysisLanguageCode.HINDI,
    ): "₹1,200 मेरी मजदूरी के लिए है। बदलने वाले पुर्जों का खर्च अलग है।",
    (
        "काम आज शुरू हो सकता है।",
        AnalysisLanguageCode.ENGLISH,
    ): "The work can start today.",
    (
        "Yes, I can start today.",
        AnalysisLanguageCode.HINDI,
    ): "हाँ, मैं आज काम शुरू कर सकता हूँ।",
}


class DeterministicTranslationService:
    model = "deterministic-translation"
    prompt_version = TRANSLATION_PROMPT_VERSION

    async def translate_message(
        self,
        original_text: str,
        source_language: AnalysisLanguageCode,
        target_language: AnalysisLanguageCode,
    ) -> TranslationOutput:
        if source_language == target_language:
            translated = original_text
        else:
            translated = _FIXTURES.get((original_text, target_language))
            if translated is None:
                raise ValueError("No deterministic translation fixture is available.")
        return _validated_output(
            original_text,
            TranslationOutput(
                source_language=source_language,
                target_language=target_language,
                translated_text=translated,
                semantic_equivalence_status=SemanticEquivalenceStatus.EQUIVALENT,
                model=self.model,
                prompt_version=self.prompt_version,
            ),
        )


class OpenAITranslationService:
    prompt_version = TRANSLATION_PROMPT_VERSION

    def __init__(self, settings: Settings | None = None, client: Any | None = None):
        self._settings = settings or get_settings()
        self._client = client
        self.model = self._settings.openai_translation_model

    async def translate_message(
        self,
        original_text: str,
        source_language: AnalysisLanguageCode,
        target_language: AnalysisLanguageCode,
    ) -> TranslationOutput:
        client = self._client or self._create_client()
        response = await client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Translate service-agreement evidence without summarizing, "
                        "legal rewriting, invented context, or removed uncertainty. "
                        "Preserve negation; included versus separate; labour versus "
                        "materials; agreed versus proposed; fixed price versus "
                        "estimate; "
                        "before versus after; must versus may; deposits; amounts, "
                        "currencies, dates, quantities, and units exactly. Return "
                        "review_required if semantic equivalence cannot be maintained."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_language": source_language.value,
                            "target_language": target_language.value,
                            "original_text": original_text,
                            "model": self.model,
                            "prompt_version": self.prompt_version,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            text_format=TranslationOutput,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("Translation returned no structured output.")
        if (
            parsed.source_language != source_language
            or parsed.target_language != target_language
        ):
            raise ValueError("Translation returned mismatched languages.")
        if parsed.model != self.model or parsed.prompt_version != self.prompt_version:
            parsed = parsed.model_copy(
                update={"model": self.model, "prompt_version": self.prompt_version}
            )
        return _validated_output(original_text, parsed)

    def _create_client(self) -> AsyncOpenAI:
        key = self._settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise ValueError("Live translation is not configured yet.")
        return AsyncOpenAI(
            api_key=key.get_secret_value(),
            timeout=self._settings.openai_request_timeout_seconds,
            max_retries=0,
        )


_CRITICAL_PATTERN = re.compile(
    r"₹|\$|€|\b(?:INR|USD|EUR)\b|\d+(?:[,.]\d+)*(?:%|\s*(?:days?|hours?|weeks?))?",
    re.IGNORECASE,
)
_NEGATION_MARKERS = {
    AnalysisLanguageCode.ENGLISH: ("not", "no ", "separate", "excluded"),
    AnalysisLanguageCode.HINDI: ("नहीं", "अलग", "शामिल नहीं"),
}
_INCLUSION_MARKERS = {
    AnalysisLanguageCode.ENGLISH: ("include", "included", "including"),
    AnalysisLanguageCode.HINDI: ("शामिल",),
}


def _validated_output(
    original_text: str, output: TranslationOutput
) -> TranslationOutput:
    source_values = _CRITICAL_PATTERN.findall(original_text)
    translated_values = _CRITICAL_PATTERN.findall(output.translated_text)
    source_negative = any(
        marker in original_text.casefold()
        for marker in _NEGATION_MARKERS[output.source_language]
    )
    target_negative = any(
        marker in output.translated_text.casefold()
        for marker in _NEGATION_MARKERS[output.target_language]
    )
    source_inclusion = any(
        marker in original_text.casefold()
        for marker in _INCLUSION_MARKERS[output.source_language]
    )
    target_inclusion = any(
        marker in output.translated_text.casefold()
        for marker in _INCLUSION_MARKERS[output.target_language]
    )
    if (
        source_values != translated_values
        or source_negative != target_negative
        or source_inclusion != target_inclusion
        or output.semantic_equivalence_status != SemanticEquivalenceStatus.EQUIVALENT
    ):
        raise ValueError("Translation did not preserve critical agreement meaning.")
    return output.model_copy(
        update={
            "preserved_amounts": source_values,
            "preserved_currencies": [
                item
                for item in source_values
                if item in {"₹", "$", "€", "INR", "USD", "EUR"}
            ],
        }
    )


class TranslationService(Protocol):
    """Optional boundary for translating display text without changing evidence."""

    def translate(
        self,
        original_text: str,
        source_language: LanguageCode,
        target_language: LanguageCode,
    ) -> str: ...


def with_optional_translation(
    message: TranscriptTurn,
    target_language: LanguageCode,
    service: TranslationService | None,
) -> TranscriptTurn:
    if target_language == message.original_language or service is None:
        return message
    translated_text = service.translate(
        message.original_text,
        message.original_language,
        target_language,
    )
    return message.model_copy(
        update={
            "translations": {**message.translations, target_language: translated_text}
        }
    )
