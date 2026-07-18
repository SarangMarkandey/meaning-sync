# Evaluation Plan

## Offline Coverage

The 12-scenario English agreement corpus covers complete agreement, price/material/timing/payment conflicts, one-sided and missing terms, self-correction, paraphrase, no agreement, and prompt-injection-like text. Assertions target semantic state, atomic ownership, evidence integrity, and controlled failures—not exact model prose. Normal tests use fixtures/mocks and spend no credits.

Workflow coverage must assert:

- exactly six visible steps and one central lifecycle mapping;
- creator role in either direction and opposite-role invitations;
- role-scoped messages, both-party contribution/readiness, and creator-only comparison;
- no analysis on message submission and readiness reset on new text;
- immutable parent-linked re-analysis versions and evidence requirements;
- three agreement-map sections and evidence for every non-missing term;
- hidden first private choice, compatible resolution, different-choice non-repetition, and optional missing topics;
- no mandatory teach-back/minimum question count;
- two current-version confirmations, Conversation re-entry, and invalidation after change;
- durable state-v3 migration, restart recovery, idempotency, optimistic conflicts, expiry, and stable receipt hash;
- receipt preservation of roles, languages, session/evidence currency, times, history, unresolved/missing items, and disclaimer.

Frontend tests cover Preferences/Participation, one-action join and automatic waiting transition, conversation/chat readiness, accessible decision controls, separate confirmation, loading/error/empty states, and deterministic Demo parity. Browser verification checks 1440×900, 1024×768, and 390×844 for overflow, clipping, focus, console/hydration errors, and usable primary actions.

## Paid Evaluation

Real-model evaluation is deliberately opt-in:

```bash
RUN_OPENAI_INTEGRATION=1 pytest tests/test_evaluations.py
```

It requires an authorized key and consumes credits. Routine verification must not run it. Record any authorized run’s model, prompt version, date, and reviewed semantic deltas in `BUILD_LOG.md`.

## Planned

Add opt-in PostgreSQL deployment coverage, Hindi/cross-language cases, privacy red-teaming, and moderated usability review. MeaningSync records stated meaning; it does not prove comprehension or provide legal advice.
