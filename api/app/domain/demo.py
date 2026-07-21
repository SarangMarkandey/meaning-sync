from datetime import UTC, datetime, timedelta

from app.schemas.session import (
    LanguageCode,
    ParticipantLanguages,
    PartyRole,
    TranscriptTurn,
)


def demo_transcript(
    session_id: str, languages: ParticipantLanguages | None = None
) -> list[TranscriptTurn]:
    started_at = datetime.now(UTC)
    selected = languages or ParticipantLanguages()
    bilingual = (
        selected.hirer == LanguageCode.HINDI and selected.worker == LanguageCode.ENGLISH
    )
    messages = [
        (
            PartyRole.HIRER,
            "Homeowner",
            (
                "मैं पंखे और दो स्विच की मरम्मत के लिए ₹1,200 दूँगा, जिसमें बदलने वाले पुर्जे शामिल हैं।"
                if bilingual
                else "I will pay ₹1,200 for repairing the fan and two switches, "
                "including replacement parts."
            ),
            LanguageCode.HINDI if bilingual else LanguageCode.ENGLISH,
            {
                LanguageCode.ENGLISH: (
                    "I will pay ₹1,200 to repair the fan and two switches, including "
                    "replacement parts."
                )
            }
            if bilingual
            else {},
        ),
        (
            PartyRole.WORKER,
            "Electrician",
            (
                "₹1,200 covers my labour. Replacement parts are separate."
                if bilingual
                else "I will repair the fan and two switches. ₹1,200 covers my labour. "
                "Replacement parts are separate."
            ),
            LanguageCode.ENGLISH,
            {
                LanguageCode.HINDI: (
                    "₹1,200 मेरी मजदूरी के लिए है। बदलने वाले पुर्जों का खर्च अलग है।"
                )
            }
            if bilingual
            else {},
        ),
        (
            PartyRole.HIRER,
            "Homeowner",
            "काम आज शुरू हो सकता है।" if bilingual else "The work can start today.",
            LanguageCode.HINDI if bilingual else LanguageCode.ENGLISH,
            {LanguageCode.ENGLISH: "The work can start today."} if bilingual else {},
        ),
        (
            PartyRole.WORKER,
            "Electrician",
            "Yes, I can start today.",
            LanguageCode.ENGLISH,
            {LanguageCode.HINDI: "हाँ, मैं आज काम शुरू कर सकता हूँ।"} if bilingual else {},
        ),
    ]
    return [
        TranscriptTurn(
            id=f"message-{index}",
            session_id=session_id,
            participant_id=role,
            speaker=role,
            speaker_name=name,
            original_text=text,
            original_language=language,
            order=index,
            timestamp=started_at + timedelta(seconds=index - 1),
            translations=translations,
        )
        for index, (role, name, text, language, translations) in enumerate(
            messages, start=1
        )
    ]
