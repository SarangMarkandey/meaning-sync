import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import app
from app.schemas.analysis import (
    AgreementTerm,
    AgreementTopic,
    LanguageCode,
    MeaningState,
    ParticipantTermStatus,
)
from app.schemas.session import ParticipantLanguages, SessionStage
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


def analyze(service: SessionService, session_id: str):
    return asyncio.run(service.analyze(session_id))


def test_required_routes_are_registered() -> None:
    routes = set(app.openapi()["paths"])
    assert "/health" in routes
    assert "/api/v1/agreements/analyze" in routes
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
    assert first.order == 1
    assert first.original_text == (
        "I will pay ₹1,200 for repairing the fan and two switches, "
        "including replacement parts."
    )
    assert first.translations == {}


def test_state_transitions_cannot_be_skipped(service: SessionService) -> None:
    created = service.create_demo()
    assert created.stage == SessionStage.CREATED

    with pytest.raises(HTTPException, match="Expected stage discussion"):
        analyze(service, created.id)

    first_consent = service.submit_consent(created.id, "hirer", True)
    assert first_consent.stage == SessionStage.CONSENT_PENDING
    second_consent = service.submit_consent(created.id, "worker", True)
    assert second_consent.stage == SessionStage.DISCUSSION

    with pytest.raises(HTTPException, match="Expected stage analyzed"):
        service.begin_clarification(created.id)


def test_deterministic_agreement_meaning_and_evidence(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = analyze(service, discussion_session)
    terms = {term.topic: term for term in analyzed.terms}

    assert terms[AgreementTopic.SCOPE].state == MeaningState.ALIGNED
    assert terms[AgreementTopic.PRICE].state == MeaningState.ALIGNED
    assert "₹1,200" in terms[AgreementTopic.PRICE].summary
    assert terms[AgreementTopic.MATERIALS].state == MeaningState.CONFLICTING
    assert "disagree" in terms[AgreementTopic.MATERIALS].summary
    assert terms[AgreementTopic.TIMING].state == MeaningState.ALIGNED

    for term in analyzed.terms:
        if term.state != MeaningState.NOT_DISCUSSED:
            assert term.evidence
            assert term.evidence_message_ids
            assert all(evidence.message_id for evidence in term.evidence)
            assert all(evidence.original_text for evidence in term.evidence)
            assert all(evidence.original_language == "en" for evidence in term.evidence)


def test_not_discussed_terms_remain_separate_from_conflicts(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = analyze(service, discussion_session)
    not_discussed = {
        term.topic
        for term in analyzed.terms
        if term.state == MeaningState.NOT_DISCUSSED
    }
    conflicts = {
        term.topic for term in analyzed.terms if term.state == MeaningState.CONFLICTING
    }
    assert {
        AgreementTopic.COMPLETION,
        AgreementTopic.PAYMENT,
        AgreementTopic.WARRANTY,
        AgreementTopic.ADDITIONAL_WORK,
    }.issubset(not_discussed)
    assert conflicts == {AgreementTopic.MATERIALS}


def test_neutral_materials_clarification_is_generated(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = analyze(service, discussion_session)
    question = analyzed.clarification_questions[0]
    assert question.target == AgreementTopic.MATERIALS
    assert "include replacement parts" in question.prompt
    assert "charged separately" in question.prompt


def test_discussed_terms_require_provenance() -> None:
    participant_status = {
        "hirer": ParticipantTermStatus.CONFIRMED,
        "worker": ParticipantTermStatus.CONFIRMED,
    }
    with pytest.raises(ValidationError, match="require transcript evidence"):
        AgreementTerm(
            id="invalid",
            analysis_item_key="scope.work",
            topic=AgreementTopic.SCOPE,
            facet="work",
            label="Invalid inferred term",
            summary="Inferred without support.",
            state=MeaningState.ALIGNED,
            participant_confirmations=participant_status,
        )


def test_first_clarification_answer_is_hidden(
    service: SessionService, clarification_session: str
) -> None:
    first = service.answer(
        clarification_session,
        "clarify-materials",
        "hirer",
        "Parts are included",
    )
    assert first.revealed is False
    assert first.answers == []

    second = service.answer(
        clarification_session,
        "clarify-materials",
        "worker",
        "Parts are charged separately",
    )
    assert second.revealed is True
    assert second.resolved is False
    assert second.term is not None
    assert second.term.state == MeaningState.CONFLICTING


def test_semantically_compatible_answers_resolve_materials(
    service: SessionService, clarification_session: str
) -> None:
    first = service.answer(
        clarification_session,
        "clarify-materials",
        "hirer",
        "Parts are charged separately",
    )
    assert first.revealed is False
    second = service.answer(
        clarification_session,
        "clarify-materials",
        "worker",
        "Replacement parts are separate",
    )
    assert second.resolved is True
    assert second.answers[0].answer != second.answers[1].answer
    assert second.answers[0].meaning == second.answers[1].meaning
    assert second.term is not None
    assert second.term.state == MeaningState.ALIGNED


def test_two_party_confirmation_and_receipt_preserve_gaps(
    service: SessionService, clarification_session: str
) -> None:
    service.answer(
        clarification_session,
        "clarify-materials",
        "hirer",
        "Parts are included",
    )
    service.answer(
        clarification_session,
        "clarify-materials",
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
    states = {term.topic: term.state for term in receipt.terms}
    assert states[AgreementTopic.MATERIALS] == MeaningState.CONFLICTING
    assert states[AgreementTopic.COMPLETION] == MeaningState.NOT_DISCUSSED
    assert len(receipt.confirmations) == 2
    assert len(receipt.integrity_hash) == 64


def test_bilingual_demo_receipt_updates_both_localized_meanings(
    service: SessionService,
) -> None:
    created = service.create_demo(
        ParticipantLanguages(hirer=LanguageCode.HINDI, worker=LanguageCode.ENGLISH)
    )
    service.submit_consent(created.id, "hirer", True)
    service.submit_consent(created.id, "worker", True)
    analyzed = analyze(service, created.id)
    service.begin_clarification(created.id)
    question = analyzed.clarification_questions[0]
    service.answer(created.id, question.id, "hirer", "पुर्जों का खर्च अलग है")
    resolved = service.answer(
        created.id, question.id, "worker", "Parts are charged separately"
    )
    assert resolved.resolved is True
    assert resolved.term is not None
    assert (
        resolved.term.localizations[LanguageCode.ENGLISH].summary
        == "Parts are charged separately"
    )
    assert (
        resolved.term.localizations[LanguageCode.HINDI].summary == "पुर्जों का खर्च अलग है"
    )
    service.confirm(created.id, "hirer", True, "मैंने साझा समझ की समीक्षा की।")
    service.confirm(created.id, "worker", True, "I reviewed the shared meaning.")
    receipt = service.create_receipt(created.id)
    assert receipt.disclaimer_hi.startswith("MeaningSync स्पष्टता रसीद")
    assert len(receipt.integrity_hash) == 64
