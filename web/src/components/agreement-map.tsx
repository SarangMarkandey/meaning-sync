import type { AgreementTerm, LanguageCode, MeaningState } from "@/lib/api";
import { roleLabel } from "@/lib/flow-presentation";

const languageNames = {
  en: "English",
  hi: "Hindi",
};

const stateLabels: Record<MeaningState, string> = {
  aligned: "Aligned",
  conflicting: "Conflicting",
  stated_by_one: "Stated by one person",
  not_discussed: "Not discussed",
};

const sections: Array<{
  states: MeaningState[];
  style: "confirmed" | "conflict" | "missing";
  title: string;
  description: string;
}> = [
  {
    states: ["aligned"],
    style: "confirmed",
    title: "What matches",
    description: "Both participants explicitly support the same meaning",
  },
  {
    states: ["conflicting", "stated_by_one"],
    style: "conflict",
    title: "Needs a decision",
    description: "Meanings conflict or only one participant stated the term",
  },
  {
    states: ["not_discussed"],
    style: "missing",
    title: "Not discussed",
    description: "Neither participant stated this topic",
  },
];

export function AgreementMap({
  terms,
  roleMode = "demo",
  onDiscussMissing,
  language = "en",
}: {
  terms: AgreementTerm[];
  roleMode?: "live" | "demo";
  onDiscussMissing?: (itemKey: string) => void;
  language?: LanguageCode;
}) {
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
        const matchingTerms = terms.filter((term) =>
          section.states.includes(term.state),
        );
        return (
          <section className={`map-section ${section.style}`} key={section.title}>
            <header className="section-heading">
              <span className="status-mark" aria-hidden="true" />
              <div>
                <h3>{section.title}</h3>
                <p>{section.description}</p>
              </div>
              <span className="term-count">{matchingTerms.length}</span>
            </header>
            <div className="term-list">
              {matchingTerms.length ? (
                matchingTerms.map((term) => {
                  const localized = term.localizations?.[language];
                  return (
                  <article className="term-card" key={term.id}>
                    <div className="term-title-row">
                      <p className="term-label" lang={language}>{localized?.label ?? term.label}</p>
                      <span className={`meaning-state ${term.state}`}>
                        {stateLabels[term.state]}
                      </span>
                    </div>
                    <p className="term-value" lang={language}>{localized?.summary ?? term.summary}</p>
                    {term.participant_positions.length > 0 &&
                      term.state !== "aligned" && (
                        <div className="position-list">
                          {term.participant_positions.map((position) => (
                            <div key={position.participant_id}>
                              <span>{roleLabel(position.role, roleMode)}</span>
                              <p lang={language}>{localized?.participant_positions.find((item) => item.participant_id === position.participant_id)?.summary ?? position.summary}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    {term.evidence.length > 0 && (
                      <details className="evidence">
                        <summary>View conversation evidence ({term.evidence.length})</summary>
                        <ul>
                          {term.evidence.map((reference) => (
                            <li
                              key={`${reference.source}-${reference.reference_id}`}
                            >
                              <span>
                                {reference.speaker_name}
                                {reference.input_source === "audio_transcript" ? " · audio transcript" : " · original"} {" · "}
                                {languageNames[reference.original_language]}
                                {reference.order ? ` · message ${reference.order}` : ""}
                              </span>
                              <q>{reference.original_text}</q>
                              {reference.corrected_text && reference.raw_transcript ? (
                                <details className="raw-transcript">
                                  <summary>Original machine transcript</summary>
                                  <q>{reference.raw_transcript}</q>
                                </details>
                              ) : null}
                              {reference.timestamp && (
                                <time dateTime={reference.timestamp}>
                                  {new Date(reference.timestamp).toLocaleString()}
                                </time>
                              )}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {term.state === "not_discussed" && onDiscussMissing ? (
                      <button className="text-action" type="button" onClick={() => onDiscussMissing(term.analysis_item_key)}>
                        Discuss this
                      </button>
                    ) : null}
                  </article>
                  );
                })
              ) : (
                <p className="section-empty">No terms in this section.</p>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
