from datetime import UTC, date, datetime, timedelta

from app.schemas.session import (
    AgreementTerm,
    ClarificationQuestion,
    EvidenceReference,
    LanguageCode,
    ParticipantTermStatus,
    PartyRole,
    TermStatus,
    TranscriptTurn,
)

CONFIRMED_BY_BOTH = {
    PartyRole.HIRER: ParticipantTermStatus.CONFIRMED,
    PartyRole.WORKER: ParticipantTermStatus.CONFIRMED,
}
CONFLICTING_BY_PARTY = {
    PartyRole.HIRER: ParticipantTermStatus.CONFLICTING,
    PartyRole.WORKER: ParticipantTermStatus.CONFLICTING,
}
NOT_STATED = {
    PartyRole.HIRER: ParticipantTermStatus.NOT_STATED,
    PartyRole.WORKER: ParticipantTermStatus.NOT_STATED,
}


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
            "₹1,200 covers my labour. Replacement parts are separate.",
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
            timestamp=started_at + timedelta(seconds=index - 1),
        )
        for index, (role, name, text) in enumerate(messages, start=1)
    ]


def _evidence(message: TranscriptTurn) -> EvidenceReference:
    return EvidenceReference(
        source="transcript",
        reference_id=message.id,
        participant_id=message.participant_id,
        message_id=message.id,
        original_text=message.original_text,
    )


def demo_terms(
    transcript: list[TranscriptTurn], today: date | None = None
) -> list[AgreementTerm]:
    messages = {message.id: message for message in transcript}
    current_date = today or date.today()
    return [
        AgreementTerm(
            id="fan-repair",
            label="Fan repair",
            status=TermStatus.CONFIRMED,
            value="Repair one fan",
            evidence=[_evidence(messages["message-1"])],
            participant_confirmations=CONFIRMED_BY_BOTH,
        ),
        AgreementTerm(
            id="switch-repair",
            label="Switch repair",
            status=TermStatus.CONFIRMED,
            value="Repair two switches",
            evidence=[_evidence(messages["message-1"])],
            participant_confirmations=CONFIRMED_BY_BOTH,
        ),
        AgreementTerm(
            id="labour-price",
            label="Labour price",
            status=TermStatus.CONFIRMED,
            value="₹1,200",
            evidence=[
                _evidence(messages["message-1"]),
                _evidence(messages["message-2"]),
            ],
            participant_confirmations=CONFIRMED_BY_BOTH,
        ),
        AgreementTerm(
            id="materials",
            label="Replacement parts",
            status=TermStatus.CONFLICT,
            value=(
                "Homeowner says parts are included in ₹1,200; electrician "
                "charges them separately"
            ),
            evidence=[
                _evidence(messages["message-1"]),
                _evidence(messages["message-2"]),
            ],
            participant_confirmations=CONFLICTING_BY_PARTY,
        ),
        AgreementTerm(
            id="start-date",
            label="Start date",
            status=TermStatus.CONFIRMED,
            value=current_date.isoformat(),
            evidence=[
                _evidence(messages["message-3"]),
                _evidence(messages["message-4"]),
            ],
            participant_confirmations=CONFIRMED_BY_BOTH,
        ),
        AgreementTerm(
            id="completion-time",
            label="Completion date or time",
            status=TermStatus.MISSING,
            participant_confirmations=NOT_STATED,
        ),
        AgreementTerm(
            id="payment-timing",
            label="Payment timing",
            status=TermStatus.MISSING,
            participant_confirmations=NOT_STATED,
        ),
        AgreementTerm(
            id="warranty",
            label="Warranty",
            status=TermStatus.MISSING,
            participant_confirmations=NOT_STATED,
        ),
        AgreementTerm(
            id="additional-work",
            label="Handling of additional work",
            status=TermStatus.MISSING,
            participant_confirmations=NOT_STATED,
        ),
    ]


def demo_questions() -> list[ClarificationQuestion]:
    return [
        ClarificationQuestion(
            id="materials-inclusion",
            term_id="materials",
            prompt=(
                "Does the ₹1,200 price include replacement parts, or are "
                "replacement parts charged separately?"
            ),
            options=["Parts are included", "Parts are charged separately"],
        )
    ]
