# API Contract

## Live Access Contract

P1B adds opaque bearer credentials without changing the Demo contract. A credential authorizes one role in one session; creator-controlled lifecycle actions use the session’s `creator_role`, which may be Customer (`hirer`) or Service provider (`worker`). The opposite role receives the high-entropy, expiring, single-use invitation.

The first private selection remains absent from participant-scoped JSON until all addressed people answer. Polling clients compare the numeric `revision` or `ETag` and retain their current view when it is unchanged.

All implemented endpoints are JSON under `/api/v1`. `GET /health` returns service status.

## Standalone Agreement Analysis

`POST /api/v1/agreements/analyze` accepts Live Mode, exactly one hirer and one worker, and 2–40 ordered English messages:

```json
{
  "session_id": "live-r1",
  "mode": "live",
  "participants": [
    {"id":"hirer","role":"hirer","language":"en"},
    {"id":"worker","role":"worker","language":"en"}
  ],
  "messages": [
    {"message_id":"message-1","speaker_id":"hirer","original_text":"Start today.","original_language":"en","order":1,"timestamp":"2026-07-16T09:00:00Z"},
    {"message_id":"message-2","speaker_id":"worker","original_text":"I can start today.","original_language":"en","order":2,"timestamp":"2026-07-16T09:01:00Z"}
  ]
}
```

The response includes `prompt_version`, configured `model`, `status` (`complete` or `partial`), `warnings`, agreement terms, and zero or one `primary_clarification`. Each term has canonical `analysis_item_key`, `topic`, and `facet` fields; neutral `summary`; underlying `state` (`aligned`, `conflicting`, `stated_by_one`, or `not_discussed`); participant positions/statuses; evidence message IDs; backend-hydrated original evidence; and an optional exact item-key clarification target. The backend derives a clarification's target item key, topic, facet, and evidence IDs from its owning term.

Atomic keys prevent adjacent meanings from being merged. For example, agreement on `price.amount` remains aligned when the parties conflict on `materials.inclusion`.

A valid map with an unusable clarification returns HTTP 200, `status: "partial"`, no `primary_clarification`, and warning code `clarification_unavailable`. Invalid core output remains a controlled upstream-analysis error.

HTTP 502 is reserved for invalid core model output or evidence. Errors use a controlled shape: `{"detail":{"code":"invalid_model_output","message":"…","retryable":true}}`. Other codes cover invalid requests/configuration/API keys, rate limits, timeout, connection failure, refusal, and provider failure. Provider details are not returned.

## Server-Owned Live Sessions

The complete product flow uses `/api/v1/live/sessions`, not browser-owned state. Its repository-backed state survives backend restart until configured expiry. It supports preferences and creator role, shared/separate participation, role-scoped messages/readiness, explicit creator analysis, immutable agreement versions, private choices, Conversation re-entry, separate version-bound confirmations, and receipt issue/retrieval. The complete route and body reference is in [Live Session API](api.md).

Every `LiveSessionView` includes lifecycle state, creator/viewer roles, currency, readiness, active participant/question/item, agreement data, confirmations, audio consent/duration/configuration, and compatibility guidance. One frontend mapping presents exactly Preferences, Participation, Conversation, Check understanding, Confirm, and Receipt. `analyzing` is loading at the start of Check understanding; clarification is an interaction inside that step.

Every applicable write includes `expected_agreement_version_id`; a stale write returns HTTP 409 and the current ID. Mutation bodies also carry `request_id` for idempotent retries, and their payload digests remain effective after restart. Each database mutation also uses an internal optimistic repository revision; a concurrent update returns `concurrent_update` without partial state. `POST /{session_id}/questions/{question_id}/selections` accepts the acting `participant_id`, backend-owned `option_id`, optional `other_text`, request ID, and expected version. The backend validates the session, participant, question, item, version, and option together. A pending selection is persisted but not returned to the browser until every addressed participant has answered; for a two-person question, the first remains hidden before the second submits. A successful meaning change creates a child snapshot rather than replacing v1. Any newer agreement version invalidates old confirmations.

Agreement snapshots expose internal `version_number`, user-facing `meaningful_version_number`, `semantic_fingerprint`, and `has_meaningful_change`. Internal order advances for each successful validated analysis. The meaningful number advances only when normalized agreement meaning changes, so operational retries do not create a misleading map version. Question records bind a stable item ID and normalized semantic commitment so wording changes do not create a duplicate question.

Guidance classifies conflicting and critical one-sided items as required; they must be answered or explicitly left unresolved. Optional not-discussed items are returned separately and may be submitted together through the existing multi-message statement operation. A unilateral not-applicable proposal remains visible and does not count as shared meaning.

`UnderstandingQuestion` retains compatibility kinds while the current product opens choices only for conflict/one-sided decision items. Options use stable server-owned meanings. Compatible answers may create a child version; different answers remain unresolved and suppress immediate repetition. `other` requires 2–280 characters and `unsure` cannot align. There is no mandatory teach-back or minimum question count. Receipt readiness requires two confirmations of the same current version. These records show stated selections, not proven comprehension or consent.

## Audio Conversation Contract

Live Conversation accepts typed messages and reviewed audio transcripts in the same ordered `AnalysisMessage` collection. `/audio-consent` persists participant-specific, versioned consent. `/transcription-session` proxies only an SDP offer/answer for transcription-only WebRTC after credential, role, stage, readiness, revision, expiry, and consent checks. `/audio-transcripts` persists the raw finalized transcript, optional correction, effective analysis text, role/language/times/model/source, consent reference, and request ID. It never accepts raw audio. Demo exposes none of these controls.

## Deterministic Demo Sessions

`POST /api/v1/demo/sessions` accepts optional independent languages, currently `en`/`en`. Follow-up routes use the returned session ID:

- `GET /{session_id}`
- `POST /{session_id}/consent`
- `POST /{session_id}/analysis`
- `POST /{session_id}/clarifications`
- `POST /{session_id}/clarifications/{question_id}/answers`
- `POST /{session_id}/confirmations`
- `POST /{session_id}/receipt`

All paths above are relative to `/api/v1/demo/sessions`. First clarification answers remain hidden until both parties answer. The receipt preserves unresolved and not-discussed terms.

## Status

Implemented: standalone analysis, server-owned durable Live workflow, deterministic Demo routes, restart-recoverable Live receipts, expiry, optimistic concurrency, shared/separate devices, and consent-gated Live WebRTC transcription with reviewed evidence provenance. `hi` exists in shared language models but Live requests reject it. Credentials authorize possession, not identity. Translation remains later work. MeaningSync does not provide legal advice, and its clarity receipt is not a legal contract.
