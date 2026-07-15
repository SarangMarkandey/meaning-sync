from typing import Protocol

from app.schemas.session import LanguageCode, TranscriptTurn


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
