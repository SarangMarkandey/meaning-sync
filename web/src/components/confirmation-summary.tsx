import type { AgreementTerm } from "@/lib/api";

export function ConfirmationSummary({ terms }: { terms: AgreementTerm[] }) {
  const agreed = terms.filter((term) => term.state === "aligned");
  const open = terms.filter((term) => term.state !== "aligned");
  return (
    <div className="confirm-summary">
      <section>
        <h2>Agreed</h2>
        {agreed.length ? agreed.map((term) => (
          <p key={term.analysis_item_key}><strong>{term.label}</strong><span>{term.summary}</span></p>
        )) : <p>Nothing is recorded as agreed.</p>}
      </section>
      <section>
        <h2>Still open</h2>
        {open.length ? open.map((term) => (
          <p key={term.analysis_item_key}><strong>{term.label}</strong><span>{term.summary}</span></p>
        )) : <p>Nothing remains open.</p>}
      </section>
    </div>
  );
}
