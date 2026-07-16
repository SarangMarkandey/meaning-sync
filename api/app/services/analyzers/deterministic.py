from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AgreementFacet,
    AgreementTopic,
    MeaningState,
    ModelAgreementTerm,
    ModelParticipantPosition,
)
from app.services.analyzers.validation import build_analysis_response

DETERMINISTIC_PROMPT_VERSION = "deterministic-demo-v2"


class DeterministicAgreementAnalyzer:
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse:
        output = AgreementAnalysisModelOutput(
            terms=[
                ModelAgreementTerm(
                    item_key="scope.work",
                    topic=AgreementTopic.SCOPE,
                    facet=AgreementFacet.WORK,
                    neutral_summary=(
                        "Repair one fan and two switches was stated by the homeowner."
                    ),
                    state=MeaningState.STATED_BY_ONE,
                    participant_positions=[
                        ModelParticipantPosition(
                            participant_id="hirer",
                            summary="Repair one fan and two switches.",
                            evidence_message_ids=["message-1"],
                        )
                    ],
                    evidence_message_ids=["message-1"],
                ),
                ModelAgreementTerm(
                    item_key="price.amount",
                    topic=AgreementTopic.PRICE,
                    facet=AgreementFacet.AMOUNT,
                    neutral_summary=(
                        "Both participants state ₹1,200 as the price, while its "
                        "materials coverage is handled separately below."
                    ),
                    state=MeaningState.ALIGNED,
                    participant_positions=[
                        ModelParticipantPosition(
                            participant_id="hirer",
                            summary="The quoted amount is ₹1,200.",
                            evidence_message_ids=["message-1"],
                        ),
                        ModelParticipantPosition(
                            participant_id="worker",
                            summary="The labour amount is ₹1,200.",
                            evidence_message_ids=["message-2"],
                        ),
                    ],
                    evidence_message_ids=["message-1", "message-2"],
                ),
                ModelAgreementTerm(
                    item_key="materials.inclusion",
                    topic=AgreementTopic.MATERIALS,
                    facet=AgreementFacet.INCLUSION,
                    neutral_summary=(
                        "The participants disagree about whether replacement parts "
                        "are included in ₹1,200."
                    ),
                    state=MeaningState.CONFLICTING,
                    participant_positions=[
                        ModelParticipantPosition(
                            participant_id="hirer",
                            summary="Replacement parts are included in ₹1,200.",
                            evidence_message_ids=["message-1"],
                        ),
                        ModelParticipantPosition(
                            participant_id="worker",
                            summary="Replacement parts are charged separately.",
                            evidence_message_ids=["message-2"],
                        ),
                    ],
                    evidence_message_ids=["message-1", "message-2"],
                    clarification_question=(
                        "Does the ₹1,200 price include replacement parts, or are "
                        "replacement parts charged separately?"
                    ),
                ),
                ModelAgreementTerm(
                    item_key="timing.start",
                    topic=AgreementTopic.TIMING,
                    facet=AgreementFacet.START,
                    neutral_summary=(
                        "Both participants agree that work can start today."
                    ),
                    state=MeaningState.ALIGNED,
                    participant_positions=[
                        ModelParticipantPosition(
                            participant_id="hirer",
                            summary="The work can start today.",
                            evidence_message_ids=["message-3"],
                        ),
                        ModelParticipantPosition(
                            participant_id="worker",
                            summary="The electrician can start today.",
                            evidence_message_ids=["message-4"],
                        ),
                    ],
                    evidence_message_ids=["message-3", "message-4"],
                ),
                *[
                    ModelAgreementTerm(
                        item_key=f"{topic.value}.{facet.value}",
                        topic=topic,
                        facet=facet,
                        neutral_summary=summary,
                        state=MeaningState.NOT_DISCUSSED,
                    )
                    for topic, facet, summary in [
                        (
                            AgreementTopic.COMPLETION,
                            AgreementFacet.DEADLINE,
                            "No completion date or time was discussed.",
                        ),
                        (
                            AgreementTopic.PAYMENT,
                            AgreementFacet.TIMING,
                            "No payment timing was discussed.",
                        ),
                        (
                            AgreementTopic.RESPONSIBILITIES,
                            AgreementFacet.ASSIGNMENT,
                            "No additional responsibilities were discussed.",
                        ),
                        (
                            AgreementTopic.WARRANTY,
                            AgreementFacet.COVERAGE,
                            "No warranty was discussed.",
                        ),
                        (
                            AgreementTopic.CANCELLATION,
                            AgreementFacet.POLICY,
                            "No cancellation policy was discussed.",
                        ),
                        (
                            AgreementTopic.ADDITIONAL_WORK,
                            AgreementFacet.POLICY,
                            "No policy for additional work was discussed.",
                        ),
                    ]
                ],
            ],
        )
        response = build_analysis_response(
            request,
            output,
            prompt_version=DETERMINISTIC_PROMPT_VERSION,
            model="deterministic",
        )
        if response.primary_clarification is not None:
            response = response.model_copy(
                update={
                    "primary_clarification": response.primary_clarification.model_copy(
                        update={
                            "options": [
                                "Parts are included",
                                "Parts are charged separately",
                            ]
                        }
                    )
                }
            )
        return response
