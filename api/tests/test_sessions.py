from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import app
from app.schemas.session import (
    AgreementTerm,
    LanguageCode,
    ParticipantLanguages,
    ParticipantTermStatus,
    SessionStage,
    TermStatus,
)
from app.services.sessions import SessionService


class TranslationSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, LanguageCode, LanguageCode]] = []

    def translate(
        self,
        original_text: str,
        source_language: LanguageCode,
        target_language: LanguageCode,
    ) -> str:
        self.calls.append((original_text, source_language, target_language))
        return f"translated: {original_text}"


def test_required_routes_are_registered() -> None:
    routes = set(app.openapi()["paths"])
    assert "/health" in routes
    assert "/api/v1/demo/sessions" in routes
    assert "/api/v1/demo/sessions/{session_id}" in routes
    assert "/api/v1/demo/sessions/{session_id}/receipt" in routes


def test_demo_defaults_both_participants_to_english(
    service: SessionService,
) -> None:
    session = service.create_demo()
    assert {participant.language for participant in session.participants} == {
        LanguageCode.ENGLISH
    }
    assert {
        participant.requested_display_language for participant in session.participants
    } == {LanguageCode.ENGLISH}


def test_participant_languages_are_independent_and_strict() -> None:
    settings = ParticipantLanguages(hirer="en", worker="hi")
    assert settings.hirer == LanguageCode.ENGLISH
    assert settings.worker == LanguageCode.HINDI

    with pytest.raises(ValidationError, match="Input should be 'en' or 'hi'"):
        ParticipantLanguages(hirer="fr", worker="en")


def test_optional_translation_preserves_original_message() -> None:
    translator = TranslationSpy()
    settings = ParticipantLanguages(hirer="en", worker="hi")
    session = SessionService(translator).create_demo(settings)

    assert [participant.language for participant in session.participants] == [
        LanguageCode.ENGLISH,
        LanguageCode.HINDI,
    ]
    assert len(translator.calls) == len(session.transcript)
    first = session.transcript[0]
    assert first.original_language == LanguageCode.ENGLISH
    assert first.original_text.startswith("I will pay ₹1,200")
    assert first.translations[LanguageCode.HINDI].startswith("translated:")


def test_english_session_does_not_request_translation() -> None:
    translator = TranslationSpy()
    session = SessionService(translator).create_demo()
    assert translator.calls == []
    assert all(not message.translations for message in session.transcript)


def test_original_message_and_speaker_provenance_are_preserved(
    service: SessionService,
) -> None:
    session = service.create_demo()
    first = session.transcript[0]
    assert first.session_id == session.id
    assert first.participant_id == "hirer"
    assert first.speaker_name == "Homeowner"
    assert first.original_language == LanguageCode.ENGLISH
    assert first.original_text == (
        "I will pay ₹1,200 for repairing the fan and two switches, "
        "including replacement parts."
    )
    assert first.translations == {}


def test_state_transitions_cannot_be_skipped(service: SessionService) -> None:
    created = service.create_demo()
    assert created.stage == SessionStage.CREATED

    with pytest.raises(HTTPException, match="Expected stage discussion"):
        service.analyze(created.id)

    first_consent = service.submit_consent(created.id, "hirer", True)
    assert first_consent.stage == SessionStage.CONSENT_PENDING
    second_consent = service.submit_consent(created.id, "worker", True)
    assert second_consent.stage == SessionStage.DISCUSSION

    with pytest.raises(HTTPException, match="Expected stage analyzed"):
        service.begin_clarification(created.id)


def test_english_agreement_meaning_and_evidence(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = service.analyze(discussion_session)
    terms = {term.id: term for term in analyzed.terms}

    assert terms["fan-repair"].status == TermStatus.CONFIRMED
    assert terms["switch-repair"].status == TermStatus.CONFIRMED
    assert terms["labour-price"].value == "₹1,200"
    assert terms["materials"].status == TermStatus.CONFLICT
    assert "included" in (terms["materials"].value or "")
    assert terms["start-date"].status == TermStatus.CONFIRMED
    assert terms["start-date"].value == date.today().isoformat()

    for term in analyzed.terms:
        if term.status != TermStatus.MISSING:
            assert term.evidence
            assert all(evidence.message_id for evidence in term.evidence)
            assert all(evidence.original_text for evidence in term.evidence)
            assert all(evidence.participant_id for evidence in term.evidence)


def test_missing_terms_remain_separate_from_conflicts(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = service.analyze(discussion_session)
    missing_ids = {term.id for term in analyzed.terms if term.status == "missing"}
    conflict_ids = {term.id for term in analyzed.terms if term.status == "conflict"}
    assert missing_ids == {
        "completion-time",
        "payment-timing",
        "warranty",
        "additional-work",
    }
    assert conflict_ids == {"materials"}


def test_neutral_materials_clarification_is_generated(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = service.analyze(discussion_session)
    question = analyzed.clarification_questions[0]
    assert question.term_id == "materials"
    assert "include replacement parts" in question.prompt
    assert "charged separately" in question.prompt


def test_non_missing_terms_require_provenance() -> None:
    participant_status = {
        "hirer": ParticipantTermStatus.CONFIRMED,
        "worker": ParticipantTermStatus.CONFIRMED,
    }
    with pytest.raises(ValidationError, match="require evidence"):
        AgreementTerm(
            id="invalid",
            label="Invalid inferred term",
            status=TermStatus.CONFIRMED,
            value="inferred",
            participant_confirmations=participant_status,
        )


def test_first_clarification_answer_is_hidden(
    service: SessionService, clarification_session: str
) -> None:
    first = service.answer(
        clarification_session,
        "materials-inclusion",
        "hirer",
        "Parts are included",
    )
    assert first.revealed is False
    assert first.answers == []

    second = service.answer(
        clarification_session,
        "materials-inclusion",
        "worker",
        "Parts are charged separately",
    )
    assert second.revealed is True
    assert second.resolved is False
    assert second.term is not None
    assert second.term.status == TermStatus.CONFLICT


def test_semantically_compatible_answers_resolve_materials(
    service: SessionService, clarification_session: str
) -> None:
    first = service.answer(
        clarification_session,
        "materials-inclusion",
        "hirer",
        "Parts are charged separately",
    )
    assert first.revealed is False
    second = service.answer(
        clarification_session,
        "materials-inclusion",
        "worker",
        "Replacement parts are separate",
    )
    assert second.resolved is True
    assert second.answers[0].answer != second.answers[1].answer
    assert second.answers[0].meaning == second.answers[1].meaning
    assert second.term is not None
    assert second.term.status == TermStatus.CONFIRMED


def test_two_party_confirmation_and_receipt_preserve_gaps(
    service: SessionService, clarification_session: str
) -> None:
    service.answer(
        clarification_session,
        "materials-inclusion",
        "hirer",
        "Parts are included",
    )
    service.answer(
        clarification_session,
        "materials-inclusion",
        "worker",
        "Parts are charged separately",
    )

    first = service.confirm(
        clarification_session,
        "hirer",
        True,
        "The work starts today; the parts policy remains unresolved.",
    )
    assert first.stage == SessionStage.TEACHBACK
    second = service.confirm(
        clarification_session,
        "worker",
        True,
        "The work starts today; the parts policy remains unresolved.",
    )
    assert second.stage == SessionStage.CONFIRMATION

    receipt = service.create_receipt(clarification_session)
    statuses = {term.id: term.status for term in receipt.terms}
    assert statuses["materials"] == TermStatus.CONFLICT
    assert statuses["completion-time"] == TermStatus.MISSING
    assert len(receipt.confirmations) == 2
