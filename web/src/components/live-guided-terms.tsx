import type {
  AgreementTerm,
  MeaningState,
  NotApplicableProposal,
  PartyRole,
  LanguageCode,
} from "@/lib/api";
import { roleLabel } from "@/lib/flow-presentation";

const stateLabels: Record<MeaningState, string> = {
  aligned: "Both said the same thing",
  conflicting: "The meanings are different",
  stated_by_one: "Only one person mentioned this",
  not_discussed: "Not discussed",
};

export function EvidenceDisclosure({ term }: { term: AgreementTerm }) {
  if (!term.evidence.length) return null;
  return (
    <details className="guided-evidence">
      <summary>See original statements</summary>
      <ul>
        {term.evidence.map((reference) => (
          <li key={`${reference.source}-${reference.reference_id}`}>
            <span>{roleLabel(reference.role)}</span>
            {reference.input_source === "audio_transcript" ? <small>Audio transcript{reference.corrected_text ? " · corrected by participant" : ""}</small> : null}
            <q>{reference.original_text}</q>
            {reference.corrected_text && reference.raw_transcript ? <details><summary>Original machine transcript</summary><q>{reference.raw_transcript}</q></details> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function GuidedTermRow({
  term,
  showState = false,
  proposal,
  language = "en",
}: {
  term: AgreementTerm;
  showState?: boolean;
  proposal?: NotApplicableProposal;
  language?: LanguageCode;
}) {
  const localized = term.localizations?.[language];
  return (
    <article className="guided-term-row" data-item={term.analysis_item_key}>
      <div>
        <p lang={language}>{localized?.label ?? term.label}</p>
        <strong lang={language}>{localized?.summary ?? term.summary}</strong>
        {showState && <span className={`plain-state ${term.state}`}>{stateLabels[term.state]}</span>}
      </div>
      <EvidenceDisclosure term={term} />
      {proposal && <NotApplicableNote proposal={proposal} />}
    </article>
  );
}

export function GuidedTermList({
  terms,
  emptyMessage = "Nothing to show here.",
  showState = false,
  proposals = [],
  language = "en",
}: {
  terms: AgreementTerm[];
  emptyMessage?: string;
  showState?: boolean;
  proposals?: NotApplicableProposal[];
  language?: LanguageCode;
}) {
  if (!terms.length) return <p className="guided-empty">{emptyMessage}</p>;
  return (
    <div className="guided-term-list">
      {terms.map((term) => (
        <GuidedTermRow
          key={term.analysis_item_key}
          term={term}
          showState={showState}
          proposal={proposals.find(
            (item) => item.item_key === term.analysis_item_key,
          )}
          language={language}
        />
      ))}
    </div>
  );
}

function NotApplicableNote({
  proposal,
}: {
  proposal: NotApplicableProposal;
}) {
  const both = proposal.proposed_by.length === 2;
  const proposers = proposal.proposed_by
    .map((party) => roleLabel(party))
    .join(" and ");
  const waitingFor = (["hirer", "worker"] as PartyRole[]).find(
    (party) => !proposal.proposed_by.includes(party),
  );
  return (
    <div className={`guided-na-note ${both ? "mutual" : "pending"}`}>
      <strong>{proposal.label} marked not applicable</strong>
      <span>{proposal.summary}</span>
      <span>
        {both
          ? `${proposers} both marked this not applicable.`
          : `${proposers} marked this not applicable. It is still pending for ${waitingFor ? roleLabel(waitingFor) : "the other person"}.`}
      </span>
    </div>
  );
}

export function ParticipantPositions({ term, language = "en" }: { term: AgreementTerm; language?: LanguageCode }) {
  if (!term.participant_positions.length) return null;
  return (
    <div className="guided-positions">
      {term.participant_positions.map((position) => (
        <div key={position.participant_id}>
          <span>{roleLabel(position.role)}</span>
          <p lang={language}>{term.localizations?.[language]?.participant_positions.find((item) => item.participant_id === position.participant_id)?.summary ?? position.summary}</p>
        </div>
      ))}
    </div>
  );
}
