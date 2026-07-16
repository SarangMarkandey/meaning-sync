"use client";

import Link from "next/link";
import { FormEvent, useId, useState } from "react";

import { AgreementMap } from "@/components/agreement-map";
import {
  api,
  MeaningSyncApiError,
  type AgreementAnalysisRequest,
  type AgreementAnalysisResponse,
  type AnalysisMessage,
  type LanguageCode,
  type PartyRole,
} from "@/lib/api";

const roleNames: Record<PartyRole, string> = {
  hirer: "Homeowner",
  worker: "Electrician",
};

const sampleStatements: Array<{ speaker: PartyRole; text: string }> = [
  {
    speaker: "hirer",
    text: "I will pay ₹1,200 for repairing the fan and two switches, including replacement parts.",
  },
  {
    speaker: "worker",
    text: "₹1,200 covers my labour. Replacement parts are separate.",
  },
  { speaker: "hirer", text: "The work can start today." },
  { speaker: "worker", text: "Yes, I can start today." },
];

type Draft = { speaker: PartyRole; text: string };

const emptyDraft: Draft = { speaker: "hirer", text: "" };

export function LiveExperience({
  participantLanguages,
}: {
  participantLanguages: Record<PartyRole, LanguageCode>;
}) {
  const reactId = useId();
  const sessionId = `live-${reactId.replaceAll(":", "")}`;
  const speakerControlId = `speaker-${reactId.replaceAll(":", "")}`;
  const statementControlId = `statement-${reactId.replaceAll(":", "")}`;
  const [messages, setMessages] = useState<AnalysisMessage[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [result, setResult] = useState<AgreementAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<MeaningSyncApiError | null>(null);

  const contributors = new Set(messages.map((message) => message.speaker_id));
  const canAnalyze =
    messages.length >= 2 &&
    contributors.has("hirer") &&
    contributors.has("worker") &&
    messages.every((message) => message.original_text.trim().length >= 2);

  const resetAnalysis = () => {
    setResult(null);
    setError(null);
  };

  const saveStatement = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.text.trim();
    if (text.length < 2) return;

    if (editingId) {
      setMessages((current) =>
        current.map((message) =>
          message.message_id === editingId
            ? {
                ...message,
                speaker_id: draft.speaker,
                original_text: text,
                original_language: participantLanguages[draft.speaker],
              }
            : message,
        ),
      );
    } else {
      const order = messages.reduce(
        (highest, message) => Math.max(highest, message.order),
        0,
      ) + 1;
      setMessages((current) => [
        ...current,
        {
          message_id: `message-${order}`,
          speaker_id: draft.speaker,
          original_text: text,
          original_language: participantLanguages[draft.speaker],
          order,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
    setDraft(emptyDraft);
    setEditingId(null);
    resetAnalysis();
  };

  const editStatement = (message: AnalysisMessage) => {
    setEditingId(message.message_id);
    setDraft({
      speaker: message.speaker_id as PartyRole,
      text: message.original_text,
    });
    setError(null);
  };

  const removeStatement = (messageId: string) => {
    setMessages((current) =>
      current.filter((message) => message.message_id !== messageId),
    );
    if (editingId === messageId) {
      setEditingId(null);
      setDraft(emptyDraft);
    }
    resetAnalysis();
  };

  const loadSample = () => {
    const startedAt = Date.now();
    setMessages(
      sampleStatements.map((statement, index) => ({
        message_id: `message-${index + 1}`,
        speaker_id: statement.speaker,
        original_text: statement.text,
        original_language: participantLanguages[statement.speaker],
        order: index + 1,
        timestamp: new Date(startedAt + index * 1000).toISOString(),
      })),
    );
    setEditingId(null);
    setDraft(emptyDraft);
    resetAnalysis();
  };

  const analyzeAgreement = async () => {
    if (!canAnalyze) return;
    setLoading(true);
    setError(null);
    try {
      const submission: AgreementAnalysisRequest = {
        session_id: sessionId,
        mode: "live",
        participants: [
          { id: "hirer", role: "hirer", language: participantLanguages.hirer },
          { id: "worker", role: "worker", language: participantLanguages.worker },
        ],
        messages,
      };
      setResult(await api.analyzeAgreement(submission));
    } catch (caught) {
      setResult(null);
      setError(
        caught instanceof MeaningSyncApiError
          ? caught
          : new MeaningSyncApiError("Live analysis could not be completed."),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <nav className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </Link>
        <span className="demo-pill">Live text preview</span>
      </nav>

      <section className="live-page">
        <header className="live-heading">
          <div>
            <p className="eyebrow">English agreement analysis</p>
            <h1>Build the conversation evidence</h1>
            <p>
              Add each person’s statements in order. MeaningSync analyzes only
              the text you submit and links every finding back to it.
            </p>
          </div>
          <div className="text-only-badge">
            <strong>Text only</strong>
            <span>No audio is recorded</span>
          </div>
        </header>

        <div className="live-workspace">
          <section className="statement-composer" aria-labelledby="composer-title">
            <div className="workspace-heading">
              <div>
                <span>Conversation input</span>
                <h2 id="composer-title">
                  {editingId ? "Edit statement" : "Add a statement"}
                </h2>
              </div>
              <button type="button" onClick={loadSample} disabled={loading}>
                Load sample conversation
              </button>
            </div>

            <form onSubmit={saveStatement}>
              <div className="composer-fields">
                <div className="composer-field">
                  <label htmlFor={speakerControlId}>Speaker</label>
                  <select
                    id={speakerControlId}
                    value={draft.speaker}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        speaker: event.target.value as PartyRole,
                      }))
                    }
                  >
                    <option value="hirer">Homeowner</option>
                    <option value="worker">Electrician</option>
                  </select>
                </div>
                <div className="composer-field">
                  <label htmlFor={statementControlId}>Original statement</label>
                  <textarea
                    id={statementControlId}
                    value={draft.text}
                    maxLength={2000}
                    rows={4}
                    placeholder="Enter what this person said…"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        text: event.target.value,
                      }))
                    }
                  />
                </div>
              </div>
              <div className="composer-actions">
                {editingId && (
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => {
                      setEditingId(null);
                      setDraft(emptyDraft);
                    }}
                  >
                    Cancel edit
                  </button>
                )}
                <button
                  className="button primary"
                  type="submit"
                  disabled={draft.text.trim().length < 2 || loading}
                >
                  {editingId ? "Save changes" : "Add statement"}
                </button>
              </div>
            </form>
          </section>

          <section className="conversation-panel" aria-labelledby="evidence-title">
            <div className="workspace-heading">
              <div>
                <span>Chronological evidence</span>
                <h2 id="evidence-title">Conversation</h2>
              </div>
              <strong>{messages.length} statements</strong>
            </div>

            {messages.length ? (
              <ol className="live-transcript">
                {messages.map((message) => {
                  const party = message.speaker_id as PartyRole;
                  return (
                    <li key={message.message_id}>
                      <div className={`message-index ${party}`}>
                        {String(message.order).padStart(2, "0")}
                      </div>
                      <article>
                        <header>
                          <div>
                            <strong>{roleNames[party]}</strong>
                            <span>
                              {message.message_id} · Original English
                            </span>
                          </div>
                          <div className="message-actions">
                            <button
                              type="button"
                              onClick={() => editStatement(message)}
                              aria-label={`Edit statement ${message.order}`}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => removeStatement(message.message_id)}
                              aria-label={`Remove statement ${message.order}`}
                            >
                              Remove
                            </button>
                          </div>
                        </header>
                        <p>{message.original_text}</p>
                      </article>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <div className="empty-state">
                Add one meaningful statement from each participant, or load the
                sample conversation.
              </div>
            )}

            <div className="analysis-gate" role="status">
              <div>
                <span className={contributors.has("hirer") ? "ready" : ""}>
                  Homeowner {contributors.has("hirer") ? "ready ✓" : "needed"}
                </span>
                <span className={contributors.has("worker") ? "ready" : ""}>
                  Electrician {contributors.has("worker") ? "ready ✓" : "needed"}
                </span>
              </div>
              <button
                className="button primary"
                type="button"
                disabled={!canAnalyze || loading}
                onClick={() => void analyzeAgreement()}
                aria-label={loading ? "Analyzing agreement" : "Analyze Agreement"}
              >
                {loading ? "Analyzing agreement…" : "Analyze Agreement"}
                {!loading && <span>→</span>}
              </button>
            </div>
          </section>
        </div>

        {error && (
          <section className="analysis-error" role="alert">
            <div>
              <span>Analysis unavailable</span>
              <h2>We could not build the agreement map.</h2>
              <p>{error.message}</p>
            </div>
            {error.retryable && (
              <button
                className="button secondary"
                type="button"
                onClick={() => void analyzeAgreement()}
                disabled={loading}
              >
                Try again
              </button>
            )}
          </section>
        )}

        {result && (
          <section className="analysis-results" aria-labelledby="results-title">
            <header>
              <span>
                {result.status === "partial"
                  ? "Partial analysis"
                  : "Validated analysis"}
              </span>
              <h2 id="results-title">Agreement map</h2>
              <p>
                Confirmed meaning requires evidence from both participants.
                One-sided statements remain open for clarification.
              </p>
            </header>
            {result.warnings.map((warning) => (
              <article
                className="analysis-warning"
                role="status"
                key={warning.code}
              >
                <strong>Clarification unavailable</strong>
                <p>{warning.message}</p>
              </article>
            ))}
            {result.primary_clarification && (
              <article className="primary-clarification">
                <span>Most useful clarification</span>
                <h3>{result.primary_clarification.prompt}</h3>
                <p>
                  Ask both participants this neutral question before relying on
                  the shared understanding.
                </p>
              </article>
            )}
            <AgreementMap terms={result.terms} />
          </section>
        )}

        <footer className="live-disclaimer">
          MeaningSync helps compare stated meaning. It does not provide legal advice
          or create a legal contract.
        </footer>
      </section>
    </main>
  );
}
