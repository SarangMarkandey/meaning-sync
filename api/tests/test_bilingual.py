from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.repositories import InMemoryLiveSessionRepository
from app.schemas.analysis import (
    AgreementAnalysisModelOutput,
    AgreementAnalysisRequest,
    AgreementFacet,
    AgreementTopic,
    AnalysisMessage,
    AnalysisParticipant,
    LanguageCode,
    MeaningState,
    ModelAgreementTerm,
    ModelAgreementTermLocalization,
    ModelLocalizedParticipantPosition,
    ModelParticipantPosition,
    PartyRole,
    SemanticEquivalenceStatus,
    SessionMode,
    TranslationStatus,
)
from app.schemas.workflow import (
    DraftStatementSubmission,
    LiveParticipationMode,
    LiveSessionCreate,
    ParticipantProfileSubmission,
)
from app.services.analyzers import DeterministicAgreementAnalyzer
from app.services.analyzers.base import AnalysisFailure
from app.services.analyzers.validation import build_analysis_response
from app.services.live_sessions import LiveSessionService
from app.services.translation import (
    DeterministicTranslationService,
    TranslationOutput,
    _validated_output,
)


def submission(
    *,
    hirer_language: LanguageCode = LanguageCode.HINDI,
    worker_language: LanguageCode = LanguageCode.ENGLISH,
) -> LiveSessionCreate:
    return LiveSessionCreate(
        participants=[
            AnalysisParticipant(
                id="hirer",
                role=PartyRole.HIRER,
                language=hirer_language,
                display_name="  सारंग  ",
            ),
            AnalysisParticipant(
                id="worker",
                role=PartyRole.WORKER,
                language=worker_language,
            ),
        ],
        participation_mode=LiveParticipationMode.SAME_DEVICE,
        creator_role=PartyRole.HIRER,
    )


def service(translator=None) -> LiveSessionService:
    return LiveSessionService(
        analyzer=DeterministicAgreementAnalyzer(),
        repository=InMemoryLiveSessionRepository(),
        translation_service=translator or DeterministicTranslationService(),
    )


@pytest.mark.anyio
async def test_mixed_message_saves_original_then_persists_translation() -> None:
    workflow = service()
    created = workflow.create(submission())
    workflow.add_draft_statement(
        created.id,
        PartyRole.HIRER,
        DraftStatementSubmission(
            original_text=(
                "मैं पंखे और दो स्विच की मरम्मत के लिए ₹1,200 दूँगा, जिसमें बदलने वाले पुर्जे शामिल हैं।"
            ),
            request_id="request-hindi-message",
        ),
    )

    pending = workflow.get(created.id).messages[0]
    assert pending.original_language == LanguageCode.HINDI
    assert (
        pending.translations[LanguageCode.ENGLISH].status == TranslationStatus.PENDING
    )

    translated = await workflow.translate_latest_message(created.id, PartyRole.HIRER)
    message = translated.messages[0]
    assert message.original_text.startswith("मैं पंखे")
    assert message.translations[LanguageCode.ENGLISH].status == TranslationStatus.READY
    assert "₹1,200" in (
        message.translations[LanguageCode.ENGLISH].translated_text or ""
    )


@pytest.mark.anyio
async def test_translation_failure_never_loses_original_and_can_retry() -> None:
    class FailingTranslator:
        model = "fixture"
        prompt_version = "fixture-v1"

        def __init__(self) -> None:
            self.calls = 0

        async def translate_message(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("provider unavailable")
            return TranslationOutput(
                source_language=LanguageCode.HINDI,
                target_language=LanguageCode.ENGLISH,
                translated_text="The work can start today.",
                semantic_equivalence_status=SemanticEquivalenceStatus.EQUIVALENT,
                model=self.model,
                prompt_version=self.prompt_version,
            )

    translator = FailingTranslator()
    workflow = service(translator)
    created = workflow.create(submission())
    original = "काम आज शुरू हो सकता है।"
    workflow.add_draft_statement(
        created.id,
        PartyRole.HIRER,
        DraftStatementSubmission(
            original_text=original,
            request_id="request-failed-translation",
        ),
    )
    result = await workflow.translate_latest_message(created.id, PartyRole.HIRER)
    assert result.messages[0].original_text == original
    translation = result.messages[0].translations[LanguageCode.ENGLISH]
    assert translation.status == TranslationStatus.FAILED
    assert translation.translated_text is None
    retried = await workflow.translate_message(
        created.id, result.messages[0].message_id
    )
    assert (
        retried.messages[0].translations[LanguageCode.ENGLISH].status
        == TranslationStatus.READY
    )
    assert translator.calls == 2


@pytest.mark.parametrize("language", [LanguageCode.ENGLISH, LanguageCode.HINDI])
def test_same_language_session_does_not_create_translation_work(
    language: LanguageCode,
) -> None:
    workflow = service()
    created = workflow.create(
        submission(
            hirer_language=language,
            worker_language=language,
        )
    )
    result = workflow.add_draft_statement(
        created.id,
        PartyRole.HIRER,
        DraftStatementSubmission(
            original_text="The work can start today.",
            request_id="request-english-message",
        ),
    )
    assert result.messages[0].translations == {}


def test_polling_never_invokes_translation() -> None:
    class CountingTranslator:
        model = "fixture"
        prompt_version = "fixture-v1"

        def __init__(self) -> None:
            self.calls = 0

        async def translate_message(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("polling must not translate")

    translator = CountingTranslator()
    workflow = service(translator)
    created = workflow.create(submission())
    workflow.add_draft_statement(
        created.id,
        PartyRole.HIRER,
        DraftStatementSubmission(
            original_text="काम आज शुरू हो सकता है।",
            request_id="request-pending-poll",
        ),
    )
    workflow.get(created.id)
    workflow.get(created.id)
    assert translator.calls == 0


def test_validation_rejects_lost_inclusion_meaning() -> None:
    with pytest.raises(ValueError, match="critical agreement meaning"):
        _validated_output(
            "Replacement parts are included in ₹1,200.",
            TranslationOutput(
                source_language=LanguageCode.ENGLISH,
                target_language=LanguageCode.HINDI,
                translated_text="बदलने वाले पुर्जों की कीमत ₹1,200 है।",
                semantic_equivalence_status=SemanticEquivalenceStatus.EQUIVALENT,
                model="fixture",
                prompt_version="fixture-v1",
            ),
        )


@pytest.mark.anyio
async def test_deterministic_translation_preserves_inclusion_both_directions() -> None:
    translator = DeterministicTranslationService()
    hindi_to_english = await translator.translate_message(
        ("मैं पंखे और दो स्विच की मरम्मत के लिए ₹1,200 दूँगा, जिसमें बदलने वाले पुर्जे शामिल हैं।"),
        LanguageCode.HINDI,
        LanguageCode.ENGLISH,
    )
    english_to_hindi = await translator.translate_message(
        "₹1,200 covers my labour. Replacement parts are separate.",
        LanguageCode.ENGLISH,
        LanguageCode.HINDI,
    )
    assert "including replacement parts" in hindi_to_english.translated_text
    assert "अलग" in english_to_hindi.translated_text
    assert hindi_to_english.preserved_amounts == ["₹", "1,200"]


def test_display_names_are_optional_trimmed_unicode_and_role_scoped() -> None:
    workflow = service()
    created = workflow.create(submission())
    assert created.participants[0].display_name == "सारंग"
    updated = workflow.update_participant_profile(
        created.id,
        PartyRole.WORKER,
        ParticipantProfileSubmission(
            display_name="  Meera  ", request_id="request-worker-profile"
        ),
    )
    assert updated.participants[1].display_name == "Meera"
    with pytest.raises(ValidationError):
        AnalysisParticipant(
            id="worker",
            role=PartyRole.WORKER,
            language=LanguageCode.ENGLISH,
            display_name="x" * 81,
        )


@pytest.mark.anyio
async def test_bilingual_demo_terms_have_two_localizations() -> None:
    request = AgreementAnalysisRequest(
        session_id="demo-bilingual",
        mode=SessionMode.DEMO,
        participants=submission().participants,
        messages=[
            AnalysisMessage(
                message_id="message-1",
                speaker_id="hirer",
                original_text="काम और कीमत ₹1,200 है।",
                original_language=LanguageCode.HINDI,
                order=1,
                timestamp=datetime.now(UTC),
            ),
            AnalysisMessage(
                message_id="message-2",
                speaker_id="worker",
                original_text="₹1,200 is labour and parts are separate.",
                original_language=LanguageCode.ENGLISH,
                order=2,
                timestamp=datetime.now(UTC),
            ),
            AnalysisMessage(
                message_id="message-3",
                speaker_id="hirer",
                original_text="काम आज शुरू होगा।",
                original_language=LanguageCode.HINDI,
                order=3,
                timestamp=datetime.now(UTC),
            ),
            AnalysisMessage(
                message_id="message-4",
                speaker_id="worker",
                original_text="I can start today.",
                original_language=LanguageCode.ENGLISH,
                order=4,
                timestamp=datetime.now(UTC),
            ),
        ],
    )
    response = await DeterministicAgreementAnalyzer().analyze(request)
    assert all(
        set(term.localizations) == {LanguageCode.ENGLISH, LanguageCode.HINDI}
        for term in response.terms
    )
    materials = next(
        term
        for term in response.terms
        if term.analysis_item_key == "materials.inclusion"
    )
    assert "पुर्जे" in materials.localizations[LanguageCode.HINDI].summary


def test_live_hindi_localization_uses_structured_meaning_not_demo_values() -> None:
    timestamp = datetime.now(UTC)
    request = AgreementAnalysisRequest(
        session_id="live-hindi",
        mode=SessionMode.LIVE,
        participants=[
            AnalysisParticipant(
                id="hirer", role=PartyRole.HIRER, language=LanguageCode.HINDI
            ),
            AnalysisParticipant(
                id="worker", role=PartyRole.WORKER, language=LanguageCode.HINDI
            ),
        ],
        messages=[
            AnalysisMessage(
                message_id="message-1",
                speaker_id="hirer",
                original_text="कीमत ₹9,500 है।",
                original_language=LanguageCode.HINDI,
                order=1,
                timestamp=timestamp,
            ),
            AnalysisMessage(
                message_id="message-2",
                speaker_id="worker",
                original_text="हाँ, कीमत ₹9,500 है।",
                original_language=LanguageCode.HINDI,
                order=2,
                timestamp=timestamp,
            ),
        ],
    )
    positions = [
        ModelParticipantPosition(
            participant_id=role.value,
            summary="The agreed price is ₹9,500.",
            evidence_message_ids=[f"message-{index}"],
        )
        for index, role in enumerate(PartyRole, start=1)
    ]
    localized_positions = [
        ModelLocalizedParticipantPosition(
            participant_id=role.value,
            summary="तय कीमत ₹9,500 है।",
        )
        for role in PartyRole
    ]
    term = ModelAgreementTerm(
        item_key="price.amount",
        topic=AgreementTopic.PRICE,
        facet=AgreementFacet.AMOUNT,
        neutral_summary="Both participants agree the price is ₹9,500.",
        state=MeaningState.ALIGNED,
        participant_positions=positions,
        evidence_message_ids=["message-1", "message-2"],
        localizations=[
            ModelAgreementTermLocalization(
                language=LanguageCode.HINDI,
                summary="दोनों प्रतिभागी ₹9,500 की कीमत पर सहमत हैं।",
                participant_positions=localized_positions,
            )
        ],
    )
    response = build_analysis_response(
        request,
        AgreementAnalysisModelOutput(terms=[term]),
        prompt_version="fixture-v1",
        model="fixture",
    )
    assert "₹9,500" in response.terms[0].localizations[LanguageCode.HINDI].summary
    assert "₹1,200" not in response.terms[0].localizations[LanguageCode.HINDI].summary

    with pytest.raises(AnalysisFailure, match="required Hindi localization"):
        build_analysis_response(
            request,
            AgreementAnalysisModelOutput(
                terms=[term.model_copy(update={"localizations": []})]
            ),
            prompt_version="fixture-v1",
            model="fixture",
        )
