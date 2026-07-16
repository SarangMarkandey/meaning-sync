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

Prompt `agreement-analysis-v3` treats messages as untrusted data, prohibits invention and silence-based agreement, and decomposes compound statements into atomic claims. A clarification question is nested on its exact `conflicting` or `stated_by_one` model term; the backend derives its public target and evidence from that owner. This removes the fragile requirement for the model to reproduce a detached item key, topic, facet, and evidence list.

After parsing, the application verifies participants, evidence ownership, both-party support, one-sided semantics, canonical topic/facet keys, duplicate atomic items, and clarification ownership. Original evidence is hydrated unchanged from the trusted request. Legacy detached output is resolved only by exact item key, exact topic/facet, unique unresolved evidence overlap, or a sole unresolved item; ambiguous matches are never guessed.

The sanitized fixture `api/tests/fixtures/problematic_price_materials_output.json` preserves the observed amount/coverage failure for offline regression testing. Its valid agreement map now returns `status: "partial"` with `clarification_unavailable`, while omitting the unsafe clarification. Invalid core terms or evidence remain controlled upstream-analysis errors.

## Status

Implemented: English topics, analyzers, validation, safe failures, and evidence UI. Partially implemented: language-neutral model fields. Planned: Hindi/cross-language evaluation, live confirmation, and a live clarity receipt. MeaningSync does not provide legal advice.
