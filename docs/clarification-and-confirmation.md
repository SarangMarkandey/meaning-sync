# Clarification and Confirmation

## Exact Choice-Based Clarification

Live clarification remains owned by one validated agreement item. Its `UnderstandingQuestion` record stores the question, session, immutable version and exact agreement-item IDs; kind; neutral prompt and options; evidence references; addressed and answered participant roles; question progress; status; and eventual outcome/resulting version. The UI shows that item’s recorded positions and expandable original evidence; it never substitutes a detached broad-topic marker.

The server selects one required issue with a deterministic priority: scope; amount and price coverage; materials; timing; payment; then other critical responsibility. Stable agreement-item order breaks ties. A clarification fingerprint binds the exact semantic target and normalized participant positions across versions. If an equivalent active clarification already exists, the service reuses it instead of showing a duplicate first action.

The server chooses the acting participant. A one-sided issue is sent only to the participant who did not state a position. A direct conflict asks both people in Homeowner-then-Electrician order. Choices are neutral renderings of the actual recorded positions, never invented distractors, and use stable backend-owned option IDs and semantic values in the same order for both people. `Something else` reveals a required short text field for that participant; `I'm not sure` records uncertainty and can never create alignment.

After the first selection, the public session view exposes only that it was received—not its option, semantic value, text, or selection ID. The browser also does not retain it in page state, a query string, or local storage for the next participant. Once every addressed participant answers, MeaningSync reveals the outcome neutrally. Explicit new meaning enters the existing immutable message/version flow; there is no fixture fallback.

Clarification can end resolved, still unresolved, or deliberately left unresolved. Matching recorded meaning completes the item. Matching alternative meaning cannot silently confirm the old version; it produces a changed version for concise review. Different meanings return only that item to clarification. `Something else` is processed through the same exact-item versioning rules. `I'm not sure` shows relevant evidence and permits another choice or an explicit unresolved outcome. Repeated attempts for one item are limited by `MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT` (default 3). MeaningSync never invents agreement or treats navigation, silence, or uncertainty as acknowledgment.

## Missing and Not Applicable

A `not_discussed` item stays not discussed unless new participant statements provide evidence and a successful analysis changes it. Unless classified as a critical responsibility, it appears in an optional-details batch after required issues. Participants can add several speaker-attributed statements in one deliberate submission, leave the items not discussed, or propose not applicable. Each not-applicable proposal records who proposed it. One participant’s proposal does not bind the other or convert the item to aligned; the proposal remains visible in final review and the receipt. Only mutual acknowledgment affects the meaningful agreement fingerprint.

Starting Check understanding requires acknowledgment of every conflicting or one-sided item in the exact current version. Optional not-discussed items remain separately visible without being presented as agreed. This lets a session finish with fully aligned meaning or with the same discussed-but-unresolved meaning explicitly acknowledged by both participants.

## Immutable Version Comparison

Every successful analysis produces a new frozen internal snapshot with a monotonically increasing number and parent link. Prior snapshots remain retrievable. The user-facing map number advances only when the semantic fingerprint changes; the primary UI shows one concise `Updated:` notice while meaningful version history stays under Advanced details. All write actions use the expected current internal version; stale actions fail with HTTP 409 rather than modifying a newer map.

## Same-Device Check Understanding

The normal path is tap-based: show one plain-language question, display neutral radio-card choices, and enable one **Submit my choice** action only after a valid selection. The stage explains: “Choose the meaning you understood. Your choice stays private until both people answer.” Progress shows the current question number. A handoff separates Homeowner and Electrician without claiming authentication or strong privacy.

FastAPI selects only high-impact commitments such as scope, price, extra costs, timing, payment, and responsibilities that could affect cost, safety, or access. After a completed clarification supported independently by both participants, it asks at most one additional question and skips directly to separate confirmation when none is eligible. If no clarification was needed, it normally asks one or two questions for a simple job and at most three for a broad agreement. Optional missing terms are excluded unless participants chose to add, resolve, or explicitly acknowledge them.

Every question binds the current session, immutable agreement version, stable agreement item, semantic commitment, and evidence or participant positions that support its choices. The server validates the selected option ID against the exact question and acting participant. Stable item IDs and normalized semantic meaning remove duplicates even when wording differs. A server-owned evidence record identifies items already independently supported by the conversation, completed clarification, completed understanding check, or confirmation; clarification evidence prevents the same item from being checked again.

The deterministic outcome rules are the same safety boundary used for clarification: a matching recorded meaning completes the check; a shared alternative enters the versioned change flow; different choices reopen only that item; `Something else` requires concise text; and `I'm not sure` never becomes alignment. Both people can deliberately leave an item unresolved, which remains visible in the map and receipt. The check records selected stated meaning; it does not grade an answer or prove comprehension.

## Separate Confirmation

Only the server-selected active participant can confirm through the normal UI. A confirmation binds its participant, current version, completion of that participant’s applicable understanding selections, acknowledgments for every conflicting or one-sided item, language, request ID, and timestamp. Homeowner and Electrician confirm separately; one record can never stand in for both.

`Confirm my understanding` stores an idempotent current-version confirmation. `I need a change` requires an exact item key and reopens clarification. New statements, changed term status, or any later agreement version invalidate prior confirmations and return the participants to the applicable check. Receipt issuance is blocked until required selections are complete or deliberately unresolved and two valid current-version confirmations exist. A confirmation is a recorded selection, not identity verification, verified consent, an electronic signature, or proof of comprehension.
