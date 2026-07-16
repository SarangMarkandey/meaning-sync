# MeaningSync Roadmap

## Implemented

- Deterministic English homeowner/electrician demo with consent, hidden clarification answers, confirmations, and clarity receipt
- Shared `aligned`, `conflicting`, `stated_by_one`, and `not_discussed` domain contract
- English text-based Live Analysis preview with add/edit/remove/sample input
- Backend-only OpenAI Responses API integration using Pydantic Structured Outputs
- Prompt version `agreement-analysis-v3`, nested clarification ownership, atomic topic/facet keys, `store=False`, evidence hydration, partial analysis warnings, and controlled failures
- Twelve-case English evaluation corpus; mocked tests spend no credits

## Partially Implemented

- Independent `en`/`hi` language settings and translation interface; only English flows are enabled
- Session-oriented models; only Demo Mode currently persists sessions, and only in memory

## Planned Milestones

1. Evaluate and refine English analysis with explicitly authorized opt-in model runs.
2. Add separate live participant confirmation and produce a live clarity receipt.
3. Add Hindi UI, Hindi analysis, and optional translation while preserving original evidence.
4. Add audio capture/playback with explicit consent and privacy controls.
5. Add separate-device QR joining and realtime session updates.
6. Add durable persistence, retention/deletion controls, and expanded safety review.

Planned features are not represented as working. MeaningSync does not provide legal advice or create a legally enforceable document.
