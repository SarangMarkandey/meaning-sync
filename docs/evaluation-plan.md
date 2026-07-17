# Evaluation Plan

## Corpus and Assertions

`api/tests/fixtures/agreement_evaluations.json` contains 12 English scenarios: complete agreement, materials/price/completion/additional-work/cancellation conflicts, one-sided payment timing, missing warranty, self-correction, paraphrased alignment, no agreement, and prompt-injection-like participant text.

Evaluations assert semantic topic states and exact clarification ownership, never exact model prose. Application tests separately assert nested materials clarification, original-text preservation, inherited clarification evidence, speaker ownership, conflict evidence from both people, duplicate atomic-item rejection, and controlled invalid-evidence failures. Resolver tests cover exact topic/facet, unique evidence overlap, broad-topic ambiguity, multiple candidates, and refusal to guess. Frontend tests verify partial maps remain visible with their warning.

## Free and Paid Runs

`pytest` validates the corpus and uses mocked OpenAI responses; it spends no credits. The sanitized historical provider fixture also runs entirely offline and must produce a partial map rather than HTTP 502. A real-model run is deliberately opt-in:

```bash
RUN_OPENAI_INTEGRATION=1 pytest tests/test_evaluations.py
```

This command requires an authorized backend key and consumes API credits. Record the model, prompt version, date, failures, and reviewed semantic deltas in `BUILD_LOG.md`; do not weaken assertions simply to match one run.

## Workflow Evaluation

Live workflow tests inject deterministic or mocked analyzers. Coverage must include exact clarification item/version ownership, hidden first selection, immutable appended messages, v1/v2 preservation, increasing parent-linked versions, invalid transitions, stale writes, attempt limits, evidence requirements, and visible unilateral not-applicable proposals.

Choice fixtures cover a normal path without free text; conditional and bounded `Something else` text; uncertainty that cannot align; exact session/participant/question/item/version/option binding; rejection of invalid or stale selections; and hidden first-participant data. Outcome tests cover shared recorded meaning, shared alternative meaning with a new version, different choices reopening only one item, and deliberately unresolved outcomes. Confirmation tests bind the acting participant, current version, and completed applicable selections; require both participants; verify request-ID idempotency; and prove that a new version invalidates prior confirmations. Receipt fixtures cover fully aligned and acknowledged-unresolved outcomes, immutable snapshots, the exact disclaimer, and deterministic hashing of a fixed canonical payload.

Frontend tests cover guidance-derived primary actions, exact clarification/evidence, accessible radio-card choices, disabled submission until valid, conditional `Something else` input, separate selection submission, hidden prior selection, neutral differing/unsure outcomes, question progress, actor-bound confirmation, early-receipt protection, keyboard interaction, loading/error/handoff states, print action, and truthful missing-session recovery. Manual browser verification exercises both participants through the full workflow and error paths at 1440×900, 1024×768, 768×1024, 390×844, and 360×800, including console/hydration and horizontal-overflow checks.

Guided-flow tests additionally assert the five visible stages, Setup outside progress, a dedicated non-clickable analyzing state, and server-derived guidance with no client fallback to stale clarification history. Required selection must follow scope, amount/coverage, materials, timing, payment, then other critical responsibility with stable tie-breaking. Fixtures cover stable item/semantic deduplication, distinct atomic targets that must not be merged, omission of completed clarification items, a maximum of one additional check after successful clarification, direct confirmation when none remains, the unchanged one/two/three policy without clarification, and exclusion of untouched optional missing terms.

Version tests distinguish immutable internal events from meaningful user-facing versions. Identical canonical semantics—including normalized state, positions and statuses, evidence-backed missing-to-stated transitions, and mutual not-applicable acknowledgment—must reproduce the same fingerprint despite neutral-summary wording changes, different IDs, timestamps, or provider metadata. A real semantic change must advance the meaningful number and produce a focused update notice.

Persistence tests run against temporary migrated SQLite databases and never call OpenAI. They cover creation/reload across repository and service instances; lossless round trips for versions, evidence, questions, private selections, reviews, confirmations, request digests, and receipts; hidden first selections after restart; idempotent and conflicting request-ID reuse after restart; optimistic revision rejection; rollback of failed final selections; retryable analysis failure; unchanged receipt hashes; invalid stored JSON; and controlled expiry. The normal suite does not require Docker. A real PostgreSQL integration remains opt-in deployment verification.

Required issues must block Check understanding until resolved or explicitly carried unresolved. Optional missing items must remain not discussed, be progressively disclosed as one batch, and support one multi-message submission without a provider call per field. Refresh/retry tests prove that idempotency does not duplicate selections or advance twice. Usability assertions cover one primary first-click target, expandable evidence, hidden technical metadata, disabled repeat submission, safe Back behavior, same-device handoff, and truthful 404/409 recovery. Manual inspection confirms that choices and the primary action remain visible and usable without horizontal scrolling.

## Status

Implemented: corpus, mocked provider coverage, deterministic choice/workflow fixtures, durable repository/restart fixtures, and a skipped-by-default paid agreement-analysis harness. Check understanding is deterministic and has no paid-model baseline. Planned: opt-in PostgreSQL deployment coverage, Hindi/cross-language cases, regression scoring, privacy red-teaming, moderated usability testing, and human review of clarity-receipt semantics. MeaningSync does not prove comprehension or provide legal advice.
