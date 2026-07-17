# Agreement Analysis

## Shared Contract

Demo and Live Mode use one contract. Every term has a canonical atomic `analysis_item_key`, matching `topic` and `facet`, neutral summary, participant positions and statuses where applicable, transcript evidence IDs, backend-hydrated evidence, and an optional exact clarification target. For example, `price.amount` is independent from `materials.inclusion`, and `timing.start` is independent from `completion.deadline`.

Meaning states are semantic, not confidence scores:

- `aligned`: both participants explicitly support compatible meaning.
- `conflicting`: both explicitly state incompatible meaning.
- `stated_by_one`: exactly one participant states the term.
- `not_discussed`: neither participant states the term.

The UI maps these to Confirmed, Needs clarification, and Not discussed without erasing the underlying state.

## Analyzers and Validation

`DeterministicAgreementAnalyzer` powers the stable, key-free demo. `OpenAIAgreementAnalyzer` powers English Live Text Analysis. Both implement `AgreementAnalyzer` and return the same response model.

Prompt `agreement-analysis-v4` treats messages as untrusted data, prohibits invention and silence-based agreement, and decomposes compound statements into atomic claims. A clarification question is nested on its exact `conflicting` or `stated_by_one` model term; the backend derives its public target and evidence from that owner. This removes the fragile requirement for the model to reproduce a detached item key, topic, facet, and evidence list.

After parsing, the application verifies participants, evidence ownership, both-party support, one-sided semantics, canonical topic/facet keys, duplicate atomic items, and clarification ownership. Original evidence is hydrated unchanged from the trusted request. Legacy detached output is resolved only by exact item key, exact topic/facet, unique unresolved evidence overlap, or a sole unresolved item; ambiguous matches are never guessed.

The sanitized fixture `api/tests/fixtures/problematic_price_materials_output.json` preserves the observed amount/coverage failure for offline regression testing. Its valid agreement map now returns `status: "partial"` with `clarification_unavailable`, while omitting the unsafe clarification. Invalid core terms or evidence remain controlled upstream-analysis errors.

## Versioned Live Processing

The Live session service turns each successful validated response into an immutable internal agreement snapshot. The initial snapshot remains available when separately submitted clarification answers are appended as messages and re-analysis creates a child snapshot. Internal version metadata includes source message IDs and analyzer prompt/model/schema versions. New statements trigger analysis only after deliberate submission; provider failure never replaces Live output with a deterministic fixture.

Internal snapshot order and the user-facing Agreement Map number are deliberately different. Every valid analysis is retained, but the displayed version advances only when a SHA-256 semantic fingerprint changes. Its canonical payload covers normalized item state, participant positions and statuses, evidence-backed missing-to-stated transitions, and mutually acknowledged not-applicable treatment. Neutral-summary wording, IDs, timestamps, request/provider metadata, and other operational fields do not affect it. `has_meaningful_change` tells the UI whether a concise update notice is useful.

Required issues are selected deterministically in this order: scope; amount and price coverage; materials; timing; payment; then other critical responsibility. Stable item order breaks ties. Clarification fingerprints combine the exact semantic target and normalized participant positions across versions so an equivalent open question is reused rather than duplicated. Different atomic items are never collapsed merely because their wording is similar.

Conflicting and critical one-sided meanings are required issues. They must be resolved or explicitly carried unresolved. Not-discussed topics are optional unless the server classifies them as critical; optional topics are grouped for review and may be addressed in one deliberate batch. Silence cannot move a missing term to aligned, and a unilateral not-applicable proposal remains separately attributed. Only mutual acknowledgment participates in the meaningful semantic fingerprint.

## Choice-Based Understanding

FastAPI constructs clarification and understanding questions from validated agreement data rather than inventing quiz answers. Each question binds its session, immutable agreement version, stable agreement item, semantic commitment, and supporting evidence or participant positions. Backend-owned option IDs and semantic values remain in a stable order for both participants; labels are neutral descriptions of recorded positions or shared meaning. Every question also offers `Something else` and `I'm not sure`. Short free text is accepted only with `Something else`.

Question selection is deliberately small. Only commitments that can materially affect scope, price, extra costs, timing, payment, safety, access, or responsibility qualify. After a completed two-party clarification, the server asks at most one additional understanding question and may skip directly to confirmation. Without clarification, it prefers one or two questions for a simple job and asks no more than three for a broad agreement. Optional missing topics are excluded unless participants deliberately addressed them, and stable item IDs plus normalized semantic commitments remove duplicates even when wording differs.

The service records where independent evidence already came from: the original conversation, completed clarification, completed understanding check, or final confirmation. An item independently answered during clarification is not asked again. Selections are validated against the exact question, participant, session, item, and version. A shared recorded meaning completes the check; the same alternative meaning enters the existing versioned change flow; different meanings reopen only that item; `I'm not sure` never produces alignment; and an explicitly unresolved result remains unresolved in the map and receipt.

## Status

Implemented: English topics, analyzers, validation, immutable Live versions, exact choice-based clarification, bounded and deduplicated understanding checks, separate confirmation, safe failures, evidence UI, and Live clarity receipt. Partially implemented: language-neutral model fields. Planned: Hindi/cross-language evaluation and durable session persistence. MeaningSync records selected stated meaning; it does not prove comprehension or provide legal advice.
