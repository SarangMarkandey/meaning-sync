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

The complete product flow uses `/api/v1/live/sessions`, not browser-owned state. Its repository-backed state survives backend restart until configured expiry. It supports session creation/reload, initial analysis, immutable agreement-version listing/retrieval, choice-based clarification, additional statements, not-applicable proposals, server-selected understanding questions, private participant selections, separate version-bound confirmations, confirmation status, and clarity-receipt issue/retrieval. The complete route and body reference is in [Live Session API](api.md).

Every `LiveSessionView` includes a `guidance` object. It gives the browser the five-stage `user_stage` (`conversation`, `clarify`, `check_understanding`, `confirm`, or `receipt`), plain-language headline/explanation, primary and optional secondary action/label, required and optional counts/item keys, acting participant, active question, and exact target item key. Setup is outside the stage list; the lower-level `analyzing` lifecycle value maps to a transient status within the move out of Conversation. Clients render guidance instead of deriving the next action from old clarification records or term-array order.

Every applicable write includes `expected_agreement_version_id`; a stale write returns HTTP 409 and the current ID. Mutation bodies also carry `request_id` for idempotent retries, and their payload digests remain effective after restart. Each database mutation also uses an internal optimistic repository revision; a concurrent update returns `concurrent_update` without partial state. `POST /{session_id}/questions/{question_id}/selections` accepts the acting `participant_id`, backend-owned `option_id`, optional `other_text`, request ID, and expected version. The backend validates the session, participant, question, item, version, and option together. A pending selection is persisted but not returned to the browser until every addressed participant has answered; for a two-person question, the first remains hidden before the second submits. A successful meaning change creates a child snapshot rather than replacing v1. Any newer agreement version invalidates old confirmations.

Agreement snapshots expose internal `version_number`, user-facing `meaningful_version_number`, `semantic_fingerprint`, and `has_meaningful_change`. Internal order advances for each successful validated analysis. The meaningful number advances only when normalized agreement meaning changes, so operational retries do not create a misleading map version. Question records bind a stable item ID and normalized semantic commitment so wording changes do not create a duplicate question.

Guidance classifies conflicting and critical one-sided items as required; they must be answered or explicitly left unresolved. Optional not-discussed items are returned separately and may be submitted together through the existing multi-message statement operation. A unilateral not-applicable proposal remains visible and does not count as shared meaning.

`UnderstandingQuestion` unifies `clarification` and `understanding_check` kinds. Its public `UnderstandingOption` values expose stable IDs and labels with `recorded_position`, `recorded_meaning`, `other`, or `unsure` kinds; semantic values remain server-owned. Check understanding uses deterministic backend construction and outcome rules. A current meaning with completed two-party clarification receives at most one additional high-impact question; without clarification, simple agreements normally receive one or two and broad agreements receive at most three. Completed clarification evidence suppresses the same semantic question. Outcomes are `aligned`, `meaning_changed`, `different`, `unsure`, or `left_unresolved`: matching recorded meaning completes a check; matching alternative meaning enters the immutable version-change flow; different meanings return only the affected item to clarification; `other` requires 2–280 characters of text; and `unsure` cannot create alignment. Receipt readiness requires all applicable current-version checks to be complete or deliberately left unresolved, followed by both current confirmations. Confirmations bind `understanding_review_id`, and receipts expose `understanding_status`. These records show independent selections, not proven comprehension or consent.

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

Implemented: standalone analysis, server-owned durable Live workflow, deterministic Demo routes, restart-recoverable Live receipts, expiry, and optimistic concurrency. Partially implemented: `hi` exists in shared language models but Live requests reject it; the interface remains same-device and database persistence is not authentication. Planned for P1B: role-bound tokens, single-use invite exchange, QR joining, participant-specific authorization, and lightweight synchronization. Audio and translation remain later work. MeaningSync does not provide legal advice, and its clarity receipt is not a legal contract.
