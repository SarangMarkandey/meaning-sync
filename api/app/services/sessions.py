from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException, status

from app.domain.demo import demo_questions, demo_terms, demo_transcript
from app.schemas.session import (
    AgreementTerm,
    ClarificationAnswer,
    ClarificationQuestion,
    ClarificationResult,
    ClarityReceipt,
    ConsentStatus,
    EvidenceReference,
    PartyConfirmation,
    PartyRole,
    SessionMode,
    SessionStage,
    SessionView,
    TermStatus,
    TranscriptTurn,
)

NEXT_STAGE = {
    SessionStage.CREATED: SessionStage.CONSENT_PENDING,
    SessionStage.CONSENT_PENDING: SessionStage.DISCUSSION,
    SessionStage.DISCUSSION: SessionStage.ANALYZED,
    SessionStage.ANALYZED: SessionStage.CLARIFICATION,
    SessionStage.CLARIFICATION: SessionStage.TEACHBACK,
    SessionStage.TEACHBACK: SessionStage.CONFIRMATION,
    SessionStage.CONFIRMATION: SessionStage.COMPLETED,
}


@dataclass
class SessionRecord:
    id: str
    mode: SessionMode
    stage: SessionStage
    created_at: datetime
    consent: dict[PartyRole, ConsentStatus]
    transcript: list[TranscriptTurn]
    terms: list[AgreementTerm] = field(default_factory=list)
    questions: list[ClarificationQuestion] = field(default_factory=list)
    answers: dict[str, dict[PartyRole, ClarificationAnswer]] = field(
        default_factory=dict
    )
    confirmations: dict[PartyRole, PartyConfirmation] = field(default_factory=dict)
    receipt: ClarityReceipt | None = None


class SessionService:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()

    def create_demo(self) -> SessionView:
        record = SessionRecord(
            id=str(uuid4()),
            mode=SessionMode.DEMO,
            stage=SessionStage.CREATED,
            created_at=datetime.now(UTC),
            consent={role: ConsentStatus.PENDING for role in PartyRole},
            transcript=demo_transcript(),
        )
        with self._lock:
            self._sessions[record.id] = record
        return self._view(record)

    def get(self, session_id: str) -> SessionView:
        return self._view(self._record(session_id))

    def submit_consent(
        self, session_id: str, party: PartyRole, accepted: bool
    ) -> SessionView:
        with self._lock:
            record = self._record(session_id)
            if record.stage == SessionStage.CREATED:
                self._transition(record, SessionStage.CONSENT_PENDING)
            self._require_stage(record, SessionStage.CONSENT_PENDING)
            record.consent[party] = (
                ConsentStatus.ACCEPTED if accepted else ConsentStatus.DECLINED
            )
            if all(
                value == ConsentStatus.ACCEPTED for value in record.consent.values()
            ):
                self._transition(record, SessionStage.DISCUSSION)
            return self._view(record)

    def analyze(self, session_id: str) -> SessionView:
        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.DISCUSSION)
            record.terms = demo_terms()
            record.questions = demo_questions()
            self._transition(record, SessionStage.ANALYZED)
            return self._view(record)

    def begin_clarification(self, session_id: str) -> SessionView:
        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.ANALYZED)
            self._transition(record, SessionStage.CLARIFICATION)
            return self._view(record)

    def answer(
        self,
        session_id: str,
        question_id: str,
        party: PartyRole,
        answer: str,
    ) -> ClarificationResult:
        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.CLARIFICATION)
            question = next(
                (item for item in record.questions if item.id == question_id), None
            )
            if question is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
            if answer not in question.options:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Answer must match one of the provided options",
                )
            question_answers = record.answers.setdefault(question_id, {})
            question_answers[party] = ClarificationAnswer(
                question_id=question_id,
                party=party,
                answer=answer,
                submitted_at=datetime.now(UTC),
            )
            if len(question_answers) < len(PartyRole):
                return ClarificationResult(question=question, revealed=False)

            revealed_answers = [question_answers[role] for role in PartyRole]
            compatible = len({item.answer for item in revealed_answers}) == 1
            term = self._resolve_term(record, question, revealed_answers, compatible)
            self._transition(record, SessionStage.TEACHBACK)
            return ClarificationResult(
                question=question,
                revealed=True,
                answers=revealed_answers,
                resolved=compatible,
                term=term,
            )

    def confirm(
        self,
        session_id: str,
        party: PartyRole,
        confirmed: bool,
        teachback: str,
    ) -> SessionView:
        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.TEACHBACK)
            record.confirmations[party] = PartyConfirmation(
                party=party,
                confirmed=confirmed,
                teachback=teachback,
                submitted_at=datetime.now(UTC),
            )
            if all(
                record.confirmations.get(role) and record.confirmations[role].confirmed
                for role in PartyRole
            ):
                self._transition(record, SessionStage.CONFIRMATION)
            return self._view(record)

    def create_receipt(self, session_id: str) -> ClarityReceipt:
        with self._lock:
            record = self._record(session_id)
            if record.receipt is not None:
                return record.receipt
            self._require_stage(record, SessionStage.CONFIRMATION)
            self._transition(record, SessionStage.COMPLETED)
            record.receipt = ClarityReceipt(
                session_id=record.id,
                terms=record.terms,
                confirmations=list(record.confirmations.values()),
                completed_at=datetime.now(UTC),
            )
            return record.receipt

    def _resolve_term(
        self,
        record: SessionRecord,
        question: ClarificationQuestion,
        answers: list[ClarificationAnswer],
        compatible: bool,
    ) -> AgreementTerm:
        index = next(
            (i for i, term in enumerate(record.terms) if term.id == question.term_id),
            None,
        )
        if index is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Question has no term")
        current = record.terms[index]
        clarification_evidence = [
            EvidenceReference(
                source="clarification",
                reference_id=f"{answer.question_id}:{answer.party.value}",
                excerpt=answer.answer,
            )
            for answer in answers
        ]
        record.terms[index] = AgreementTerm(
            id=current.id,
            label=current.label,
            status=TermStatus.CONFIRMED if compatible else TermStatus.CONFLICT,
            value=(
                answers[0].answer
                if compatible
                else "The parties gave different clarification answers"
            ),
            evidence=[*current.evidence, *clarification_evidence],
        )
        return record.terms[index]

    def _transition(self, record: SessionRecord, target: SessionStage) -> None:
        if NEXT_STAGE.get(record.stage) != target:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Cannot move from {record.stage.value} to {target.value}",
            )
        record.stage = target

    @staticmethod
    def _require_stage(record: SessionRecord, expected: SessionStage) -> None:
        if record.stage != expected:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                (
                    f"Expected stage {expected.value}; "
                    f"current stage is {record.stage.value}"
                ),
            )

    def _record(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        return record

    @staticmethod
    def _view(record: SessionRecord) -> SessionView:
        return SessionView(
            id=record.id,
            mode=record.mode,
            stage=record.stage,
            created_at=record.created_at,
            consent=record.consent,
            transcript=record.transcript,
            terms=record.terms,
            clarification_questions=record.questions,
            confirmations=list(record.confirmations.values()),
        )


session_service = SessionService()
