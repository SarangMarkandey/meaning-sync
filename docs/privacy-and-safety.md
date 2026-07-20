# Privacy and Safety

## Data Flow

The browser sends speaker-attributed English text to FastAPI through the typed client. Only FastAPI holds the OpenAI key. The creator’s readiness-gated comparison starts agreement analysis; a consenting participant may separately initialize transcription-only WebRTC during Conversation. Demo and normal automated tests are key-free/fake.

Do not put API keys, authorization headers, invitation fragments, prompts, model reasoning, raw provider errors, or full conversations in routine logs. Keep backend secrets in ignored `.env` files and use explicit CORS origins.

## Durable Live Storage

Live sessions retain participants, creator role, currency, readiness, messages, audio consent, finalized transcript provenance, immutable versions, questions/private selections, confirmations, request digests, and receipts in validated SQL state until expiry. MeaningSync does not persist raw audio, SDP, ephemeral connection data, partial deltas, media objects, or credentials. Original evidence retains machine transcript plus any clearly marked correction. Demo remains process-local. Automatic cleanup, backup governance, and user-controlled deletion are not implemented.

## Audio Consent and Transport

Before first microphone access, each participant accepts: “MeaningSync will send your speech to OpenAI for transcription. MeaningSync stores the transcript as conversation evidence but does not save the raw audio recording.” Consent is bound to session, bearer/active role, notice version, timestamp, and request ID. A shared device requires a private role handoff; a separate device can consent only for its bearer role. Consent does not claim that OpenAI never processes or retains data.

The browser sends SDP only to authorized FastAPI, which initializes the backend-key Realtime call and returns only an SDP answer. Failures are sanitized. Configured turn/session duration, initialization/idle timeout, transcript length, and concurrency limits bound cost and exposure. HTTPS is required for real-device microphone testing; `http://localhost` is the development exception. Do not recommend disabling browser secure-context controls.

## Role Authorization

Each Live request after creation requires an expiring bearer credential bound to one session and role. Only SHA-256 hashes are stored. A separate-device creator receives only their credential; the opposite role receives an expiring, single-use invitation claimed atomically. QR generation is local, the join page removes the URL fragment, and credentials stay in `sessionStorage`. Either Customer or Service provider may create.

The first private choice is withheld from all participant-scoped responses until every addressed person answers. This prevents accidental ordinary-flow disclosure, not a compromised browser, credential, or database.

## Limitations and Receipt

Shared-device switching is presentation, not authentication, and audio attribution uses its explicit active role rather than diarization. Separate-device credentials authorize possession, not identity, and capture only that device; MeaningSync is not a participant audio call. Neither path proves comprehension, identity, or authorship. New text or finalized transcript clears readiness and invalidates current confirmations.

The immutable receipt preserves matching, unresolved, one-sided, and not-discussed terms, evidence, history, roles/languages/currency, timestamps, and a SHA-256 integrity hash. The hash is not a signature, trusted timestamp, identity proof, or legal guarantee. MeaningSync does not provide legal advice, and its receipt is not a legal contract.
