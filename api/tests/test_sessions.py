import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import app
from app.schemas.session import AgreementTerm, SessionStage, TermStatus
from app.services.sessions import SessionService


def test_required_routes_are_registered() -> None:
    routes = set(app.openapi()["paths"])
    assert "/health" in routes
    assert "/api/v1/demo/sessions" in routes
    assert "/api/v1/demo/sessions/{session_id}/receipt" in routes


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


def test_non_missing_terms_require_evidence(
    service: SessionService, discussion_session: str
) -> None:
    analyzed = service.analyze(discussion_session)
    assert all(term.evidence for term in analyzed.terms if term.status != "missing")
    assert all(not term.evidence for term in analyzed.terms if term.status == "missing")

    with pytest.raises(ValidationError, match="require evidence"):
        AgreementTerm(
            id="invalid",
            label="Invalid inferred term",
            status=TermStatus.CONFIRMED,
            value="inferred",
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
    assert len(second.answers) == 2
    assert second.resolved is False
    assert second.term is not None
    assert second.term.status == TermStatus.CONFLICT


def test_compatible_answers_resolve_materials(
    service: SessionService, clarification_session: str
) -> None:
    for party in ("hirer", "worker"):
        result = service.answer(
            clarification_session,
            "materials-inclusion",
            party,
            "Parts are charged separately",
        )
    assert result.resolved is True
    assert result.term is not None
    assert result.term.status == TermStatus.CONFIRMED


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
        "Labour is ₹1,200; parts remain unresolved.",
    )
    assert first.stage == SessionStage.TEACHBACK
    second = service.confirm(
        clarification_session,
        "worker",
        True,
        "Labour is ₹1,200; parts remain unresolved.",
    )
    assert second.stage == SessionStage.CONFIRMATION

    receipt = service.create_receipt(clarification_session)
    statuses = {term.id: term.status for term in receipt.terms}
    assert statuses["materials"] == TermStatus.CONFLICT
    assert statuses["completion-time"] == TermStatus.MISSING
    assert len(receipt.confirmations) == 2
