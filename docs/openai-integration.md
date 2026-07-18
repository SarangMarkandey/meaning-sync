# OpenAI Integration

## Backend-Only Design

FastAPI uses the official asynchronous Python SDK and `responses.parse` with Pydantic Structured Outputs. Prompt `agreement-analysis-v4` produces atomic agreement items; the default model is `gpt-5.6`, every request sets `store=False`, and the browser never receives `OPENAI_API_KEY`.

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
OPENAI_STORE_RESPONSES=false
OPENAI_REQUEST_TIMEOUT_SECONDS=30
```

## Request Boundary

Live makes a model request only when the session creator explicitly chooses **Compare what we mean** after both roles have contributed and marked ready. Adding a single message or legacy statement batch, setting readiness, joining, polling, constructing/answering choices, confirmation, and receipt issuance never call OpenAI. Demo uses deterministic fixture data. Currency is session metadata; the model/application must not convert evidence amounts.

The `analyzing` state is committed before the external await and shown as loading at the start of Check understanding. The SQL transaction is released while awaiting the provider. A failure restores a retryable Conversation state without deterministic fallback or lost durable data.

## Validation and Failures

Missing/invalid credentials, limits, timeouts, connection failures, refusals, schema failures, and invalid evidence become controlled errors without raw provider detail. A valid map with unusable clarification remains a partial success. FastAPI deterministically builds choices, validates private selections, resolves compatible outcomes, manages versions, and computes receipt hashes. Normal tests inject fixtures/mocks and spend no credits; paid evaluation is explicitly opt-in.

Do not log keys, full conversations, prompts, model reasoning, or provider bodies. MeaningSync exposes evidence and application outcomes, not model chain-of-thought or confidence scores.
