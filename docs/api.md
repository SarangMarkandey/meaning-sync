# Live Session API

## P1B Authorization and Joining

Every Live endpoint except creation and invitation exchange requires `Authorization: Bearer <role-access-token>`. Missing or invalid credentials return `401`; a valid credential used for another session or participant role returns `403`; stale agreement writes retain the existing `409` contract.

- `POST /api/v1/live/sessions` accepts `participation_mode`, `creator_role`, `currency`, and independent participant languages. Shared-device creation returns both role credentials; separate-device creation returns the creator credential and one invitation for the opposite role.
- `POST /api/v1/live/invitations/exchange` atomically exchanges the one-time invitation for the invited role credential.
- `POST /api/v1/live/sessions/{id}/invitations/regenerate` replaces a pending invitation.
- `POST /api/v1/live/sessions/{id}/participants/{role}/revoke` lets the creator revoke the opposite role’s access.
- `POST /api/v1/live/sessions/{id}/draft-statements` appends a server-owned message for the bearer role before analysis.
- `POST /api/v1/live/sessions/{id}/readiness` records the bearer role’s readiness; both roles must be ready before comparison.
- `POST /api/v1/live/sessions/{id}/conversation/reentry` returns an item to Conversation and invalidates readiness/review/confirmation state.
- `POST /api/v1/live/sessions/{id}/audio-consent` records accepted, role-bound, notice-versioned consent with `expected_revision` and `request_id`.
- `POST /api/v1/live/sessions/{id}/transcription-session` accepts authorized `application/sdp` and returns only `application/sdp`; it creates no evidence.
- `POST /api/v1/live/sessions/{id}/transcription-session/end` releases the bearer role’s transient concurrency lease after stop, cancel, failure, or navigation.
- `POST /api/v1/live/sessions/{id}/audio-transcripts` appends one reviewed transcript with raw/corrected/effective provenance, consent, model, timing, revision, and request ID.

Session views include `revision`, `participation_mode`, `viewer_role`, and participant presence. `GET` also returns the revision as `ETag`. Secrets never belong in query parameters or ordinary session views.

## Live Audio Transcription

Speak is available only in `conversation_draft`, before that bearer role marks ready. Consent must match the session, role, and configured notice version. FastAPI initializes a transcription-only OpenAI Realtime WebRTC call using `gpt-realtime-whisper` by default and the participant language. The standard backend key is never returned.

Initialization does not hold a SQL transaction or persist SDP, audio, partial deltas, connection state, or credentials. Only `/audio-transcripts` mutates the existing ledger. It preserves immutable machine transcript, optional participant correction, effective analysis text, and provenance; then clears readiness and stale review/confirmation state. Turn/session duration, transcript length, initialization/idle timeout, and concurrency limits return controlled errors with text fallback.

All operations are JSON under `/api/v1/live/sessions`. FastAPI owns lifecycle state, the active participant, version order, and receipt readiness. `GET /health` remains the service health check. `POST /api/v1/agreements/analyze` remains the standalone analysis contract, but the product workflow uses session endpoints.

## Session and Analysis

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/live/sessions` | Create an English Live session with Customer/Service provider domain roles and an initially empty conversation. |
| `GET` | `/api/v1/live/sessions/{session_id}` | Reload the authoritative durable session view after refresh or backend restart. |
| `POST` | `/api/v1/live/sessions/{session_id}/analysis` | Analyze the draft and create Agreement Map v1. Body: `expected_agreement_version_id` (initially `null`). |
| `GET` | `/api/v1/live/sessions/{session_id}/agreement-versions` | List immutable snapshots in version order. |
| `GET` | `/api/v1/live/sessions/{session_id}/agreement-versions/{version_id}` | Retrieve one immutable snapshot for comparison. |

An `AgreementVersion` contains its ID and increasing internal number, user-facing `meaningful_version_number`, `has_meaningful_change`, deterministic `semantic_fingerprint`, parent and session IDs, creation time, source message IDs, full `terms`, unresolved item keys, not-applicable proposals, prompt/model/schema metadata, analysis status/warnings, exact primary clarification, and per-item changes. Internal order records every validated analysis; the meaningful number changes only when normalized agreement meaning changes.

Every session response also contains compatibility `guidance`, plus `creator_role`, `currency`, `participant_readiness`, and an optional conversation-reentry item. The client maps server lifecycle centrally to exactly:

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

`analyzing` maps to a loading state at the start of Check understanding. Lower-level clarification/check lifecycle values also map there; they do not add progress steps.

## Clarification and Check Understanding

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/questions/{question_id}/selections` | `expected_agreement_version_id`, acting `participant_id`, backend-owned `option_id`, optional `other_text`, `request_id` |
| `POST` | `/{session_id}/questions/{question_id}/leave-unresolved` | expected version, acting `participant_id`, and `request_id`; explicitly retain the exact issue as unresolved |
| `POST` | `/{session_id}/statements` | Legacy batch append: expected version, chronological `messages`, `request_id`; returns to Conversation and does not analyze. |
| `POST` | `/{session_id}/not-applicable` | expected version, participant, exact `item_key`, `request_id` |
| `POST` | `/{session_id}/optional-details/reviewed` | expected version and `request_id`; finish the optional batch without changing missing terms |
| `POST` | `/{session_id}/understanding-checks` | Begin confirmation after decision items are resolved or explicitly left open; no mandatory teach-back questions are created. |

Paths in this and later tables are relative to `/api/v1/live/sessions`. `UnderstandingQuestion` is shared by `clarification` and `understanding_check` kinds. It binds the session, immutable version, stable agreement item, semantic commitment, evidence IDs, addressed participants, question number/count, three or four options, status, and eventual outcome. Each public `UnderstandingOption` exposes a stable ID, neutral label, and kind: `recorded_position`, `recorded_meaning`, `other`, or `unsure`. Its semantic value remains backend-owned and is never accepted from the browser.

The former Live clarification-answer, review, and teach-back routes are retired from the product workflow. Question selections and `POST /understanding-checks` own the same server lifecycle rather than creating a parallel browser-managed flow.

The backend validates an option against the exact question, participant, session, item, and agreement version. `other_text` is rejected unless the `other` option is selected and requires 2–280 characters when it is selected. The first pending `ParticipantSelection` is stored internally but is absent from the public question/session response. Only after all addressed participants submit does the question expose the neutral outcome: `aligned`, `meaning_changed`, `different`, `unsure`, or `left_unresolved`.

Questions are deduplicated by stable item ID and semantic commitment. The service also records independent evidence from the conversation, completed choices, and confirmation. Compatible selections may create a child version. Different selections remain unresolved and are not immediately asked again; clients offer Conversation re-entry or an explicit unresolved outcome. Untouched optional missing topics are excluded from required decisions.

`POST /statements` accepts multiple chronological messages but never analyzes them; the creator must explicitly call `/analysis` after both people are ready. Marking optional details reviewed records workflow progress only; it does not add evidence or convert a missing term to alignment. Matching recorded meaning completes a question; matching alternative meaning enters the immutable version-change flow; `unsure` cannot align; and both participants may explicitly leave the item unresolved.

## Confirmation

| Method | Path | Required body fields |
| --- | --- | --- |
| `POST` | `/{session_id}/confirmations` | expected version, participant, own `understanding_review_id`, `decision`, unresolved acknowledgments, optional exact `change_item_key`, `request_id` |
| `GET` | `/{session_id}/confirmation-status` | Returns each current confirmation and whether a receipt is ready. |

A `confirm` decision binds that participant to the current version and acknowledged open items. `request_change` requires an exact item and returns the session to Conversation. New messages, re-entry, or a new version invalidate current confirmations. Duplicate request IDs and duplicate current confirmations are idempotent. A selection and confirmation record what the participant chose; neither proves comprehension, identity, or consent.

## Clarity Receipt

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/{session_id}/receipt` | Issue after both participants confirm the same current version. Body: expected version and `request_id`. |
| `GET` | `/{session_id}/receipt` | Retrieve the immutable durable snapshot; returns `receipt_not_ready` before issuance. |

The immutable receipt separates aligned, conflicting/unresolved, one-sided, not-applicable, and not-discussed entries; retains evidence and agreement history; records roles, languages, session currency, session/confirmation timestamps, original evidence currency, and an integrity hash; and reports `fully_aligned` or `contains_unresolved_items`.

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

HTTP 404 covers missing sessions, versions, or questions; HTTP 410 returns `session_expired`; 409 covers invalid state, stale versions, concurrent repository revisions, the wrong active participant, idempotency conflict, incomplete understanding, confirmation/version mismatch, and receipt readiness; 422 covers invalid item, option, or acknowledgment data. Named persistence codes include `concurrent_update` and `stored_state_invalid`; invalid or unknown stored JSON returns a controlled HTTP 500 instead of being accepted. Provider errors retain the existing safe 429/502/503/504 contract without raw provider details.

Request-ID digests are part of the durable session document. A retry with the same ID and payload returns the current successful state even after restart; using that ID for a different payload remains a conflict. The internal repository revision is intentionally absent from the public JSON contract.

## Client Usability Contract

The default client renders one primary action from `guidance`. Its first useful click must either invoke that action, reveal the exact evidence or issue needed to decide, or navigate safely back to the current summary. Loading disables repeat mutation. A 404 means the session is absent; a 410 means its configured retention period ended. Technical item keys, repository revisions, internal snapshot numbers, and fingerprints are diagnostic/provenance details and are progressively disclosed rather than used as the main instructions.
