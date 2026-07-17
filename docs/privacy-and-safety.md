# Privacy and Safety

## Data Flow

The browser sends speaker-attributed English statements to FastAPI through the typed JSON client. Only FastAPI can call OpenAI. Live agreement analysis uses the Responses API with `store=False`, strict Pydantic outputs, timeouts, and safe provider-error translation. Clarification and understanding choices are built and validated deterministically by FastAPI. The application must not put API keys, prompts, model reasoning, raw provider exceptions, or full conversations in routine logs.

Demo Mode is deterministic, key-free, and sends nothing to OpenAI. Normal automated tests use deterministic or mocked analyzers plus deterministic choice services and consume no API credits. A paid integration run remains explicitly opt-in and must never be used as a routine test.

## Process-Local Storage

Live sessions currently retain participants, messages, immutable agreement versions, questions, pending participant selections, independent-evidence status, confirmations, and clarity receipts only in FastAPI process memory. No database, durable backup, or cross-worker recovery exists. A page refresh can recover while the same backend process is alive; a restart or memory loss removes the session. The UI reports a missing session and directs users to start again rather than presenting cached browser state as authoritative.

A pending participant’s option, semantic value, selection ID, and `Something else` text remain in private process state until every addressed participant answers. For a two-person question, the first selection is not included in the public session response, page payload, query string, local storage, or client state available during the handoff to the second person. After both answer, the UI may reveal their positions neutrally. These controls reduce accidental disclosure in the ordinary flow; they are not a durable secrecy guarantee.

Progressive disclosure keeps full evidence, technical item keys, internal snapshot history, fingerprints, and optional details out of the default decision view. This reduces accidental shoulder-surfing and cognitive overload, but it is presentation—not access control. The data remains available to the same browser session and in FastAPI process memory.

## Same-Device Limitations

The handoff UI asks users to pass the device during Clarify, Check understanding, and Confirm, locks the completed step, and does not display the previous participant’s hidden selection. There is no authentication, identity verification, separate user account, secure device boundary, or protection from browser/devtools or process-memory access. Do not describe this milestone as private independent voting, proof of comprehension, or verified consent.

An explicit **Continue unresolved** action records that an issue remains open; it is not consent to the other participant’s position. Optional details can remain not discussed. Neither advancing a screen nor viewing a receipt silently changes agreement meaning.

Separate confirmations bind server-owned participant role, current version, completion of that participant’s applicable checks, acknowledgments, language, and timestamp. They record a stated selection; they are not proof that the participant understood, freely consented, or signed anything.

## Receipt and Integrity

A clarity receipt is an immutable in-memory snapshot. It preserves aligned and unresolved meaning, one-sided and not-discussed terms, not-applicable proposals, evidence, clarification history, understanding-check completion status, and separate confirmation timestamps. Its SHA-256 integrity hash is calculated over a canonical server-side payload and can reveal payload changes when recomputed. It does not prove comprehension, consent, identity, authorship, time from a trusted authority, non-repudiation, or legal validity; it is not a digital signature.

Keep secrets only in ignored local `.env` files and use explicit CORS origins. Durable encryption, retention/deletion controls, authenticated access, audit logging, and secure separate-device participation remain planned. MeaningSync does not provide legal advice, and a clarity receipt is not a legally enforceable contract.
