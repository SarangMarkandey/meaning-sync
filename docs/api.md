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

- `user_stage`: `conversation`, `clarify`, `check_understanding`, `confirm`, or `receipt`;
- plain-language `headline`, `explanation`, and primary/secondary labels;
- typed actions rather than client-inferred navigation;
- `acting_participant`, active question ID, and exact target item key;
- required/optional item keys and their counts.

The server orders required issues by scope, amount and price coverage, materials, timing, payment, then other critical responsibility. Guidance actions include `submit_selection`, `leave_unresolved`, `review_optional_details`, `start_understanding_check`, `submit_confirmation`, `issue_receipt`, and `view_receipt`. Setup is not a user stage, and `analyzing` is a transient lifecycle status rather than a clickable progress destination.

## Clarification and Check Understanding

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/questions/{question_id}/selections` | `expected_agreement_version_id`, acting `participant_id`, backend-owned `option_id`, optional `other_text`, `request_id` |
| `POST` | `/{session_id}/questions/{question_id}/leave-unresolved` | expected version, acting `participant_id`, and `request_id`; explicitly retain the exact issue as unresolved |
| `POST` | `/{session_id}/statements` | expected version, new chronological `messages`, `request_id` |
| `POST` | `/{session_id}/not-applicable` | expected version, participant, exact `item_key`, `request_id` |
| `POST` | `/{session_id}/optional-details/reviewed` | expected version and `request_id`; finish the optional batch without changing missing terms |
| `POST` | `/{session_id}/understanding-checks` | expected version, complete `acknowledged_unresolved_item_keys`, `request_id`; create zero to three high-impact checks |

Paths in this and later tables are relative to `/api/v1/live/sessions`. `UnderstandingQuestion` is shared by `clarification` and `understanding_check` kinds. It binds the session, immutable version, stable agreement item, semantic commitment, evidence IDs, addressed participants, question number/count, three or four options, status, and eventual outcome. Each public `UnderstandingOption` exposes a stable ID, neutral label, and kind: `recorded_position`, `recorded_meaning`, `other`, or `unsure`. Its semantic value remains backend-owned and is never accepted from the browser.

The former Live clarification-answer, review, and teach-back routes are retired from the product workflow. Question selections and `POST /understanding-checks` own the same server lifecycle rather than creating a parallel browser-managed flow.

The backend validates an option against the exact question, participant, session, item, and agreement version. `other_text` is rejected unless the `other` option is selected and requires 2–280 characters when it is selected. The first pending `ParticipantSelection` is stored internally but is absent from the public question/session response. Only after all addressed participants submit does the question expose the neutral outcome: `aligned`, `meaning_changed`, `different`, `unsure`, or `left_unresolved`.

Questions are deduplicated by stable item ID and semantic commitment. The service also records independent evidence from the conversation, completed clarification, completed understanding checks, and confirmation. A completed clarification item is not asked again; when current meaning includes a completed two-party clarification, the server creates at most one additional material check and may create none. Without clarification, simple agreements normally receive one or two checks and broad agreements receive at most three. Untouched optional missing topics are excluded.

`POST /statements` accepts multiple chronological messages, allowing users to discuss several optional details in one deliberate batch and incur at most one resulting re-analysis. Marking optional details reviewed records workflow progress only; it does not add evidence or convert a missing term to alignment. Matching recorded meaning completes a question; matching alternative meaning enters the immutable version-change flow; different meaning reopens only that item; `unsure` cannot align; and both participants may explicitly leave the item unresolved.

## Confirmation

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/confirmations` | expected version, participant, own `understanding_review_id`, `decision`, unresolved acknowledgments, optional exact `change_item_key`, `request_id` |
| `GET` | `/{session_id}/confirmation-status` | Returns each current confirmation and whether a receipt is ready. |

A `confirm` decision requires that participant’s current-version understanding review, including every applicable selection or a valid server-recorded skip. `request_change` requires an exact item and returns the session to clarification. Duplicate request IDs and duplicate current confirmations are idempotent. A selection and confirmation record what the participant chose; neither proves comprehension, identity, or consent.

## Clarity Receipt

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/{session_id}/receipt` | Issue once applicable understanding checks and both current confirmations are complete. Body: expected version and `request_id`. |
| `GET` | `/{session_id}/receipt` | Retrieve the immutable in-memory snapshot; returns `receipt_not_ready` before issuance. |

The `clarity-receipt-v2` snapshot separates aligned, conflicting/unresolved, one-sided, not-applicable, and not-discussed entries; retains evidence and clarification history; records `understanding_status` and both confirmation timestamps; and reports `fully_aligned` or `contains_unresolved_items`.

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

HTTP 404 covers missing sessions, versions, or questions; 409 covers invalid state, stale versions, the wrong active participant, idempotency conflict, incomplete understanding, confirmation/version mismatch, and receipt readiness; 422 covers invalid item, option, or acknowledgment data. Named workflow codes include `invalid_state`, `session_not_found`, `stale_agreement_version`, `question_not_found`, `invalid_option`, `question_incomplete`, `idempotency_conflict`, `clarification_target_missing`, `clarification_limit_reached`, `participant_mismatch`, `understanding_incomplete`, `confirmation_missing`, `confirmation_version_mismatch`, and `receipt_not_ready`. Provider errors retain the existing safe 429/502/503/504 contract without raw provider details.

## Client Usability Contract

The default client renders one primary action from `guidance`. Its first useful click must either invoke that action, reveal the exact evidence or issue needed to decide, or navigate safely back to the current summary. Loading disables repeat mutation, and a 404 session response leads to the explicit in-memory-session recovery screen. Technical item keys, internal snapshot numbers, and fingerprints are diagnostic/provenance details and are progressively disclosed rather than used as the main instructions.
