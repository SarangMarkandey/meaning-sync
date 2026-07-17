# OpenAI Integration

## Backend-Only Design

FastAPI uses the official asynchronous Python SDK and `responses.parse` for bounded agreement-analysis Structured Outputs. `AgreementAnalysisModelOutput` with prompt `agreement-analysis-v4` separates compound statements into canonical atomic items such as `price.amount` and `materials.inclusion`, while trusted clarification context identifies which participant responses answer an application-owned question. The default model is `gpt-5.6`; every request sets `store=False`. The browser never receives or uses `OPENAI_API_KEY`.

Choice construction and validation are application responsibilities. FastAPI derives neutral options from validated participant positions or recorded shared meaning, assigns stable option IDs and semantic values, and validates selections against the exact session, participant, question, item, and immutable version. Check understanding therefore adds no OpenAI request on the normal path. If model-assisted wording is added later, it may only rewrite validated semantic positions into plain language; it must not invent an option or decide the outcome.

Configure `api/.env` from the ignored example:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
OPENAI_STORE_RESPONSES=false
OPENAI_REQUEST_TIMEOUT_SECONDS=30
MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT=3
```

`OPENAI_STORE_RESPONSES` cannot be enabled by configuration. Do not log keys, full participant conversations, raw provider errors, prompts, or model reasoning.

## Failure Behavior

Missing/invalid keys, rate limits, quota/provider failures, timeouts, connection errors, refusals, absent parsed output, schema failures, and invalid core evidence become controlled application errors. A valid core map with an invalid, ambiguous, or misplaced clarification instead returns HTTP 200 partial success with `clarification_unavailable`; it never fabricates a question. Live Analysis never falls back to deterministic or fixture data, and Demo Mode remains available without a key.

Live analysis runs only after an explicit draft or additional-statement submission. Compatible explicit selections, including a shared alternative, are resolved deterministically into the existing immutable version flow with selection-derived evidence; they do not ask a model to infer agreement. Selecting a recorded meaning or `I'm not sure` also adds no model call. Request IDs prevent duplicate workflow writes, and their payload digests remain in the durable Live session across restart. The `analyzing` stage is committed before the external await and the database transaction is released until the provider returns. Normal tests inject deterministic or mocked implementations and consume no credits; real-model evaluation remains explicitly opt-in.

The UI does not call the model merely to decide what screen, question, option, or button comes next. FastAPI derives guidance, required/optional classification, deterministic issue priority, question deduplication, and check outcomes from validated application state. Optional-detail messages can be submitted as one deliberate batch, producing at most one agreement re-analysis for that batch rather than one request per field.

After validation, the application computes a semantic fingerprint from normalized meaning and trusted provenance fields. Provider wording, IDs, timestamps, and model metadata do not create a new user-facing Agreement Map number. This comparison does not discard the response: every successful analysis remains an immutable internal snapshot. Stable item IDs, semantic commitments, and independent-evidence records prevent equivalent questions from repeating while distinct atomic targets remain separate.

Selection outcome rules are deterministic. Matching recorded meaning completes the check; matching alternative meaning enters the immutable version-change flow; different meanings reopen only the exact item; `Something else` requires short text; and `I'm not sure` remains unresolved. No answer is labelled correct, and no model reasoning, confidence percentage, prompt, or raw provider response is exposed.

## Status

Implemented: agreement-analysis Responses API calls, deterministic choice construction and validation, Structured Outputs, prompt versioning, `store=False`, timeouts, safe errors, no-fallback behavior, and mocked provider tests. Partially implemented: operational monitoring. Planned: production secret management, privacy-preserving observability, and explicitly authorized model evaluation. MeaningSync does not use selections to prove comprehension or provide legal advice.
