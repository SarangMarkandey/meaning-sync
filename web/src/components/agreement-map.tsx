import type { AgreementTerm, TermStatus } from "@/lib/api";

const sections: Array<{
  status: TermStatus;
  title: string;
  description: string;
}> = [
  {
    status: "confirmed",
    title: "Confirmed",
    description: "Both sides said the same thing",
  },
  {
    status: "conflict",
    title: "Needs clarification",
    description: "The conversation points in different directions",
  },
  {
    status: "missing",
    title: "Not discussed",
    description: "No shared meaning was stated yet",
  },
];

export function AgreementMap({ terms }: { terms: AgreementTerm[] }) {
  if (!terms.length) {
    return (
      <div className="empty-state" role="status">
        No agreement terms are available yet.
      </div>
    );
  }

  return (
    <div className="map-sections">
      {sections.map((section) => {
        const matchingTerms = terms.filter(
          (term) => term.status === section.status,
        );
        return (
          <section className={`map-section ${section.status}`} key={section.status}>
            <header className="section-heading">
              <span className="status-mark" aria-hidden="true" />
              <div>
                <h3>{section.title}</h3>
                <p>{section.description}</p>
              </div>
              <span className="term-count">{matchingTerms.length}</span>
            </header>
            <div className="term-list">
              {matchingTerms.map((term) => (
                <article className="term-card" key={term.id}>
                  <p className="term-label">{term.label}</p>
                  <p className="term-value">
                    {term.value ?? "No detail captured"}
                  </p>
                  {term.evidence.length > 0 && (
                    <details className="evidence">
                      <summary>
                        View evidence ({term.evidence.length})
                      </summary>
                      <ul>
                        {term.evidence.map((reference) => (
                          <li key={`${reference.source}-${reference.reference_id}`}>
                            <span>{reference.source}</span>
                            “{reference.excerpt}”
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
