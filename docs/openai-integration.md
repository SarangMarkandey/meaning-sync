# OpenAI Integration

## Backend-Only Design

FastAPI uses the official asynchronous Python SDK and `responses.parse` for two bounded Structured Outputs tasks. `AgreementAnalysisModelOutput` with prompt `agreement-analysis-v4` separates compound statements into canonical atomic items such as `price.amount` and `materials.inclusion`, while trusted clarification context identifies which participant responses answer an application-owned question. `TeachbackModelOutput` with prompt `teachback-comparison-v1` compares one participant’s explanation only with required items from a trusted agreement version. The default model is `gpt-5.6`; every request sets `store=False`. The browser never receives or uses `OPENAI_API_KEY`.

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

Live analysis runs only after explicit draft, clarification, or additional-statement submission. Teach-back comparison runs only after that participant explicitly submits. Request IDs prevent duplicate workflow writes, and results remain attached to the in-memory session. Normal tests inject deterministic or mocked implementations and consume no credits; real-model evaluation remains explicitly opt-in.

The UI does not call the model merely to decide what screen or button comes next. FastAPI derives guidance, required/optional classification, deterministic issue priority, and clarification deduplication from validated application state. Optional-detail messages can be submitted as one deliberate batch, producing at most one agreement re-analysis for that batch rather than one request per field.

After validation, the application computes a semantic fingerprint from normalized meaning and trusted provenance fields. Provider wording, IDs, timestamps, and model metadata do not create a new user-facing Agreement Map number. This comparison does not discard the response: every successful analysis remains an immutable internal snapshot. Clarification fingerprints prevent equivalent active questions from triggering a duplicate clarification cycle, while distinct atomic targets remain separate.

Teach-back validation requires exactly the reviewed version’s required item keys. The model returns comparison states only; application code derives safe feedback from trusted agreement summaries and never exposes chain-of-thought, confidence percentages, prompts, or raw provider responses.

## Status

Implemented: agreement and teach-back Responses API calls, Structured Outputs, prompt versioning, `store=False`, timeouts, safe errors, no-fallback behavior, and mocked provider tests. Partially implemented: operational monitoring. Planned: production secret management, privacy-preserving observability, and explicitly authorized model evaluation. MeaningSync does not provide legal advice.
