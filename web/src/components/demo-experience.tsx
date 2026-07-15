"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AgreementMap } from "@/components/agreement-map";
import {
  api,
  type ClarityReceipt,
  type ClarificationResult,
  type LanguageCode,
  type PartyRole,
  type SessionView,
} from "@/lib/api";

type Screen = "consent" | "evidence" | "map" | "clarification" | "receipt";

const roleNames: Record<PartyRole, string> = {
  hirer: "Homeowner",
  worker: "Electrician",
};

const defaultTeachback =
  "One fan and two switches will be repaired starting today for ₹1,200 labour. Replacement parts remain as shown in the map.";

export function DemoExperience({
  participantLanguages,
}: {
  participantLanguages: Record<PartyRole, LanguageCode>;
}) {
  const [screen, setScreen] = useState<Screen>("consent");
  const [session, setSession] = useState<SessionView | null>(null);
  const [activeParty, setActiveParty] = useState<PartyRole>("hirer");
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [clarification, setClarification] =
    useState<ClarificationResult | null>(null);
  const [confirmedParties, setConfirmedParties] = useState<PartyRole[]>([]);
  const [receipt, setReceipt] = useState<ClarityReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .createDemo(participantLanguages)
      .then((created) => {
        if (active) setSession(created);
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(
            caught instanceof Error ? caught.message : "The demo could not start.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [participantLanguages]);

  const perform = async (action: () => Promise<void>) => {
    setLoading(true);
    setError("");
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const acceptConsent = (party: PartyRole) => {
    if (!session) return;
    void perform(async () => {
      setSession(await api.submitConsent(session.id, party));
    });
  };

  const analyzeConversation = () => {
    if (!session) return;
    void perform(async () => {
      const analyzed = await api.analyze(session.id);
      setSession(analyzed);
      setScreen("map");
    });
  };

  const openClarification = () => {
    if (!session) return;
    void perform(async () => {
      setSession(await api.beginClarification(session.id));
      setScreen("clarification");
    });
  };

  const submitAnswer = () => {
    const question = session?.clarification_questions[0];
    if (!session || !question || !selectedAnswer) return;
    void perform(async () => {
      const result = await api.answerClarification(
        session.id,
        question.id,
        activeParty,
        selectedAnswer,
      );
      setClarification(result);
      setSelectedAnswer("");
      if (!result.revealed) setActiveParty("worker");
    });
  };

  const confirmTeachback = (party: PartyRole) => {
    if (!session) return;
    void perform(async () => {
      setSession(await api.confirm(session.id, party, defaultTeachback));
      setConfirmedParties((current) =>
        current.includes(party) ? current : [...current, party],
      );
    });
  };

  const finishDemo = () => {
    if (!session) return;
    void perform(async () => {
      setReceipt(await api.createReceipt(session.id));
      setScreen("receipt");
    });
  };

  const bothConsented = session
    ? Object.values(session.consent).every((status) => status === "accepted")
    : false;

  return (
    <main className="app-shell">
      <nav className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </Link>
        <span className="demo-pill">Demo mode</span>
      </nav>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <Link href="/demo/setup">Back to demo setup</Link>
        </div>
      )}
      {loading && (
        <div className="loading-bar" role="status">
          <span />
          Checking shared meaning…
        </div>
      )}

      {screen === "consent" && session && (
        <FlowPage
          step="01"
          title="Start with clear consent"
          subtitle="Each person agrees separately before the prepared conversation is reviewed."
        >
          <div className="consent-grid">
            {(["hirer", "worker"] as PartyRole[]).map((party) => {
              const accepted = session.consent[party] === "accepted";
              return (
                <article
                  className={`consent-card ${accepted ? "accepted" : ""}`}
                  key={party}
                >
                  <div className="avatar">{party === "hirer" ? "H" : "E"}</div>
                  <div>
                    <h3>{roleNames[party]}</h3>
                    <p>
                      I agree to use this prepared conversation for the
                      MeaningSync demo.
                    </p>
                  </div>
                  <button
                    onClick={() => acceptConsent(party)}
                    disabled={accepted || loading}
                  >
                    {accepted ? "Consent given ✓" : "Give consent"}
                  </button>
                </article>
              );
            })}
          </div>
          <div className="privacy-note">
            <strong>Demo safeguard</strong>
            <span>
              No microphone, audio recording, identity check, or AI call is used.
            </span>
          </div>
          <button
            className="button primary full"
            disabled={!bothConsented}
            onClick={() => setScreen("evidence")}
          >
            Review conversation <span>→</span>
          </button>
        </FlowPage>
      )}

      {screen === "evidence" && session && (
        <FlowPage
          step="02"
          title="Conversation evidence"
          subtitle="A prepared English homeowner–electrician conversation. Every finding points back to an original statement."
        >
          {session.transcript.length ? (
            <div className="transcript">
              {session.transcript.map((turn, index) => (
                <article className="turn" key={turn.id}>
                  <span className="turn-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className={`avatar small ${turn.speaker}`}>
                    {turn.speaker_name[0]}
                  </div>
                  <div>
                    <header>
                      <strong>{turn.speaker_name}</strong>
                      <span>
                        Original · {turn.original_language === "en" ? "English" : "Hindi"}
                      </span>
                    </header>
                    <p>{turn.original_text}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">The prepared conversation is empty.</div>
          )}
          <button
            className="button primary full"
            onClick={analyzeConversation}
            disabled={loading}
          >
            Build agreement map <span>→</span>
          </button>
        </FlowPage>
      )}

      {screen === "map" && session && (
        <FlowPage
          step="03"
          title="Agreement map"
          subtitle="The deterministic demo separates shared meaning from conflicts and gaps."
        >
          <AgreementMap terms={session.terms} />
          <button
            className="button primary full"
            onClick={openClarification}
            disabled={loading}
          >
            Clarify replacement parts <span>→</span>
          </button>
        </FlowPage>
      )}

      {screen === "clarification" && session && (
        <FlowPage
          step="04"
          title="Clarify separately"
          subtitle="One question, answered privately by each person. The first answer stays hidden until the second is submitted."
        >
          {session.clarification_questions.length ? (
            <div className="clarify-card">
              <div className="party-switch">
                <span>Answering as</span>
                <strong>{roleNames[activeParty]}</strong>
              </div>
              <h3>{session.clarification_questions[0].prompt}</h3>
              {!clarification?.revealed &&
                session.clarification_questions[0].options.map((option) => (
                  <label
                    className={`answer-option ${
                      selectedAnswer === option ? "selected" : ""
                    }`}
                    key={option}
                  >
                    <input
                      type="radio"
                      name="answer"
                      value={option}
                      checked={selectedAnswer === option}
                      onChange={() => setSelectedAnswer(option)}
                    />
                    <span>{option}</span>
                    <i />
                  </label>
                ))}
              {!clarification?.revealed && (
                <button
                  className="button primary full"
                  onClick={submitAnswer}
                  disabled={!selectedAnswer || loading}
                >
                  Submit private answer
                </button>
              )}
              {clarification && !clarification.revealed && (
                <div className="hidden-answer">
                  <span>🔒</span>
                  <div>
                    <strong>The homeowner’s answer is safely hidden</strong>
                    <p>
                      Now pass the device to the electrician. Neither answer is
                      revealed yet.
                    </p>
                  </div>
                </div>
              )}
              {clarification?.revealed && (
                <div className="reveal-panel">
                  <p className="eyebrow">Both answers revealed</p>
                  <div className="answer-pair">
                    {clarification.answers.map((answer) => (
                      <div key={answer.party}>
                        <span>{roleNames[answer.party]}</span>
                        <strong>{answer.answer}</strong>
                      </div>
                    ))}
                  </div>
                  <div
                    className={
                      clarification.resolved
                        ? "resolution good"
                        : "resolution warn"
                    }
                  >
                    <strong>
                      {clarification.resolved
                        ? "Meaning aligned"
                        : "Still needs clarification"}
                    </strong>
                    <p>
                      {clarification.resolved
                        ? "Both parties selected the same materials policy."
                        : "The receipt will preserve this unresolved difference."}
                    </p>
                  </div>
                  <div className="teachback">
                    <span>Shared teach-back</span>
                    <p>{defaultTeachback}</p>
                  </div>
                  <div className="confirmation-actions">
                    {(["hirer", "worker"] as PartyRole[]).map((party) => {
                      const confirmed = confirmedParties.includes(party);
                      return (
                        <button
                          key={party}
                          onClick={() => confirmTeachback(party)}
                          disabled={confirmed || loading}
                        >
                          <span>{roleNames[party]}</span>
                          <strong>
                            {confirmed
                              ? "Confirmed ✓"
                              : "Confirm my understanding"}
                          </strong>
                        </button>
                      );
                    })}
                  </div>
                  {confirmedParties.length === 2 && (
                    <button
                      className="button primary full"
                      onClick={finishDemo}
                      disabled={loading}
                    >
                      Create clarity receipt <span>→</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              No clarification question is available.
            </div>
          )}
        </FlowPage>
      )}

      {screen === "receipt" && receipt && (
        <FlowPage
          step="05"
          title="Clarity receipt"
          subtitle="A faithful snapshot of what matched, what did not, and what remains unsaid."
        >
          <article className="receipt">
            <header>
              <div className="receipt-mark">✓</div>
              <div>
                <p>Session complete</p>
                <h2>{receipt.title}</h2>
                <span>
                  Created {new Date(receipt.completed_at).toLocaleString()}
                </span>
              </div>
            </header>
            <AgreementMap terms={receipt.terms} />
            <div className="confirmed-by">
              <span>Confirmed separately by</span>
              {receipt.confirmations.map((confirmation) => (
                <strong key={confirmation.party}>
                  {roleNames[confirmation.party]} ✓
                </strong>
              ))}
            </div>
            <footer>{receipt.disclaimer}</footer>
          </article>
          <Link className="button secondary full" href="/demo/setup">
            Start over
          </Link>
        </FlowPage>
      )}
    </main>
  );
}

function FlowPage({
  step,
  title,
  subtitle,
  children,
}: {
  step: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flow-page">
      <header className="flow-heading">
        <span>{step} / 05</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </header>
      {children}
    </section>
  );
}
