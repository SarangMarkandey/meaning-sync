from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException, status

from app.domain.demo import demo_transcript
from app.schemas.analysis import (
    AgreementAnalysisRequest,
    AnalysisMessage,
    AnalysisParticipant,
    EvidenceReference,
    MeaningState,
)
from app.schemas.session import (
    AgreementTerm,
    ClarificationAnswer,
    ClarificationQuestion,
    ClarificationResult,
    ClarityReceipt,
    ConsentStatus,
    MaterialsPolicy,
    ParticipantLanguages,
    PartyConfirmation,
    PartyRole,
    SessionMode,
    SessionParticipant,
    SessionStage,
    SessionView,
    TranscriptTurn,
)
from app.services.analyzers import AgreementAnalyzer, DeterministicAgreementAnalyzer
from app.services.analyzers.validation import ROLE_NAMES
from app.services.translation import TranslationService, with_optional_translation

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
    participants: list[SessionParticipant]
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
    def __init__(
        self,
        translation_service: TranslationService | None = None,
        analyzer: AgreementAnalyzer | None = None,
    ) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()
        self._translation_service = translation_service
        self._analyzer = analyzer or DeterministicAgreementAnalyzer()

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()

    def create_demo(
        self, participant_languages: ParticipantLanguages | None = None
    ) -> SessionView:
        languages = participant_languages or ParticipantLanguages()
        session_id = str(uuid4())
        participants = [
            SessionParticipant(
                id=PartyRole.HIRER,
                role=PartyRole.HIRER,
                display_name="Homeowner",
                language=languages.hirer,
                requested_display_language=languages.hirer,
            ),
            SessionParticipant(
                id=PartyRole.WORKER,
                role=PartyRole.WORKER,
                display_name="Electrician",
                language=languages.worker,
                requested_display_language=languages.worker,
            ),
        ]
        transcript = demo_transcript(session_id)
        for target_language in {
            participant.requested_display_language for participant in participants
        }:
            transcript = [
                with_optional_translation(
                    message, target_language, self._translation_service
                )
                for message in transcript
            ]
        record = SessionRecord(
            id=session_id,
            mode=SessionMode.DEMO,
            stage=SessionStage.CREATED,
            created_at=datetime.now(UTC),
            participants=participants,
            consent={role: ConsentStatus.PENDING for role in PartyRole},
            transcript=transcript,
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

    async def analyze(self, session_id: str) -> SessionView:
        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.DISCUSSION)
            request = self._analysis_request(record)

        analysis = await self._analyzer.analyze(request)

        with self._lock:
            record = self._record(session_id)
            self._require_stage(record, SessionStage.DISCUSSION)
            record.terms = analysis.terms
            record.questions = (
                [analysis.primary_clarification]
                if analysis.primary_clarification is not None
                else []
            )
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
            meaning = self._materials_meaning(answer)
            question_answers = record.answers.setdefault(question_id, {})
            question_answers[party] = ClarificationAnswer(
                question_id=question_id,
                party=party,
                answer=answer,
                meaning=meaning,
                submitted_at=datetime.now(UTC),
            )
            if len(question_answers) < len(PartyRole):
                return ClarificationResult(question=question, revealed=False)

            revealed_answers = [question_answers[role] for role in PartyRole]
            compatible = len({item.meaning for item in revealed_answers}) == 1
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
                participant_id=answer.party,
                role=answer.party,
                speaker_name=ROLE_NAMES[answer.party],
                original_text=answer.answer,
                original_language=next(
                    participant.language
                    for participant in record.participants
                    if participant.role == answer.party
                ),
            )
            for answer in answers
        ]
        record.terms[index] = AgreementTerm(
            id=current.id,
            analysis_item_key=current.analysis_item_key,
            topic=current.topic,
            facet=current.facet,
            label=current.label,
            state=MeaningState.ALIGNED if compatible else MeaningState.CONFLICTING,
            summary=(
                (
                    "Parts are included"
                    if answers[0].meaning == MaterialsPolicy.INCLUDED
                    else "Parts are charged separately"
                )
                if compatible
                else "The parties gave different clarification answers"
            ),
            participant_positions=current.participant_positions,
            evidence_message_ids=current.evidence_message_ids,
            evidence=[*current.evidence, *clarification_evidence],
            participant_confirmations={
                role: ("confirmed" if compatible else "conflicting")
                for role in PartyRole
            },
            clarification_target=(None if compatible else current.analysis_item_key),
        )
        return record.terms[index]

    @staticmethod
    def _materials_meaning(answer: str) -> MaterialsPolicy:
        normalized = " ".join(answer.casefold().replace("₹1,200", "").split())
        included_answers = {
            "included",
            "parts are included",
            "replacement parts are included",
            "include replacement parts",
        }
        separate_answers = {
            "charged_separately",
            "separate",
            "parts are charged separately",
            "replacement parts are charged separately",
            "replacement parts are separate",
        }
        if normalized in included_answers:
            return MaterialsPolicy.INCLUDED
        if normalized in separate_answers:
            return MaterialsPolicy.CHARGED_SEPARATELY
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Answer must express whether replacement parts are included or separate",
        )

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
    def _analysis_request(record: SessionRecord) -> AgreementAnalysisRequest:
        return AgreementAnalysisRequest(
            session_id=record.id,
            mode=record.mode,
            participants=[
                AnalysisParticipant(
                    id=participant.id.value,
                    role=participant.role,
                    language=participant.language,
                )
                for participant in record.participants
            ],
            messages=[
                AnalysisMessage(
                    message_id=message.id,
                    speaker_id=message.participant_id.value,
                    original_text=message.original_text,
                    original_language=message.original_language,
                    order=message.order,
                    timestamp=message.timestamp,
                )
                for message in record.transcript
            ],
        )

    @staticmethod
    def _view(record: SessionRecord) -> SessionView:
        return SessionView(
            id=record.id,
            mode=record.mode,
            stage=record.stage,
            created_at=record.created_at,
            participants=record.participants,
            consent=record.consent,
            transcript=record.transcript,
            terms=record.terms,
            clarification_questions=record.questions,
            confirmations=list(record.confirmations.values()),
        )


session_service = SessionService()
