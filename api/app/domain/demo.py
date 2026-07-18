from datetime import UTC, datetime, timedelta

from app.schemas.session import LanguageCode, PartyRole, TranscriptTurn


def demo_transcript(session_id: str) -> list[TranscriptTurn]:
    started_at = datetime.now(UTC)
    messages = [
        (
            PartyRole.HIRER,
            "Homeowner",
            "I will pay ₹1,200 for repairing the fan and two switches, "
            "including replacement parts.",
        ),
        (
            PartyRole.WORKER,
            "Electrician",
            "I will repair the fan and two switches. ₹1,200 covers my labour. "
            "Replacement parts are separate.",
        ),
        (PartyRole.HIRER, "Homeowner", "The work can start today."),
        (PartyRole.WORKER, "Electrician", "Yes, I can start today."),
    ]
    return [
        TranscriptTurn(
            id=f"message-{index}",
            session_id=session_id,
            participant_id=role,
            speaker=role,
            speaker_name=name,
            original_text=text,
            original_language=LanguageCode.ENGLISH,
            order=index,
            timestamp=started_at + timedelta(seconds=index - 1),
        )
        for index, (role, name, text) in enumerate(messages, start=1)
    ]
