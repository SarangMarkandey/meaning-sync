# API Contract

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

The complete product flow uses `/api/v1/live/sessions`, not browser-owned state. It supports session creation/reload, initial analysis, immutable agreement-version listing/retrieval, separately submitted clarification answers, additional statements, not-applicable proposals, review start, actor-bound teach-backs, separate version-bound confirmations, confirmation status, and clarity-receipt issue/retrieval. The complete route and body reference is in [Live Session API](api.md).

Every `LiveSessionView` includes a `guidance` object. It gives the browser the five-stage `user_stage`, plain-language headline/explanation, primary and optional secondary action/label, required and optional counts/item keys, acting participant, active clarification ID, and exact target item key. Setup is outside the stage list; the lower-level `analyzing` lifecycle value maps to a transient status within the move from Conversation to Clarify or Review. Clients render guidance instead of deriving the next action from old clarification records or term-array order.

Every applicable write includes `expected_agreement_version_id`; a stale write returns HTTP 409 and the current ID. Mutation bodies also carry `request_id` for idempotent retries. The first clarification response is not revealed until both parties answer. A successful re-analysis creates a child snapshot rather than replacing v1. Any newer agreement version invalidates old confirmations.

Agreement snapshots expose internal `version_number`, user-facing `meaningful_version_number`, `semantic_fingerprint`, and `has_meaningful_change`. Internal order advances for each successful validated analysis. The meaningful number advances only when normalized agreement meaning changes, so operational retries do not create a misleading map version. Clarification records similarly expose `fingerprint` and `semantic_target` for exact-target deduplication.

Guidance classifies conflicting and critical one-sided items as required; they must be answered or explicitly left unresolved. Optional not-discussed items are returned separately and may be submitted together through the existing multi-message statement operation. A unilateral not-applicable proposal remains visible and does not count as shared meaning.

Live teach-back uses the backend OpenAI evaluator and Structured Outputs. It never calls OpenAI from the browser or falls back to a fixture. Both current, matching teach-backs and both current confirmations are required before receipt issuance.

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

Implemented: standalone analysis, server-owned Live workflow, deterministic Demo routes, and Live clarity receipt. Partially implemented: `hi` exists in shared language models but Live requests reject it; session recovery works only while the same FastAPI process retains memory. Planned: audio, translation, authentication, durable persistence, and separate-device joining. MeaningSync does not provide legal advice, and its clarity receipt is not a legal contract.
