# Privacy and Safety

## Data Flow

The browser sends speaker-attributed English statements to FastAPI through the typed JSON client. Only FastAPI can call OpenAI. Live agreement analysis uses the Responses API with `store=False`, strict Pydantic outputs, timeouts, and safe provider-error translation. Clarification and understanding choices are built and validated deterministically by FastAPI. The application must not put API keys, prompts, model reasoning, raw provider exceptions, or full conversations in routine logs.

Demo Mode is deterministic, key-free, and sends nothing to OpenAI. Normal automated tests use deterministic or mocked analyzers plus deterministic choice services and consume no API credits. A paid integration run remains explicitly opt-in and must never be used as a routine test.

## Durable Live Storage

Live sessions retain participants, messages, immutable agreement versions, questions, pending participant selections, independent-evidence status, confirmations, request-ID digests, and clarity receipts in a validated versioned database document. PostgreSQL is recommended for production; ignored SQLite supports local development. Live state survives backend restarts until the configured 1–720 hour TTL expires. Demo Mode remains process-local.

Persistence is not authorization. P1A has no participant token, account, role-specific read boundary, or deletion endpoint. Anyone who can reach a session through the current same-device application context is not cryptographically distinguished from either participant. Backups, encryption-key operations, automatic expired-row cleanup, audit logging, and user-controlled deletion are not implemented; production operators must apply database access, encryption, backup, and deletion policies outside the application for now.

A pending participant’s option, semantic value, selection ID, and `Something else` text remain in backend-only persisted state until every addressed participant answers. For a two-person question, the first selection is not included in the public session response, page payload, query string, local storage, or client state available during the handoff to the second person. After both answer, the UI may reveal their positions neutrally. These controls reduce accidental disclosure in the ordinary flow; database persistence does not make them a participant-specific secrecy guarantee.

Progressive disclosure keeps full evidence, technical item keys, internal snapshot history, fingerprints, and optional details out of the default decision view. This reduces accidental shoulder-surfing and cognitive overload, but it is presentation—not access control. The data remains available through the same browser flow and in backend storage.

## Same-Device Limitations

The handoff UI asks users to pass the device during Clarify, Check understanding, and Confirm, locks the completed step, and does not display the previous participant’s hidden selection. There is no authentication, identity verification, separate user account, secure device boundary, or protection from browser/devtools or process-memory access. Do not describe this milestone as private independent voting, proof of comprehension, or verified consent.

An explicit **Continue unresolved** action records that an issue remains open; it is not consent to the other participant’s position. Optional details can remain not discussed. Neither advancing a screen nor viewing a receipt silently changes agreement meaning.

Separate confirmations bind server-owned participant role, current version, completion of that participant’s applicable checks, acknowledgments, language, and timestamp. They record a stated selection; they are not proof that the participant understood, freely consented, or signed anything.

## Receipt and Integrity

A clarity receipt is an immutable durable snapshot. It preserves aligned and unresolved meaning, one-sided and not-discussed terms, not-applicable proposals, evidence, clarification history, understanding-check completion status, and separate confirmation timestamps. Its SHA-256 integrity hash is unchanged across storage reloads and can reveal payload changes when recomputed. It does not prove comprehension, consent, identity, authorship, time from a trusted authority, non-repudiation, or legal validity; it is not a digital signature.

Keep secrets and database credentials only in ignored backend `.env` files; never expose them through `NEXT_PUBLIC_*`. Use explicit CORS origins. Role-bound access, invitation exchange, QR joining, participant authorization, and synchronization remain P1B. MeaningSync does not provide legal advice, and a clarity receipt is not a legally enforceable contract.
