# Live Data Model

## Durable Session State

`live_sessions` stores Pydantic-validated versioned JSON plus optimistic `revision`, creation/update times, and expiry. New documents use `state-v4`; readers migrate v1/v2/v3 documents with empty consent and zero-duration defaults. State includes participants, participation mode, creator role, currency, per-role readiness, audio consent/duration, messages, immutable agreement versions, private selections, confirmations, idempotency digests, evidence, and receipt.

Typed messages retain effective text, language, order, timestamp, speaker, and source. Audio messages additionally retain immutable machine transcript, optional participant correction, analyzed effective text, transcription model/request, consent reference, capture timestamps, and duration. Evidence copies this provenance into agreement versions and receipts. Raw audio, SDP, partial deltas, media objects, and API credentials are never fields in the durable model.

## Access Credentials and Invitations

`live_access_credentials` stores a session/role, SHA-256 token hash, creation/expiry/last-seen times, and optional revocation. Tokens contain at least 256 random bits and are returned once. Plaintext tokens never enter SQL, logs, URLs, or receipt state.

`live_session_invitations` stores the opposite of `creator_role`, a SHA-256 invitation hash, expiry, use/revocation state, and exchanged credential ID. A conditional update atomically claims one valid invitation before creating that role credential; exactly one concurrent exchange succeeds.

## Ownership and Retention

The session owns workflow state. Access records authorize a role credential, not a person’s identity. Session, credential, and invitation TTLs are independent. Expiry is enforced on access; cleanup, backup, and deletion policies remain deployment responsibilities.
