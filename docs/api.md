# Live Session API

All operations are JSON under `/api/v1/live/sessions`. FastAPI owns lifecycle state, the active participant, version order, and receipt readiness. `GET /health` remains the service health check. `POST /api/v1/agreements/analyze` remains the standalone analysis contract, but the product workflow uses session endpoints.

## Session and Analysis

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/live/sessions` | Create an English Live session from exactly one `hirer`, one `worker`, and 2–40 ordered messages. |
| `GET` | `/api/v1/live/sessions/{session_id}` | Reload the authoritative session view. Returns `session_not_found` after in-memory loss. |
| `POST` | `/api/v1/live/sessions/{session_id}/analysis` | Analyze the draft and create Agreement Map v1. Body: `expected_agreement_version_id` (initially `null`). |
| `GET` | `/api/v1/live/sessions/{session_id}/agreement-versions` | List immutable snapshots in version order. |
| `GET` | `/api/v1/live/sessions/{session_id}/agreement-versions/{version_id}` | Retrieve one immutable snapshot for comparison. |

An `AgreementVersion` contains its ID and increasing internal number, user-facing `meaningful_version_number`, `has_meaningful_change`, deterministic `semantic_fingerprint`, parent and session IDs, creation time, source message IDs, full `terms`, unresolved item keys, not-applicable proposals, prompt/model/schema metadata, analysis status/warnings, exact primary clarification, and per-item changes. Internal order records every validated analysis; the meaningful number changes only when normalized agreement meaning changes.

Every session response also contains `guidance`:

- `user_stage`: `conversation`, `clarify`, `review`, `confirm`, or `receipt`;
- plain-language `headline`, `explanation`, and primary/secondary labels;
- typed actions rather than client-inferred navigation;
- `acting_participant`, active clarification ID, and exact target item key;
- required/optional item keys and their counts.

The server orders required issues by scope, amount and price coverage, materials, timing, payment, then other critical responsibility. Setup is not a user stage, and `analyzing` is a transient lifecycle status rather than a clickable progress destination.

## Clarification and Review

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/clarifications/{clarification_id}/answers` | `expected_agreement_version_id`, acting `participant_id`, `answer`, `request_id` |
| `POST` | `/{session_id}/clarifications/{clarification_id}/leave-unresolved` | expected version and `request_id`; explicitly retain the exact issue as unresolved |
| `POST` | `/{session_id}/statements` | expected version, new chronological `messages`, `request_id` |
| `POST` | `/{session_id}/not-applicable` | expected version, participant, exact `item_key`, `request_id` |
| `POST` | `/{session_id}/optional-details/reviewed` | expected version and `request_id`; finish the optional batch without changing missing terms |
| `POST` | `/{session_id}/review` | expected version, complete `acknowledged_unresolved_item_keys`, `request_id` |

Paths in this and later tables are relative to `/api/v1/live/sessions`. The first clarification answer is recorded internally but its text/message ID is not returned. After the second answer, both are appended as immutable speaker messages and one deliberate re-analysis creates the next internal version. A clarification record carries a deterministic fingerprint and semantic target; an equivalent active question is reused rather than duplicated. A unilateral not-applicable proposal remains visible and does not change `not_discussed` to `aligned`.

`POST /statements` accepts multiple chronological messages, allowing users to discuss several optional details in one deliberate batch and incur at most one resulting re-analysis. Marking optional details reviewed records workflow progress only; it does not add evidence or convert a missing term to alignment.

## Teach-Back and Confirmation

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/teachbacks` | expected version, active `participant_id`, `text`, `original_language`, unresolved acknowledgments, `request_id` |
| `POST` | `/{session_id}/confirmations` | expected version, participant, own `teachback_id`, `decision`, unresolved acknowledgments, optional exact `change_item_key`, `request_id` |
| `GET` | `/{session_id}/confirmation-status` | Returns each current confirmation and whether a receipt is ready. |

Teach-back submission returns the session view with `matches`, `partially_matches`, `contradicts`, or `insufficient` results. Normal serialization omits original teach-back text. A `confirm` decision requires that participant’s matching teach-back for the current version. `request_change` requires an exact item and returns the session to clarification. Duplicate request IDs and duplicate current confirmations are idempotent.

## Clarity Receipt

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/{session_id}/receipt` | Issue once both participants have matching teach-backs and current confirmations. Body: expected version and `request_id`. |
| `GET` | `/{session_id}/receipt` | Retrieve the immutable in-memory snapshot; returns `receipt_not_ready` before issuance. |

The receipt separates aligned, conflicting/unresolved, one-sided, not-applicable, and not-discussed entries; retains evidence and clarification history; records both teach-backs and confirmation timestamps; and reports `fully_aligned` or `contains_unresolved_items`.

## Errors and Concurrency

Workflow failures use:

```json
{
  "detail": {
    "code": "stale_agreement_version",
    "message": "The agreement changed. Refresh before continuing.",
    "retryable": false,
    "current_agreement_version_id": "agreement-..."
  }
}
```

HTTP 404 covers missing sessions, versions, or clarification records; 409 covers invalid state, stale versions, wrong active participant, confirmation/version mismatch, and receipt readiness; 422 covers invalid actor/item/acknowledgment data. Named workflow codes include `invalid_state`, `session_not_found`, `stale_agreement_version`, `clarification_target_missing`, `clarification_limit_reached`, `participant_mismatch`, `teachback_incomplete`, `teachback_mismatch`, `confirmation_missing`, `confirmation_version_mismatch`, and `receipt_not_ready`. Provider errors retain the existing safe 429/502/503/504 contract without raw provider details.

## Client Usability Contract

The default client renders one primary action from `guidance`. Its first useful click must either invoke that action, reveal the exact evidence or issue needed to decide, or navigate safely back to the current summary. Loading disables repeat mutation, and a 404 session response leads to the explicit in-memory-session recovery screen. Technical item keys, internal snapshot numbers, and fingerprints are diagnostic/provenance details and are progressively disclosed rather than used as the main instructions.
