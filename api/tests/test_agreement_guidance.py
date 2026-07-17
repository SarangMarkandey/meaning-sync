from __future__ import annotations

from datetime import UTC, datetime

from app.domain.agreement_guidance import (
    addressed_participants,
    agreement_semantic_fingerprint,
    clarification_fingerprint,
    optional_item_keys,
    ordered_clarification_candidates,
    required_issue_keys,
    semantic_target,
)
from app.schemas.analysis import (
    AgreementFacet,
    AgreementTerm,
    AgreementTopic,
    EvidenceReference,
    MeaningState,
    ParticipantPosition,
    ParticipantTermStatus,
    PartyRole,
)


def term(
    item_key: str,
    topic: AgreementTopic,
    facet: AgreementFacet,
    state: MeaningState,
    summaries: dict[PartyRole, str] | None = None,
) -> AgreementTerm:
    summaries = summaries or {}
    evidence = [
        EvidenceReference(
            source="transcript",
            reference_id=f"message-{role.value}-{item_key}",
            participant_id=role.value,
            role=role,
            speaker_name=role.value,
            message_id=f"message-{role.value}-{item_key}",
            original_text=summary,
            original_language="en",
            order=index,
            timestamp=datetime(2026, 7, 17, 9, tzinfo=UTC),
        )
        for index, (role, summary) in enumerate(summaries.items(), start=1)
    ]
    positions = [
        ParticipantPosition(
            participant_id=role.value,
            role=role,
            summary=summary,
            evidence_message_ids=[f"message-{role.value}-{item_key}"],
        )
        for role, summary in summaries.items()
    ]
    if state == MeaningState.ALIGNED:
        statuses = {role: ParticipantTermStatus.CONFIRMED for role in PartyRole}
    elif state == MeaningState.CONFLICTING:
        statuses = {role: ParticipantTermStatus.CONFLICTING for role in PartyRole}
    elif state == MeaningState.NOT_DISCUSSED:
        statuses = {role: ParticipantTermStatus.NOT_STATED for role in PartyRole}
    else:
        stated = next(iter(summaries))
        statuses = {
            role: (
                ParticipantTermStatus.STATED
                if role == stated
                else ParticipantTermStatus.NOT_STATED
            )
            for role in PartyRole
        }
    return AgreementTerm(
        id=item_key.replace(".", "-"),
        analysis_item_key=item_key,
        topic=topic,
        facet=facet,
        label=item_key,
        summary=" / ".join(summaries.values()) or "Not discussed.",
        state=state,
        participant_positions=positions,
        participant_confirmations=statuses,
        evidence_message_ids=[item.message_id for item in evidence if item.message_id],
        evidence=evidence,
    )


def test_application_policy_classifies_and_orders_issues() -> None:
    scope = term(
        "scope.work",
        AgreementTopic.SCOPE,
        AgreementFacet.WORK,
        MeaningState.STATED_BY_ONE,
        {PartyRole.HIRER: "Repair the fan."},
    )
    price = term(
        "price.amount",
        AgreementTopic.PRICE,
        AgreementFacet.AMOUNT,
        MeaningState.CONFLICTING,
        {PartyRole.HIRER: "₹1,200.", PartyRole.WORKER: "₹1,500."},
    )
    materials = term(
        "materials.inclusion",
        AgreementTopic.MATERIALS,
        AgreementFacet.INCLUSION,
        MeaningState.CONFLICTING,
        {
            PartyRole.HIRER: "Parts are included.",
            PartyRole.WORKER: "Parts are separate.",
        },
    )
    warranty = term(
        "warranty.coverage",
        AgreementTopic.WARRANTY,
        AgreementFacet.COVERAGE,
        MeaningState.NOT_DISCUSSED,
    )

    terms = [warranty, materials, price, scope]

    assert required_issue_keys(terms) == [
        "scope.work",
        "price.amount",
        "materials.inclusion",
    ]
    assert optional_item_keys(terms) == ["warranty.coverage"]
    assert [
        item.analysis_item_key for item in ordered_clarification_candidates(terms)
    ] == [
        "scope.work",
        "price.amount",
        "materials.inclusion",
    ]
    assert addressed_participants(scope) == [PartyRole.WORKER]
    assert addressed_participants(materials) == list(PartyRole)


def test_price_coverage_and_materials_share_one_semantic_target() -> None:
    price_coverage = term(
        "price.amount",
        AgreementTopic.PRICE,
        AgreementFacet.AMOUNT,
        MeaningState.CONFLICTING,
        {
            PartyRole.HIRER: "₹1,200 includes replacement parts.",
            PartyRole.WORKER: "₹1,200 labour; parts are separate.",
        },
    )
    materials = term(
        "materials.inclusion",
        AgreementTopic.MATERIALS,
        AgreementFacet.INCLUSION,
        MeaningState.CONFLICTING,
        {
            PartyRole.HIRER: "Replacement parts are included.",
            PartyRole.WORKER: "Replacement parts are separate.",
        },
    )

    assert semantic_target(price_coverage) == "materials.inclusion"
    assert clarification_fingerprint(price_coverage, [price_coverage, materials]) == (
        clarification_fingerprint(materials, [price_coverage, materials])
    )
    assert ordered_clarification_candidates([price_coverage, materials]) == [materials]


def test_semantic_fingerprint_normalizes_position_order_and_whitespace() -> None:
    original = term(
        "materials.inclusion",
        AgreementTopic.MATERIALS,
        AgreementFacet.INCLUSION,
        MeaningState.CONFLICTING,
        {
            PartyRole.HIRER: "Parts   are INCLUDED.",
            PartyRole.WORKER: "Parts are separate.",
        },
    )
    normalized = original.model_copy(
        deep=True,
        update={
            "participant_positions": [
                original.participant_positions[1].model_copy(
                    update={"summary": " parts are separate "}
                ),
                original.participant_positions[0].model_copy(
                    update={"summary": "parts are included"}
                ),
            ]
        },
    )

    assert agreement_semantic_fingerprint([original]) == (
        agreement_semantic_fingerprint([normalized])
    )
    assert agreement_semantic_fingerprint([original], ["warranty.coverage"]) != (
        agreement_semantic_fingerprint([original])
    )
