# API Contract

All implemented endpoints are JSON under `/api/v1`. `GET /health` returns service status.

## Live Agreement Analysis

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

A valid map with an unusable clarification returns HTTP 200, `status: "partial"`, no `primary_clarification`, and warning code `clarification_unavailable`. The UI preserves the map and displays: “The agreement map is ready, but a clarification question could not be generated. Review the highlighted conflict.”

HTTP 502 is reserved for invalid core model output or evidence. Errors use a controlled shape: `{"detail":{"code":"invalid_model_output","message":"…","retryable":true}}`. Other codes cover invalid requests/configuration/API keys, rate limits, timeout, connection failure, refusal, and provider failure. Provider details are not returned.

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

Implemented: the live endpoint and deterministic routes. Partially implemented: `hi` exists in shared language models but live requests reject it. Planned: audio, translation, authentication, persistence, device joining, and live clarity-receipt endpoints. MeaningSync does not provide legal advice.
