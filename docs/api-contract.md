# API Contract

All implemented workflow endpoints are under `/api/v1/demo/sessions` and use JSON. Session state is in memory.

## Create and Load a Session

`POST /api/v1/demo/sessions` accepts an optional body; omitted values default independently to English:

```json
{"participant_languages":{"hirer":"en","worker":"en"}}
```

`GET /api/v1/demo/sessions/{session_id}` returns the same `SessionView`. Its core shape is:

```json
{
  "id": "uuid",
  "mode": "demo",
  "stage": "created",
  "participants": [
    {"id":"hirer","role":"hirer","display_name":"Homeowner","language":"en","requested_display_language":"en"},
    {"id":"worker","role":"worker","display_name":"Electrician","language":"en","requested_display_language":"en"}
  ],
  "consent": {"hirer":"pending","worker":"pending"},
  "transcript": [
    {
      "id":"message-1",
      "session_id":"uuid",
      "participant_id":"hirer",
      "speaker":"hirer",
      "speaker_name":"Homeowner",
      "original_text":"I will pay ₹1,200 for repairing the fan and two switches, including replacement parts.",
      "original_language":"en",
      "timestamp":"2026-07-15T00:00:00Z",
      "translations":{}
    }
  ],
  "terms": [],
  "clarification_questions": [],
  "confirmations": []
}
```

Only `en` and `hi` are accepted. The current deterministic content is English; Hindi and mixed-language user flows are planned.

## Messages and Agreement Terms

Each transcript message includes `id`, `session_id`, `participant_id`, `speaker`, `speaker_name`, `original_text`, `original_language`, `timestamp`, and `translations` keyed by target language.

Each term includes `id`, `label`, `status` (`confirmed`, `conflict`, or `missing`), `value`, `evidence`, and `participant_confirmations`. Transcript evidence contains `participant_id`, `message_id`, and `original_text`. Missing terms have no evidence and remain distinct from conflicts.

## Workflow Endpoints

- `POST /{session_id}/consent` — `{"party":"hirer","accepted":true}`
- `POST /{session_id}/analysis` — advances discussion to analyzed and returns terms.
- `POST /{session_id}/clarifications` — opens clarification.
- `POST /{session_id}/clarifications/{question_id}/answers` — accepts `party` and an answer expressing included/separate materials. Before both answer, `revealed` is false and `answers` is empty. Once both answer, each answer includes canonical `meaning`.
- `POST /{session_id}/confirmations` — accepts `party`, `confirmed`, and `teachback`; both parties must confirm.
- `POST /{session_id}/receipt` — returns the clarity receipt only after confirmation.

Example clarification body:

```json
{"party":"worker","answer":"Replacement parts are separate"}
```

Example result after both answers:

```json
{
  "revealed": true,
  "answers": [
    {"party":"hirer","answer":"Parts are charged separately","meaning":"charged_separately"},
    {"party":"worker","answer":"Replacement parts are separate","meaning":"charged_separately"}
  ],
  "resolved": true
}
```

Timestamps, question metadata, and the resulting term are also present in actual responses. There are no implemented Live Mode, translation, audio, QR, or persistence endpoints.
