# Privacy and Safety

## Data Flow

The browser sends speaker-attributed English statements to FastAPI through the typed JSON client. Only FastAPI can call OpenAI. Live agreement analysis and Live teach-back comparison use the Responses API with `store=False`, strict Pydantic outputs, timeouts, and safe provider-error translation. The application must not put API keys, prompts, model reasoning, raw provider exceptions, or full conversations in routine logs.

Demo Mode is deterministic, key-free, and sends nothing to OpenAI. Normal automated tests use deterministic or mocked analyzers/evaluators and consume no API credits. A paid integration run remains explicitly opt-in and must never be used as a routine test.

## Process-Local Storage

Live sessions currently retain participants, messages, immutable agreement versions, pending clarification answers, review status, teach-back records, confirmations, and clarity receipts only in FastAPI process memory. No database, durable backup, or cross-worker recovery exists. A page refresh can recover while the same backend process is alive; a restart or memory loss removes the session. The UI reports a missing session and directs users to start again rather than presenting cached browser state as authoritative.

The first clarification answer remains in private process state and is not included in the public session response until the second participant answers. Submitted teach-back text is retained for evaluation but excluded from normal session serialization. These controls reduce accidental disclosure in the ordinary flow; they are not a durable secrecy guarantee.

Progressive disclosure keeps full evidence, technical item keys, internal snapshot history, fingerprints, and optional details out of the default decision view. This reduces accidental shoulder-surfing and cognitive overload, but it is presentation—not access control. The data remains available to the same browser session and in FastAPI process memory.

## Same-Device Limitations

The handoff UI asks users to pass the device during Clarify, Review, and Confirm, locks the completed step, and does not display the previous participant’s hidden response or teach-back. There is no authentication, identity verification, separate user account, secure device boundary, or protection from browser/devtools access. Do not describe this milestone as private independent voting or verified consent.

An explicit **Continue unresolved** action records that an issue remains open; it is not consent to the other participant’s position. Optional details can remain not discussed. Neither advancing a screen nor viewing a receipt silently changes agreement meaning.

Separate confirmations bind server-owned participant role, current version, that participant’s teach-back, acknowledgments, language, and timestamp. They record stated understanding; they are not electronic signatures.

## Receipt and Integrity

A clarity receipt is an immutable in-memory snapshot. It preserves aligned and unresolved meaning, one-sided and not-discussed terms, not-applicable proposals, evidence, clarification history, teach-back completion, and separate confirmation timestamps. Its SHA-256 integrity hash is calculated over a canonical server-side payload and can reveal payload changes when recomputed. It does not prove identity, authorship, time from a trusted authority, non-repudiation, or legal validity; it is not a digital signature.

Keep secrets only in ignored local `.env` files and use explicit CORS origins. Durable encryption, retention/deletion controls, authenticated access, audit logging, and secure separate-device participation remain planned. MeaningSync does not provide legal advice, and a clarity receipt is not a legally enforceable contract.
