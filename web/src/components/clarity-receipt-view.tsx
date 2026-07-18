"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import { GuidedTermList } from "@/components/live-guided-terms";
import {
  api,
  MeaningSyncApiError,
  type AgreementTerm,
  type LiveClarityReceipt,
} from "@/lib/api";
import { roleLabel } from "@/lib/flow-presentation";
import { getAnyLiveAccess } from "@/lib/live-access";

const languageNames = { en: "English", hi: "Hindi" } as const;
const understandingStatusNames = {
  completed: "Completed",
  skipped: "No additional question was needed",
} as const;

export function ClarityReceiptView({ sessionId }: { sessionId: string }) {
  const [receipt, setReceipt] = useState<LiveClarityReceipt | null>(null);
  const [error, setError] = useState<MeaningSyncApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const loadReceipt = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReceipt(
        await api.getLiveReceipt(
          sessionId,
          getAnyLiveAccess(sessionId)?.token ?? "",
        ),
      );
    } catch (caught) {
      setError(
        caught instanceof MeaningSyncApiError
          ? caught
          : new MeaningSyncApiError("The clarity receipt could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    let current = true;
    void api
      .getLiveReceipt(sessionId, getAnyLiveAccess(sessionId)?.token ?? "")
      .then((next) => {
        if (!current) return;
        setReceipt(next);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!current) return;
        setError(
          caught instanceof MeaningSyncApiError
            ? caught
            : new MeaningSyncApiError("The clarity receipt could not be loaded."),
        );
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [sessionId]);

  if (loading) {
    return (
      <main className="app-shell">
        <LiveBrandBar />
        <div className="guided-loading" role="status"><span /> Loading clarity receipt…</div>
      </main>
    );
  }

  if (!receipt) {
    const early = error?.code === "receipt_not_ready";
    return (
      <main className="app-shell">
        <LiveBrandBar />
        <section className="session-recovery" role="alert">
          <span>{early ? "Receipt not ready" : "Receipt unavailable"}</span>
          <h1>{early ? "Both participants must confirm first." : "We could not open this receipt."}</h1>
          <p>{early ? "Return to the session to finish open decisions and each person’s separate confirmation." : error?.message}</p>
          <div>
            <Link className="button secondary" href={`/live/${encodeURIComponent(sessionId)}`}>Return to session</Link>
            {!early && <button className="button primary" type="button" onClick={() => void loadReceipt()}>Try again</button>}
          </div>
        </section>
      </main>
    );
  }

  const aligned = uniqueTerms(receipt.aligned_terms);
  const unresolved = uniqueTerms([
    ...receipt.unresolved_terms,
    ...receipt.one_sided_terms,
  ]);
  const notDiscussed = uniqueTerms(receipt.not_discussed_terms);
  const hasOpenPoints = receipt.status === "contains_unresolved_items";
  const allTerms = uniqueTerms([...aligned, ...unresolved, ...notDiscussed]);
  const termLabel = (itemKey: string) =>
    allTerms.find((term) => term.analysis_item_key === itemKey)?.label ??
    "Recorded detail";

  return (
    <main className="app-shell receipt-page">
      <LiveBrandBar trailing={<button className="button secondary print-action" type="button" onClick={() => window.print()}>Print / Save</button>} />
      <section className="guided-flow-page receipt-flow">
        <LiveProgress currentStage="receipt" explanation="The record is complete and ready to print or save." />
        <article className="live-receipt guided-receipt">
          <header>
            <div className="receipt-mark" aria-hidden="true">✓</div>
            <div>
              <p>MeaningSync Clarity Receipt — not a legal contract.</p>
              <h1>{hasOpenPoints ? "Both people confirmed this record contains unresolved points" : "Both people confirmed this understanding"}</h1>
              <span>Issued {new Date(receipt.issued_at).toLocaleString()}</span>
            </div>
          </header>

          {hasOpenPoints && (
            <section className="receipt-unresolved" role="alert">
              <strong>Some points remain unresolved</strong>
              <p>Both people reviewed this record. Open points are still open; they were not turned into agreement.</p>
            </section>
          )}

          <section className="receipt-meta" aria-label="Receipt summary">
            <div><span>Status</span><strong>{hasOpenPoints ? "Some points remain unresolved" : "All recorded meanings match"}</strong></div>
            <div><span>Participants</span><strong>{receipt.participants.map((participant) => roleLabel(participant.role)).join(" and ")}</strong></div>
            <div><span>Session currency</span><strong>{receipt.currency}</strong></div>
            <div><span>Session started</span><strong>{receipt.session_created_at ? new Date(receipt.session_created_at).toLocaleString() : "Not recorded"}</strong></div>
            <div><span>Receipt ID</span><strong>{receipt.id}</strong></div>
          </section>

          <section className="receipt-section">
            <header><span>Matching understanding</span><h2>What both people understood the same way</h2></header>
            <div className="receipt-term-group"><GuidedTermList terms={aligned} /></div>
          </section>

          {unresolved.length > 0 && (
            <section className="receipt-section receipt-open-terms">
              <header><span>Open points</span><h2>What remains unresolved</h2></header>
              <div className="receipt-term-group"><GuidedTermList terms={unresolved} showState /></div>
            </section>
          )}

          {(notDiscussed.length > 0 || receipt.not_applicable_terms.length > 0) && (
            <details className="receipt-section receipt-not-discussed">
              <summary><span>Not discussed</span><strong>Open details and not-applicable proposals</strong></summary>
              <GuidedTermList terms={notDiscussed} />
              {receipt.not_applicable_terms.length > 0 && (
                <div className="not-applicable-list">
                  <strong>Proposed not applicable</strong>
                  {receipt.not_applicable_terms.map((proposal) => (
                    <p key={proposal.item_key}><strong>{proposal.label}</strong> — {proposal.summary} Marked by {proposal.proposed_by.map((party) => roleLabel(party)).join(" and ")}.</p>
                  ))}
                </div>
              )}
            </details>
          )}

          <section className="receipt-section receipt-confirmations">
            <header><span>Separate review</span><h2>Each person confirmed separately</h2></header>
            <div>
              {receipt.confirmations.map((confirmation) => (
                <article key={confirmation.participant_id}>
                  <span className={`avatar small ${confirmation.participant_id === "worker" ? "worker" : ""}`}>{roleLabel(confirmation.participant_id)[0]}</span>
                  <p><strong>{roleLabel(confirmation.participant_id)}</strong><span>Confirmed {new Date(confirmation.confirmed_at).toLocaleString()}</span></p>
                  <i aria-label="Confirmed">✓</i>
                </article>
              ))}
            </div>
          </section>

          <section className="receipt-disclaimer"><p>{receipt.disclaimer}</p></section>

          <details className="receipt-advanced">
            <summary>Advanced details</summary>
            <div>
              <dl>
                <div><dt>Recorded version</dt><dd>{receipt.agreement_version_number}</dd></div>
                <div><dt>Integrity hash</dt><dd>{receipt.integrity_hash}</dd></div>
                <div><dt>Schema</dt><dd>{receipt.schema_version}</dd></div>
              </dl>
              <p>The hash can detect a change to this server-generated snapshot. It is not a digital signature and does not prove identity.</p>
              <section>
                <h2>Languages used</h2>
                <ul>{receipt.participants.map((participant) => <li key={participant.participant_id}>{roleLabel(participant.role)} — {languageNames[participant.language]}</li>)}</ul>
              </section>
              <section>
                <h2>Review status</h2>
                <ul>{receipt.understanding_status.map((item) => <li key={item.review_id}>{roleLabel(item.participant_id)} — {understandingStatusNames[item.result]}</li>)}</ul>
              </section>
              {receipt.clarification_history.length > 0 && (
                <section>
                  <h2>Decision history</h2>
                  <ul>{receipt.clarification_history.map((item) => <li key={item.clarification_id}>{termLabel(item.target_item_key)} — {item.status.replaceAll("_", " ")}</li>)}</ul>
                </section>
              )}
              {receipt.agreement_history.length > 0 && (
                <section>
                  <h2>Changes over time</h2>
                  <ul>{receipt.agreement_history.map((item, index) => <li key={`${item.item_key}-${index}`}>{item.label} — {item.resulting_meaning}</li>)}</ul>
                </section>
              )}
              {receipt.not_applicable_terms.length > 0 && (
                <section>
                  <h2>Not-applicable review</h2>
                  <ul>{receipt.not_applicable_terms.map((proposal) => <li key={proposal.item_key}>{proposal.label} — {proposal.summary} Marked by {proposal.proposed_by.map((party) => roleLabel(party)).join(" and ")}.</li>)}</ul>
                </section>
              )}
            </div>
          </details>
        </article>
        <div className="receipt-actions"><Link className="button secondary" href="/">Return home</Link><button className="button primary" type="button" onClick={() => window.print()}>Print / Save</button></div>
      </section>
    </main>
  );
}

function uniqueTerms(terms: AgreementTerm[]) {
  return terms.filter(
    (term, index) =>
      terms.findIndex(
        (candidate) => candidate.analysis_item_key === term.analysis_item_key,
      ) === index,
  );
}
