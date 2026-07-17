import type {
  AgreementFacet,
  AgreementTerm,
  AgreementTopic,
  LiveGuidance,
  LiveSessionView,
  MeaningState,
  PartyRole,
} from "@/lib/api";

const timestamp = "2026-07-17T10:00:00Z";

function term({
  key,
  topic,
  facet,
  label,
  summary,
  state,
  speakers = [],
}: {
  key: string;
  topic: AgreementTopic;
  facet: AgreementFacet;
  label: string;
  summary: string;
  state: MeaningState;
  speakers?: PartyRole[];
}): AgreementTerm {
  const evidence = speakers.map((speaker, index) => ({
    source: "transcript" as const,
    reference_id: `${key}-${speaker}`,
    participant_id: speaker,
    role: speaker,
    speaker_name: speaker === "hirer" ? "Homeowner" : "Electrician",
    message_id: `${key}-${speaker}`,
    original_text:
      state === "stated_by_one"
        ? "I will repair the fan and two switches."
        : `${label}: ${summary}`,
    original_language: "en" as const,
    order: index + 1,
    timestamp,
  }));
  return {
    id: `term-${key}`,
    analysis_item_key: key,
    topic,
    facet,
    label,
    summary,
    state,
    participant_positions: speakers.map((speaker) => ({
      participant_id: speaker,
      role: speaker,
      summary:
        state === "stated_by_one"
          ? "The Electrician offered to repair the fan and two switches."
          : summary,
      evidence_message_ids: [`${key}-${speaker}`],
    })),
    participant_confirmations: {
      hirer:
        state === "aligned"
          ? "confirmed"
          : speakers.includes("hirer")
            ? "stated"
            : "not_stated",
      worker:
        state === "aligned"
          ? "confirmed"
          : speakers.includes("worker")
            ? "stated"
            : "not_stated",
    },
    evidence_message_ids: evidence.map((item) => item.reference_id),
    evidence,
    clarification_target: state === "stated_by_one" ? key : null,
  };
}

export const alignedTerms = [
  term({
    key: "price.amount",
    topic: "price",
    facet: "amount",
    label: "Labour price",
    summary: "The labour price is ₹1,200.",
    state: "aligned",
    speakers: ["hirer", "worker"],
  }),
  term({
    key: "materials.inclusion",
    topic: "materials",
    facet: "inclusion",
    label: "Replacement parts",
    summary: "Replacement parts cost extra after Homeowner approval.",
    state: "aligned",
    speakers: ["hirer", "worker"],
  }),
  term({
    key: "timing.start",
    topic: "timing",
    facet: "start",
    label: "Start time",
    summary: "The work starts today.",
    state: "aligned",
    speakers: ["hirer", "worker"],
  }),
  term({
    key: "responsibilities.assignment",
    topic: "responsibilities",
    facet: "assignment",
    label: "Parts approval",
    summary: "The Homeowner approves replacement parts before purchase.",
    state: "aligned",
    speakers: ["hirer", "worker"],
  }),
];

export const requiredScope = term({
  key: "scope.work",
  topic: "scope",
  facet: "work",
  label: "Work scope",
  summary: "Only the Electrician mentioned repairing the fan and two switches.",
  state: "stated_by_one",
  speakers: ["worker"],
});

export const optionalTerms = [
  term({ key: "completion.deadline", topic: "completion", facet: "deadline", label: "Completion time", summary: "A completion time was not discussed.", state: "not_discussed" }),
  term({ key: "payment.timing", topic: "payment", facet: "timing", label: "Payment timing", summary: "Payment timing was not discussed.", state: "not_discussed" }),
  term({ key: "warranty.coverage", topic: "warranty", facet: "coverage", label: "Warranty", summary: "A warranty was not discussed.", state: "not_discussed" }),
  term({ key: "cancellation.policy", topic: "cancellation", facet: "policy", label: "Cancellation", summary: "Cancellation was not discussed.", state: "not_discussed" }),
  term({ key: "additional_work.policy", topic: "additional_work", facet: "policy", label: "Additional work", summary: "How additional work is approved or priced was not discussed.", state: "not_discussed" }),
];

export const guidedV5Terms = [...alignedTerms, requiredScope, ...optionalTerms];

export function guidance(
  overrides: Partial<LiveGuidance> = {},
): LiveGuidance {
  return {
    user_stage: "clarify",
    headline: "Most of the conversation is clear",
    explanation: "Answer one scope question, then choose whether to add optional details.",
    primary_action: "submit_selection",
    primary_label: "Answer 1 question",
    secondary_action: "leave_unresolved",
    secondary_label: "Continue with this unresolved",
    required_issue_count: 1,
    optional_missing_count: 5,
    acting_participant: "hirer",
    active_question_id: "clarification-scope",
    active_clarification_id: "clarification-scope",
    target_item_key: "scope.work",
    required_item_keys: ["scope.work"],
    optional_item_keys: optionalTerms.map((item) => item.analysis_item_key),
    ...overrides,
  };
}

export function guidedV5Session(
  overrides: Partial<LiveSessionView> = {},
): LiveSessionView {
  const sessionGuidance = overrides.guidance ?? guidance();
  return {
    id: "live-guided-v5",
    stage: "needs_clarification",
    created_at: timestamp,
    participants: [
      { id: "hirer", role: "hirer", language: "en", display_name: "Homeowner" },
      { id: "worker", role: "worker", language: "en", display_name: "Electrician" },
    ],
    messages: [
      { message_id: "scope-worker", speaker_id: "worker", original_text: "I will repair the fan and two switches.", original_language: "en", order: 1, timestamp },
      { message_id: "price-hirer", speaker_id: "hirer", original_text: "The labour price is ₹1,200 and parts need my approval.", original_language: "en", order: 2, timestamp },
    ],
    agreement_versions: [
      {
        id: "version-5",
        version_number: 5,
        meaningful_version_number: 2,
        has_meaningful_change: true,
        semantic_fingerprint: "a".repeat(64),
        parent_version_id: "version-4",
        session_id: "live-guided-v5",
        mode: "live",
        created_at: timestamp,
        source_message_ids: ["scope-worker", "price-hirer"],
        terms: guidedV5Terms,
        unresolved_item_keys: [
          "scope.work",
          ...optionalTerms.map((item) => item.analysis_item_key),
        ],
        prompt_version: "agreement-analysis-v4",
        schema_version: "agreement-map-v2",
        model: "mock-model",
        analysis_status: "complete",
        warnings: [],
        primary_clarification: null,
        changes: [],
        not_applicable_proposals: [],
      },
    ],
    current_agreement_version_id: "version-5",
    questions: [
      {
        id: "clarification-scope",
        session_id: "live-guided-v5",
        agreement_version_id: "version-5",
        agreement_item_id: "scope.work",
        kind: "clarification",
        prompt: "Homeowner, do you also understand the work to be repairing the fan and two switches?",
        options: [
          { id: "scope-recorded", label: "Yes, the work is the fan and two switches", kind: "recorded_meaning" },
          { id: "scope-different", label: "No, the work scope is different", kind: "recorded_position" },
          { id: "scope-other", label: "Something else", kind: "other" },
          { id: "scope-unsure", label: "I’m not sure", kind: "unsure" },
        ],
        evidence_reference_ids: ["scope.work-worker"],
        addressed_participant_ids: ["hirer"],
        answered_participant_ids: [],
        responses_revealed: false,
        status: "pending",
        question_number: 1,
        question_count: 1,
        outcome: null,
      },
    ],
    confirmations: [],
    understanding_reviews: {},
    active_participant_id: "hirer",
    receipt_id: null,
    receipt_ready: false,
    clarification_attempt_limit: 3,
    ...overrides,
    guidance: sessionGuidance,
  };
}
