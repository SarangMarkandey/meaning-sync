# Clarification and Confirmation

## Exact Clarification

Live clarification remains owned by one validated agreement item. Its record stores the clarification ID, exact item key and term ID, source agreement-version ID, neutral question, addressed participant roles, attempt number, timestamps, response message IDs, result status, and resulting version ID. The UI shows that item’s two positions and expandable original evidence; it never substitutes a detached broad-topic marker.

The server selects one required issue with a deterministic priority: scope; amount and price coverage; materials; timing; payment; then other critical responsibility. Stable agreement-item order breaks ties. A clarification fingerprint binds the exact semantic target and normalized participant positions across versions. If an equivalent active clarification already exists, the service reuses it instead of showing a duplicate first action.

The server chooses the acting participant. A one-sided issue is sent only to the participant who did not state a position. A direct conflict asks both people in Homeowner-then-Electrician order; after the first answer, the public session view exposes only that it was received—not its text or message ID. Once every addressed participant answers, the responses become immutable speaker-attributed conversation messages and one deliberate analyzer call produces the next internal snapshot. There is no fixture fallback.

Clarification can end `resolved`, `still_unresolved`, or `left_unresolved`. Repeated attempts for one item are limited by `MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT` (default 3). At any permitted point the participants may use the explicit unresolved action; at the limit, MeaningSync stops asking and requires that choice before review. It never invents agreement or treats navigation as acknowledgment.

## Missing and Not Applicable

A `not_discussed` item stays not discussed unless new participant statements provide evidence and a successful analysis changes it. Unless classified as a critical responsibility, it appears in an optional-details batch after required issues. Participants can add several speaker-attributed statements in one deliberate submission, leave the items not discussed, or propose not applicable. Each not-applicable proposal records who proposed it. One participant’s proposal does not bind the other or convert the item to aligned; the proposal remains visible in final review and the receipt. Only mutual acknowledgment affects the meaningful agreement fingerprint.

Starting review requires acknowledgment of every conflicting or one-sided item in the exact current version. Optional not-discussed items remain separately visible without being presented as agreed. This lets a session finish with fully aligned meaning or with the same discussed-but-unresolved meaning explicitly acknowledged by both participants.

## Immutable Version Comparison

Every successful analysis produces a new frozen internal snapshot with a monotonically increasing number and parent link. Prior snapshots remain retrievable. The user-facing map number advances only when the semantic fingerprint changes; the primary UI shows one concise `Updated:` notice while meaningful version history stays under Advanced details. All write actions use the expected current internal version; stale actions fail with HTTP 409 rather than modifying a newer map.

## Same-Device Teach-Back

Review is sequential: pass the device to Homeowner, then Electrician. Normal API serialization omits original submitted teach-back text, and the UI does not show one participant the other’s response. This is same-device presentation without authentication or strong privacy.

Each participant explains critical scope, amount/coverage, materials, timing, discussed payment, and acknowledged unresolved items. The backend evaluator compares only against trusted current-version terms and returns per-item and overall states:

- `matches`: materially equivalent meaning, including explicit recognition that an acknowledged item remains unresolved.
- `partially_matches`: some required meaning is present; ask the smallest focused follow-up.
- `insufficient`: not enough meaning to compare; do not advance.
- `contradicts`: incompatible meaning; reopen the exact affected item for clarification.

Referenced items must exist in the reviewed version. The evaluator cannot introduce or resolve agreement meaning, and no confidence score or chain-of-thought is exposed. Live uses OpenAI Structured Outputs from FastAPI with `store=False`; tests use a deterministic evaluator or mocked provider.

## Separate Confirmation

Only the server-selected active participant can confirm through the normal UI. A confirmation binds its participant, current version, that participant’s matching teach-back, acknowledgments for every conflicting or one-sided item, language, request ID, and timestamp. Homeowner and Electrician confirm separately; one record can never stand in for both.

`Confirm my understanding` stores an idempotent current-version confirmation. `I need a change` requires an exact item key and reopens clarification. New statements, changed term status, or any later agreement version invalidate prior confirmations and return the participants to review. Receipt issuance is blocked until two valid confirmations and their two current matching teach-backs exist.
