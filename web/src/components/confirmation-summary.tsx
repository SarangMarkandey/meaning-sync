import type { AgreementTerm, LanguageCode } from "@/lib/api";

export function ConfirmationSummary({ terms, language = "en" }: { terms: AgreementTerm[]; language?: LanguageCode }) {
  const agreed = terms.filter((term) => term.state === "aligned");
  const open = terms.filter((term) => term.state !== "aligned");
  return (
    <div className="confirm-summary">
      <section>
        <h2>Agreed</h2>
        {agreed.length ? agreed.map((term) => (
          <p key={term.analysis_item_key}><strong>{term.localizations?.[language]?.label ?? term.label}</strong><span>{term.localizations?.[language]?.summary ?? term.summary}</span></p>
        )) : <p>Nothing is recorded as agreed.</p>}
      </section>
      <section>
        <h2>Still open</h2>
        {open.length ? open.map((term) => (
          <p key={term.analysis_item_key}><strong>{term.localizations?.[language]?.label ?? term.label}</strong><span>{term.localizations?.[language]?.summary ?? term.summary}</span></p>
        )) : <p>Nothing remains open.</p>}
      </section>
    </div>
  );
}
