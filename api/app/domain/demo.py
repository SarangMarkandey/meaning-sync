from datetime import date

from app.schemas.session import (
    AgreementTerm,
    ClarificationQuestion,
    EvidenceReference,
    PartyRole,
    TermStatus,
    TranscriptTurn,
)


def demo_transcript() -> list[TranscriptTurn]:
    return [
        TranscriptTurn(
            id="turn-1",
            speaker=PartyRole.HIRER,
            speaker_name="Asha",
            language="hinglish",
            text="Ravi ji, aaj ceiling fan aur do switches repair karne hain.",
        ),
        TranscriptTurn(
            id="turn-2",
            speaker=PartyRole.WORKER,
            speaker_name="Ravi",
            language="hinglish",
            text=(
                "Theek hai: fan aur dono switches. Labour ka total ₹1,200 hoga, "
                "aur main aaj shuru karunga."
            ),
        ),
        TranscriptTurn(
            id="turn-3",
            speaker=PartyRole.HIRER,
            speaker_name="Asha",
            language="hinglish",
            text=(
                "Haan, fan aur do switches ke labour ke ₹1,200 theek hain. "
                "Replacement parts bhi included hain na?"
            ),
        ),
        TranscriptTurn(
            id="turn-4",
            speaker=PartyRole.WORKER,
            speaker_name="Ravi",
            language="hinglish",
            text=(
                "Kaam aur labour price confirmed. Lekin replacement parts ₹1,200 "
                "mein included nahi hain; woh alag lagenge."
            ),
        ),
    ]


def _evidence(turn_id: str, excerpt: str) -> EvidenceReference:
    return EvidenceReference(source="transcript", reference_id=turn_id, excerpt=excerpt)


def demo_terms(today: date | None = None) -> list[AgreementTerm]:
    current_date = today or date.today()
    return [
        AgreementTerm(
            id="scope",
            label="Scope of work",
            status=TermStatus.CONFIRMED,
            value="Repair one ceiling fan and two switches",
            evidence=[
                _evidence(
                    "turn-3", "fan aur do switches ke labour ke ₹1,200 theek hain"
                ),
                _evidence("turn-4", "Kaam aur labour price confirmed"),
            ],
        ),
        AgreementTerm(
            id="labour-price",
            label="Labour price",
            status=TermStatus.CONFIRMED,
            value="₹1,200",
            evidence=[
                _evidence("turn-2", "Labour ka total ₹1,200 hoga"),
                _evidence("turn-3", "labour ke ₹1,200 theek hain"),
            ],
        ),
        AgreementTerm(
            id="materials",
            label="Replacement parts",
            status=TermStatus.CONFLICT,
            value="Asha expects parts included; Ravi expects a separate charge",
            evidence=[
                _evidence("turn-3", "Replacement parts bhi included hain na?"),
                _evidence("turn-4", "replacement parts ₹1,200 mein included nahi hain"),
            ],
        ),
        AgreementTerm(
            id="start-date",
            label="Start date",
            status=TermStatus.CONFIRMED,
            value=current_date.isoformat(),
            evidence=[
                _evidence("turn-1", "aaj"),
                _evidence("turn-2", "main aaj shuru karunga"),
            ],
        ),
        AgreementTerm(
            id="completion-time",
            label="Completion time",
            status=TermStatus.MISSING,
        ),
        AgreementTerm(
            id="payment-timing",
            label="Payment timing",
            status=TermStatus.MISSING,
        ),
        AgreementTerm(
            id="additional-work",
            label="Additional-work policy",
            status=TermStatus.MISSING,
        ),
    ]


def demo_questions() -> list[ClarificationQuestion]:
    return [
        ClarificationQuestion(
            id="materials-inclusion",
            term_id="materials",
            prompt="Are replacement parts included in the ₹1,200 labour price?",
            options=["Parts are included", "Parts are charged separately"],
        )
    ]
