# OpenAI Integration

## Backend-Only Design

FastAPI uses the official asynchronous Python SDK and `responses.parse` with Pydantic Structured Outputs. Prompt `agreement-analysis-v5` produces atomic agreement items and required English/Hindi localizations; the default model is `gpt-5.6`, every request sets `store=False`, and the browser never receives `OPENAI_API_KEY`.

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
OPENAI_TRANSLATION_MODEL=gpt-5.6
OPENAI_STORE_RESPONSES=false
OPENAI_REQUEST_TIMEOUT_SECONDS=30
OPENAI_ANALYSIS_TIMEOUT_SECONDS=90
OPENAI_TRANSCRIPTION_MODEL=gpt-realtime-whisper
```

## Request Boundary

Live agreement analysis makes a model request only when the session creator explicitly chooses **Compare what we mean** after both roles have contributed and marked ready. In mixed-language Live, adding a finalized typed or reviewed-audio message first stores the original and then performs one separate GPT-5.6 Structured Output translation. Joining, polling, setting readiness, constructing/answering choices, confirmation, and receipt issuance do not call OpenAI. Same-language sessions do not translate. Demo uses deterministic fixture data. Currency is session metadata; the model/application must not convert evidence amounts.

The `analyzing` state is committed before the external await and shown as loading at the start of Check understanding. The SQL transaction is released while awaiting the provider. Agreement analysis has a dedicated 90-second timeout because its localized structured result is larger than translation or teach-back output. A failure restores a retryable Conversation state without deterministic fallback or lost durable data; background polling does not hide the failure message. MeaningSync does not retry paid analysis automatically.

## Realtime Transcription Boundary

Live Speak uses transcription-only Realtime sessions and browser WebRTC. The authorized browser posts its SDP offer to FastAPI; FastAPI calls the unified `/v1/realtime/calls` interface with the backend key, transcription session configuration, `gpt-realtime-whisper` default, active participant ISO language (`en` or `hi`), and manual commit (`turn_detection: null`). Only the SDP answer returns. Delta/completed events arrive over the WebRTC data channel; the client commits on **Stop and review** and never submits partial text. Realtime is not asked to translate; only the reviewed effective transcript is translated afterward when participant languages differ.

## Bidirectional Text Translation

`OpenAITranslationService` uses the asynchronous Responses API with Pydantic Structured Outputs, `gpt-5.6` by default, and `store=False`. The Audio translations endpoint is not used because its output is English-only. The translation prompt forbids summarization, legal rewriting, invented context, and loss of uncertainty; it explicitly preserves numbers, currencies, dates, quantities, negation, inclusion/exclusion, and labour/material distinctions. Narrow deterministic validation rejects unsafe output. Failed translation remains retryable while the immutable original stays visible. `DeterministicTranslationService` provides the same contract for Demo and tests without a network request.

The initializer is injected behind a narrow protocol. Normal tests use deterministic success/failure fakes; opt-in paid tests remain disabled. Agreement analysis still uses `OPENAI_MODEL` and is unchanged by this milestone.

## Validation and Failures

Missing/invalid credentials, limits, timeouts, connection failures, refusals, schema failures, unsafe translation, and invalid evidence become controlled errors without raw provider detail. A valid map with unusable clarification remains a partial success. FastAPI deterministically builds choices, validates private selections by stable semantic option ID, resolves compatible outcomes, manages versions/localizations, and computes receipt hashes. Normal tests inject fixtures/mocks and spend no credits; paid evaluation is explicitly opt-in.

Do not log keys, full conversations, prompts, model reasoning, or provider bodies. MeaningSync exposes evidence and application outcomes, not model chain-of-thought or confidence scores.
