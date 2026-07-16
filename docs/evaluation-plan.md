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

## Status

Implemented: corpus, mocked coverage, and skipped-by-default integration harness. Partially implemented: real-model baselines have not been established. Planned: Hindi/cross-language cases, regression scoring, privacy red-teaming, and human review of live clarity-receipt semantics. MeaningSync does not provide legal advice.
