"use client";

import { useState } from "react";

import { AgreementMap } from "@/components/agreement-map";
import {
  api,
  type ClarityReceipt,
  type ClarificationResult,
  type PartyRole,
  type SessionView,
} from "@/lib/api";

type Screen =
  | "landing"
  | "consent"
  | "evidence"
  | "map"
  | "clarification"
  | "receipt";

const roleNames: Record<PartyRole, string> = {
  hirer: "Asha · Hirer",
  worker: "Ravi · Electrician",
};

const defaultTeachback =
  "The fan and two switches will be repaired today for ₹1,200 labour. Parts remain as shown in the map.";

export default function Home() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [session, setSession] = useState<SessionView | null>(null);
  const [activeParty, setActiveParty] = useState<PartyRole>("hirer");
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [clarification, setClarification] =
    useState<ClarificationResult | null>(null);
  const [confirmedParties, setConfirmedParties] = useState<PartyRole[]>([]);
  const [receipt, setReceipt] = useState<ClarityReceipt | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  const startDemo = () =>
    perform(async () => {
      const created = await api.createDemo();
      setSession(created);
      setScreen("consent");
    });

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
        <button className="brand" onClick={() => setScreen("landing")}>
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </button>
        {screen !== "landing" && (
          <span className="demo-pill">Demo mode</span>
        )}
      </nav>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      {loading && (
        <div className="loading-bar" role="status">
          <span />
          Checking shared meaning…
        </div>
      )}

      {screen === "landing" && (
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Clarity before commitment</p>
            <h1>Make sure both sides mean the same thing.</h1>
            <p className="hero-text">
              MeaningSync turns a spoken service agreement into a clear,
              evidence-linked view of what matches, what conflicts, and what was
              never discussed.
            </p>
            <div className="hero-actions">
              <button className="button primary" onClick={startDemo} disabled={loading}>
                Try Demo <span>→</span>
              </button>
              <button className="button secondary" disabled>
                Start Live Session
                <small>Next milestone</small>
              </button>
            </div>
          </div>
          <div className="meaning-preview" aria-label="Agreement map preview">
            <div className="preview-top">
              <span>Shared meaning</span>
              <strong>4 of 7 clear</strong>
            </div>
            <div className="preview-ring"><span>57%</span></div>
            <div className="preview-row good"><i />Scope & price <b>Aligned</b></div>
            <div className="preview-row warn"><i />Replacement parts <b>Different</b></div>
            <div className="preview-row mute"><i />Payment timing <b>Not said</b></div>
          </div>
        </section>
      )}

      {screen === "consent" && session && (
        <FlowPage step="01" title="Start with clear consent" subtitle="Each person agrees separately before the prepared conversation is reviewed.">
          <div className="consent-grid">
            {(["hirer", "worker"] as PartyRole[]).map((party) => {
              const accepted = session.consent[party] === "accepted";
              return (
                <article className={`consent-card ${accepted ? "accepted" : ""}`} key={party}>
                  <div className="avatar">{party === "hirer" ? "A" : "R"}</div>
                  <div><h3>{roleNames[party]}</h3><p>I agree to use this prepared conversation for the MeaningSync demo.</p></div>
                  <button onClick={() => acceptConsent(party)} disabled={accepted || loading}>
                    {accepted ? "Consent given ✓" : "Give consent"}
                  </button>
                </article>
              );
            })}
          </div>
          <div className="privacy-note"><strong>Demo safeguard</strong><span>No microphone, audio recording, identity check, or AI call is used.</span></div>
          <button className="button primary full" disabled={!bothConsented} onClick={() => setScreen("evidence")}>Review conversation <span>→</span></button>
        </FlowPage>
      )}

      {screen === "evidence" && session && (
        <FlowPage step="02" title="Conversation evidence" subtitle="A prepared Hindi–English electrician conversation. Every finding will point back here.">
          {session.transcript.length ? (
            <div className="transcript">
              {session.transcript.map((turn, index) => (
                <article className="turn" key={turn.id}>
                  <span className="turn-number">{String(index + 1).padStart(2, "0")}</span>
                  <div className={`avatar small ${turn.speaker}`}>{turn.speaker_name[0]}</div>
                  <div><header><strong>{turn.speaker_name}</strong><span>{turn.speaker === "hirer" ? "Hirer" : "Electrician"} · {turn.language}</span></header><p>{turn.text}</p></div>
                </article>
              ))}
            </div>
          ) : <div className="empty-state">The prepared conversation is empty.</div>}
          <button className="button primary full" onClick={analyzeConversation} disabled={loading}>Build agreement map <span>→</span></button>
        </FlowPage>
      )}

      {screen === "map" && session && (
        <FlowPage step="03" title="Agreement map" subtitle="The deterministic demo separates shared meaning from conflicts and gaps.">
          <AgreementMap terms={session.terms} />
          <button className="button primary full" onClick={openClarification} disabled={loading}>Clarify replacement parts <span>→</span></button>
        </FlowPage>
      )}

      {screen === "clarification" && session && (
        <FlowPage step="04" title="Clarify separately" subtitle="One question, answered privately by each person. The first answer stays hidden until the second is submitted.">
          {session.clarification_questions.length ? (
            <div className="clarify-card">
              <div className="party-switch"><span>Answering as</span><strong>{roleNames[activeParty]}</strong></div>
              <h3>{session.clarification_questions[0].prompt}</h3>
              {!clarification?.revealed && session.clarification_questions[0].options.map((option) => (
                <label className={`answer-option ${selectedAnswer === option ? "selected" : ""}`} key={option}>
                  <input type="radio" name="answer" value={option} checked={selectedAnswer === option} onChange={() => setSelectedAnswer(option)} />
                  <span>{option}</span><i />
                </label>
              ))}
              {!clarification?.revealed && <button className="button primary full" onClick={submitAnswer} disabled={!selectedAnswer || loading}>Submit private answer</button>}
              {clarification && !clarification.revealed && <div className="hidden-answer"><span>🔒</span><div><strong>Asha’s answer is safely hidden</strong><p>Now pass the device to Ravi. Neither answer is revealed yet.</p></div></div>}
              {clarification?.revealed && (
                <div className="reveal-panel">
                  <p className="eyebrow">Both answers revealed</p>
                  <div className="answer-pair">{clarification.answers.map((answer) => <div key={answer.party}><span>{roleNames[answer.party]}</span><strong>{answer.answer}</strong></div>)}</div>
                  <div className={clarification.resolved ? "resolution good" : "resolution warn"}><strong>{clarification.resolved ? "Meaning aligned" : "Still needs clarification"}</strong><p>{clarification.resolved ? "Both parties selected the same materials policy." : "The receipt will preserve this unresolved difference."}</p></div>
                  <div className="teachback">
                    <span>Shared teach-back</span>
                    <p>{defaultTeachback}</p>
                  </div>
                  <div className="confirmation-actions">
                    {(["hirer", "worker"] as PartyRole[]).map((party) => {
                      const confirmed = confirmedParties.includes(party);
                      return (
                        <button key={party} onClick={() => confirmTeachback(party)} disabled={confirmed || loading}>
                          <span>{roleNames[party]}</span>
                          <strong>{confirmed ? "Confirmed ✓" : "Confirm my understanding"}</strong>
                        </button>
                      );
                    })}
                  </div>
                  {confirmedParties.length === 2 && <button className="button primary full" onClick={finishDemo} disabled={loading}>Create clarity receipt <span>→</span></button>}
                </div>
              )}
            </div>
          ) : <div className="empty-state">No clarification question is available.</div>}
        </FlowPage>
      )}

      {screen === "receipt" && receipt && (
        <FlowPage step="05" title="Clarity receipt" subtitle="A faithful snapshot of what matched, what did not, and what remains unsaid.">
          <article className="receipt">
            <header><div className="receipt-mark">✓</div><div><p>Session complete</p><h2>{receipt.title}</h2><span>Created {new Date(receipt.completed_at).toLocaleString()}</span></div></header>
            <AgreementMap terms={receipt.terms} />
            <div className="confirmed-by"><span>Confirmed separately by</span>{receipt.confirmations.map((confirmation) => <strong key={confirmation.party}>{roleNames[confirmation.party]} ✓</strong>)}</div>
            <footer>{receipt.disclaimer}</footer>
          </article>
          <button className="button secondary full" onClick={() => window.location.reload()}>Start over</button>
        </FlowPage>
      )}
    </main>
  );
}

function FlowPage({ step, title, subtitle, children }: { step: string; title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="flow-page">
      <header className="flow-heading"><span>{step} / 05</span><h1>{title}</h1><p>{subtitle}</p></header>
      {children}
    </section>
  );
}
