from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AgreementFacet,
    AgreementTerm,
    AgreementTopic,
    AnalysisErrorCode,
    AnalysisStatus,
    AnalysisWarning,
    AnalysisWarningCode,
    ClarificationQuestion,
    EvidenceReference,
    MeaningState,
    ModelAgreementTerm,
    ParticipantPosition,
    ParticipantTermStatus,
    PartyRole,
)
from app.services.analyzers.base import AnalysisFailure

TOPIC_FACETS = {
    AgreementTopic.SCOPE: {AgreementFacet.WORK},
    AgreementTopic.PRICE: {AgreementFacet.AMOUNT},
    AgreementTopic.MATERIALS: {AgreementFacet.INCLUSION},
    AgreementTopic.TIMING: {AgreementFacet.START},
    AgreementTopic.COMPLETION: {AgreementFacet.DEADLINE},
    AgreementTopic.PAYMENT: {AgreementFacet.TIMING},
    AgreementTopic.RESPONSIBILITIES: {AgreementFacet.ASSIGNMENT},
    AgreementTopic.WARRANTY: {AgreementFacet.COVERAGE},
    AgreementTopic.CANCELLATION: {AgreementFacet.POLICY},
    AgreementTopic.ADDITIONAL_WORK: {AgreementFacet.POLICY},
    AgreementTopic.OTHER: {AgreementFacet.DETAIL},
}

ITEM_LABELS = {
    (AgreementTopic.SCOPE, AgreementFacet.WORK): "Scope of work",
    (AgreementTopic.PRICE, AgreementFacet.AMOUNT): "Labour price",
    (
        AgreementTopic.MATERIALS,
        AgreementFacet.INCLUSION,
    ): "Materials and replacement parts",
    (AgreementTopic.TIMING, AgreementFacet.START): "Start timing",
    (AgreementTopic.COMPLETION, AgreementFacet.DEADLINE): ("Completion date or time"),
    (AgreementTopic.PAYMENT, AgreementFacet.TIMING): "Payment timing",
    (AgreementTopic.RESPONSIBILITIES, AgreementFacet.ASSIGNMENT): ("Responsibilities"),
    (AgreementTopic.WARRANTY, AgreementFacet.COVERAGE): "Warranty",
    (AgreementTopic.CANCELLATION, AgreementFacet.POLICY): "Cancellation",
    (AgreementTopic.ADDITIONAL_WORK, AgreementFacet.POLICY): "Additional work",
    (AgreementTopic.OTHER, AgreementFacet.DETAIL): "Other agreement detail",
}

ROLE_NAMES = {
    PartyRole.HIRER: "Homeowner",
    PartyRole.WORKER: "Electrician",
}

CLARIFICATION_WARNING = (
    "The agreement map is ready, but a clarification question could not be "
    "generated. Review the highlighted conflict."
)


def invalid_output(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        AnalysisErrorCode.INVALID_MODEL_OUTPUT,
        message,
        retryable=True,
        status_code=502,
    )


def _build_clarification(
    terms: list[AgreementTerm],
    candidates: list[tuple[str, str]],
    *,
    clarification_unavailable: bool,
) -> tuple[ClarificationQuestion | None, bool]:
    if clarification_unavailable:
        return None, True
    if not candidates:
        return None, False
    if len(candidates) != 1:
        return None, True

    term_id, question = candidates[0]
    term_index = next(
        (index for index, term in enumerate(terms) if term.id == term_id),
        None,
    )
    if term_index is None:
        return None, True
    term = terms[term_index]
    if term.state not in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}:
        return None, True
    if not _is_neutral_question(question):
        return None, True

    terms[term_index] = term.model_copy(
        update={"clarification_target": term.analysis_item_key}
    )
    return (
        ClarificationQuestion(
            id=f"clarify-{term.topic.value}",
            term_id=term.id,
            target_item_key=term.analysis_item_key,
            target=term.topic,
            facet=term.facet,
            evidence_message_ids=term.evidence_message_ids,
            prompt=question,
        ),
        False,
    )


def _is_neutral_question(question: str) -> bool:
    normalized = " ".join(question.split())
    if len(normalized) < 5 or not normalized.endswith("?"):
        return False
    disallowed_phrases = {
        "admit",
        "at fault",
        "lying",
        "obviously",
        "who is right",
        "why did you",
        "you are wrong",
    }
    lowered = normalized.casefold()
    return not any(phrase in lowered for phrase in disallowed_phrases)


def resolve_legacy_clarification_owner(
    terms: Sequence[ModelAgreementTerm],
    *,
    target_item_key: str | None = None,
    target: str | None = None,
    facet: str | None = None,
    evidence_message_ids: Sequence[str] = (),
) -> int | None:
    unresolved = [
        (index, term)
        for index, term in enumerate(terms)
        if term.state in {MeaningState.CONFLICTING, MeaningState.STATED_BY_ONE}
    ]

    if target_item_key:
        exact_key = [
            index for index, term in unresolved if term.item_key == target_item_key
        ]
        if len(exact_key) == 1:
            return exact_key[0]
        if len(exact_key) > 1:
            return None

    if target and facet:
        exact_pair = [
            index
            for index, term in unresolved
            if term.topic == target and term.facet == facet
        ]
        if len(exact_pair) == 1:
            return exact_pair[0]
        if len(exact_pair) > 1:
            return None

    evidence = set(evidence_message_ids)
    if evidence:
        evidence_matches = [
            index
            for index, term in unresolved
            if evidence.intersection(term.evidence_message_ids)
        ]
        if len(evidence_matches) == 1:
            return evidence_matches[0]
        if len(evidence_matches) > 1:
            return None

    if len(unresolved) == 1:
        return unresolved[0][0]
    return None


def normalize_legacy_model_output(
    payload: Mapping[str, Any],
) -> tuple[AgreementAnalysisModelOutput, bool]:
    data = dict(payload)
    raw_terms = [dict(term) for term in data.pop("terms", [])]
    primary = data.pop("primary_clarification", None)
    markers: list[tuple[int, str]] = []
    for index, term in enumerate(raw_terms):
        marker = term.pop("clarification_target", None)
        if marker is not None:
            markers.append((index, marker))

    output = AgreementAnalysisModelOutput.model_validate({**data, "terms": raw_terms})
    if primary is None and not markers:
        return output, False
    if not isinstance(primary, Mapping):
        return output, True

    owner_index = resolve_legacy_clarification_owner(
        output.terms,
        target_item_key=primary.get("target_item_key"),
        target=primary.get("target"),
        facet=primary.get("facet"),
        evidence_message_ids=primary.get("evidence_message_ids", ()),
    )
    marker_mismatch = any(
        index >= len(output.terms) or marker != output.terms[index].item_key
        for index, marker in markers
    )
    marker_owners = [index for index, _ in markers]
    if (
        owner_index is None
        or marker_mismatch
        or len(marker_owners) > 1
        or (marker_owners and marker_owners != [owner_index])
    ):
        return output, True

    question = primary.get("question")
    if not isinstance(question, str):
        return output, True
    terms = list(output.terms)
    terms[owner_index] = terms[owner_index].model_copy(
        update={"clarification_question": question}
    )
    return output.model_copy(update={"terms": terms}), False


def build_analysis_response(
    request: AgreementAnalysisRequest,
    output: AgreementAnalysisModelOutput,
    *,
    prompt_version: str,
    model: str,
    clarification_unavailable: bool = False,
) -> AgreementAnalysisResponse:
    participant_by_id = {
        participant.id: participant for participant in request.participants
    }
    message_by_id = {message.message_id: message for message in request.messages}
    seen_item_keys: set[str] = set()
    clarification_candidates: list[tuple[str, str]] = []
    terms: list[AgreementTerm] = []

    for index, model_term in enumerate(output.terms, start=1):
        item_key = f"{model_term.topic.value}.{model_term.facet.value}"
        if model_term.facet not in TOPIC_FACETS[model_term.topic]:
            raise invalid_output(
                "The analysis returned a facet that does not match its topic."
            )
        if model_term.item_key != item_key:
            raise invalid_output(
                "The analysis item key does not match its topic and facet."
            )
        if item_key in seen_item_keys:
            raise invalid_output(
                "The analysis returned the same atomic agreement item more than once."
            )
        seen_item_keys.add(item_key)

        evidence_ids = list(dict.fromkeys(model_term.evidence_message_ids))
        if len(evidence_ids) != len(model_term.evidence_message_ids):
            raise invalid_output("The analysis returned duplicate evidence IDs.")
        try:
            evidence_messages = [message_by_id[item] for item in evidence_ids]
        except KeyError as exc:
            raise invalid_output("The analysis cited an unknown message ID.") from exc

        evidence_by_participant: dict[str, set[str]] = defaultdict(set)
        for message in evidence_messages:
            evidence_by_participant[message.speaker_id].add(message.message_id)

        model_positions = model_term.participant_positions
        position_ids = [position.participant_id for position in model_positions]
        if len(position_ids) != len(set(position_ids)):
            raise invalid_output("The analysis duplicated a participant position.")

        positions: list[ParticipantPosition] = []
        for position in model_positions:
            participant = participant_by_id.get(position.participant_id)
            if participant is None:
                raise invalid_output("The analysis cited an unknown participant.")
            if not set(position.evidence_message_ids).issubset(set(evidence_ids)):
                raise invalid_output(
                    "Position evidence must belong to the term evidence."
                )
            if not set(position.evidence_message_ids).issubset(
                evidence_by_participant[position.participant_id]
            ):
                raise invalid_output(
                    "Position evidence must belong to the claimed participant."
                )
            positions.append(
                ParticipantPosition(
                    participant_id=participant.id,
                    role=participant.role,
                    summary=position.summary,
                    evidence_message_ids=position.evidence_message_ids,
                )
            )

        expected_participants = set(participant_by_id)
        evidence_participants = {
            participant_id
            for participant_id, ids in evidence_by_participant.items()
            if ids
        }
        position_participants = set(position_ids)
        if model_term.state in {MeaningState.ALIGNED, MeaningState.CONFLICTING}:
            if evidence_participants != expected_participants:
                raise invalid_output(
                    "Aligned and conflicting terms require evidence from both "
                    "participants."
                )
            if position_participants != expected_participants:
                raise invalid_output(
                    "Aligned and conflicting terms require both participant positions."
                )
        elif model_term.state == MeaningState.STATED_BY_ONE:
            if (
                len(evidence_participants) != 1
                or position_participants != evidence_participants
            ):
                raise invalid_output(
                    "One-sided terms require one supported participant position."
                )
        elif evidence_ids or model_positions:
            raise invalid_output(
                "Not-discussed terms cannot contain evidence or participant positions."
            )

        statuses = _participant_statuses(
            request, model_term.state, evidence_participants
        )
        evidence = [
            EvidenceReference(
                source="transcript",
                reference_id=message.message_id,
                participant_id=message.speaker_id,
                role=participant_by_id[message.speaker_id].role,
                speaker_name=ROLE_NAMES[participant_by_id[message.speaker_id].role],
                message_id=message.message_id,
                original_text=message.original_text,
                original_language=message.original_language,
                order=message.order,
                timestamp=message.timestamp,
                input_source=message.input_source,
                raw_transcript=message.raw_transcript,
                corrected_text=message.corrected_text,
                transcription_model=message.transcription_model,
                consent_id=message.consent_id,
            )
            for message in evidence_messages
        ]
        term_id = f"{model_term.topic.value}-{model_term.facet.value}-{index}"
        if model_term.clarification_question is not None:
            clarification_candidates.append(
                (term_id, model_term.clarification_question)
            )
        terms.append(
            AgreementTerm(
                id=term_id,
                analysis_item_key=item_key,
                topic=model_term.topic,
                facet=model_term.facet,
                label=ITEM_LABELS[(model_term.topic, model_term.facet)],
                summary=model_term.neutral_summary,
                state=model_term.state,
                participant_positions=positions,
                participant_confirmations=statuses,
                evidence_message_ids=evidence_ids,
                evidence=evidence,
                clarification_target=None,
            )
        )

    clarification, warning_required = _build_clarification(
        terms,
        clarification_candidates,
        clarification_unavailable=clarification_unavailable,
    )
    warnings = (
        [
            AnalysisWarning(
                code=AnalysisWarningCode.CLARIFICATION_UNAVAILABLE,
                message=CLARIFICATION_WARNING,
            )
        ]
        if warning_required
        else []
    )

    return AgreementAnalysisResponse(
        session_id=request.session_id,
        mode=request.mode,
        prompt_version=prompt_version,
        model=model,
        status=(AnalysisStatus.PARTIAL if warnings else AnalysisStatus.COMPLETE),
        warnings=warnings,
        terms=terms,
        primary_clarification=clarification,
    )


def _participant_statuses(
    request: AgreementAnalysisRequest,
    state: MeaningState,
    evidence_participants: set[str],
) -> dict[PartyRole, ParticipantTermStatus]:
    if state == MeaningState.ALIGNED:
        return {role: ParticipantTermStatus.CONFIRMED for role in PartyRole}
    if state == MeaningState.CONFLICTING:
        return {role: ParticipantTermStatus.CONFLICTING for role in PartyRole}
    if state == MeaningState.NOT_DISCUSSED:
        return {role: ParticipantTermStatus.NOT_STATED for role in PartyRole}

    stated_id = next(iter(evidence_participants))
    stated_role = next(
        participant.role
        for participant in request.participants
        if participant.id == stated_id
    )
    return {
        role: (
            ParticipantTermStatus.STATED
            if role == stated_role
            else ParticipantTermStatus.NOT_STATED
        )
        for role in PartyRole
    }
