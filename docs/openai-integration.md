# OpenAI Integration

## Backend-Only Design

FastAPI uses the official asynchronous Python SDK and `responses.parse` with strict `AgreementAnalysisModelOutput`. Prompt `agreement-analysis-v3` separates compound statements into canonical atomic items such as `price.amount` and `materials.inclusion`. A possible clarification is nested on its owning unresolved term, so the model does not independently repeat a target key or evidence IDs. The default model is `gpt-5.6`; requests set `store=False`. The browser never receives or uses `OPENAI_API_KEY`.

Configure `api/.env` from the ignored example:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
OPENAI_STORE_RESPONSES=false
OPENAI_REQUEST_TIMEOUT_SECONDS=30
```

`OPENAI_STORE_RESPONSES` cannot be enabled by configuration. Do not log keys, full participant conversations, raw provider errors, prompts, or model reasoning.

## Failure Behavior

Missing/invalid keys, rate limits, quota/provider failures, timeouts, connection errors, refusals, absent parsed output, schema failures, and invalid core evidence become controlled application errors. A valid core map with an invalid, ambiguous, or misplaced clarification instead returns HTTP 200 partial success with `clarification_unavailable`; it never fabricates a question. Live Analysis never falls back to deterministic or fixture data, and Demo Mode remains available without a key.

## Status

Implemented: Responses API, Structured Outputs, prompt versioning, timeouts, safe errors, and mocked provider tests. Partially implemented: operational monitoring. Planned: production secret management, observability without conversation logging, and authorized model evaluation. MeaningSync does not provide legal advice.
