export type SessionMode = "demo" | "live";
export type PartyRole = "hirer" | "worker";
export type LanguageCode = "en" | "hi";
export type ConsentStatus = "pending" | "accepted" | "declined";
export type MeaningState =
  | "aligned"
  | "conflicting"
  | "stated_by_one"
  | "not_discussed";
export type AgreementTopic =
  | "scope"
  | "price"
  | "materials"
  | "timing"
  | "completion"
  | "payment"
  | "responsibilities"
  | "warranty"
  | "cancellation"
  | "additional_work"
  | "other";
export type AgreementFacet =
  | "work"
  | "amount"
  | "inclusion"
  | "start"
  | "deadline"
  | "timing"
  | "assignment"
  | "coverage"
  | "policy"
  | "detail";
export type ParticipantTermStatus =
  | "confirmed"
  | "conflicting"
  | "stated"
  | "not_stated";
export type AnalysisErrorCode =
  | "invalid_request"
  | "configuration_error"
  | "invalid_api_key"
  | "rate_limited"
  | "timeout"
  | "connection_error"
  | "refused"
  | "invalid_model_output"
  | "provider_error";
export type AnalysisStatus = "complete" | "partial";
export type AnalysisWarningCode = "clarification_unavailable";
export type LiveSessionStage =
  | "conversation_draft"
  | "analyzing"
  | "needs_clarification"
  | "ready_for_review"
  | "awaiting_teachbacks"
  | "awaiting_confirmations"
  | "confirmed"
  | "receipt_issued";
export type ClarificationStatus =
  | "pending"
  | "answered"
  | "resolved"
  | "still_unresolved"
  | "left_unresolved";
export type ParticipantReviewStatus =
  | "not_started"
  | "reviewing"
  | "teachback_submitted"
  | "needs_clarification"
  | "ready_to_confirm"
  | "confirmed";
export type TeachbackComparisonState =
  | "matches"
  | "partially_matches"
  | "contradicts"
  | "insufficient";
export type ReceiptStatus = "fully_aligned" | "contains_unresolved_items";
export type LiveUserStage =
  | "conversation"
  | "clarify"
  | "review"
  | "confirm"
  | "receipt";
export type LiveGuidanceAction =
  | "answer_clarification"
  | "leave_unresolved"
  | "review_optional_details"
  | "review_final_understanding"
  | "submit_teachback"
  | "submit_confirmation"
  | "issue_receipt"
  | "view_receipt";
export type LiveErrorCode =
  | "invalid_request"
  | "invalid_state"
  | "stale_agreement_version"
  | "clarification_target_missing"
  | "clarification_limit_reached"
  | "participant_mismatch"
  | "teachback_incomplete"
  | "teachback_mismatch"
  | "confirmation_missing"
  | "confirmation_version_mismatch"
  | "receipt_not_ready"
  | "session_not_found";
export type SessionStage =
  | "created"
  | "consent_pending"
  | "discussion"
  | "analyzed"
  | "clarification"
  | "teachback"
  | "confirmation"
  | "completed";

export interface TranscriptTurn {
  id: string;
  session_id: string;
  participant_id: PartyRole;
  speaker: PartyRole;
  speaker_name: string;
  original_text: string;
  original_language: LanguageCode;
  order: number;
  timestamp: string;
  translations: Partial<Record<LanguageCode, string>>;
}

export interface EvidenceReference {
  source: "transcript" | "clarification";
  reference_id: string;
  participant_id: string;
  role: PartyRole;
  speaker_name: string;
  message_id: string | null;
  original_text: string;
  original_language: LanguageCode;
  order: number | null;
  timestamp: string | null;
}

export interface ParticipantPosition {
  participant_id: string;
  role: PartyRole;
  summary: string;
  evidence_message_ids: string[];
}

export interface AgreementTerm {
  id: string;
  analysis_item_key: string;
  topic: AgreementTopic;
  facet: AgreementFacet;
  label: string;
  summary: string;
  state: MeaningState;
  participant_positions: ParticipantPosition[];
  participant_confirmations: Record<PartyRole, ParticipantTermStatus>;
  evidence_message_ids: string[];
  evidence: EvidenceReference[];
  clarification_target: string | null;
}

export interface ClarificationQuestion {
  id: string;
  term_id: string;
  target_item_key: string;
  target: AgreementTopic;
  facet: AgreementFacet;
  evidence_message_ids: string[];
  prompt: string;
  options: string[];
}

export interface ClarificationAnswer {
  question_id: string;
  party: PartyRole;
  answer: string;
  meaning: "included" | "charged_separately";
  submitted_at: string;
}

export interface SessionParticipant {
  id: PartyRole;
  role: PartyRole;
  display_name?: string;
  language: LanguageCode;
  requested_display_language?: LanguageCode;
}

export interface PartyConfirmation {
  party: PartyRole;
  confirmed: boolean;
  teachback: string;
  submitted_at: string;
}

export interface SessionView {
  id: string;
  mode: SessionMode;
  stage: SessionStage;
  created_at: string;
  participants: SessionParticipant[];
  consent: Record<PartyRole, ConsentStatus>;
  transcript: TranscriptTurn[];
  terms: AgreementTerm[];
  clarification_questions: ClarificationQuestion[];
  confirmations: PartyConfirmation[];
}

export interface ClarificationResult {
  question: ClarificationQuestion;
  revealed: boolean;
  answers: ClarificationAnswer[];
  resolved: boolean;
  term: AgreementTerm | null;
}

export interface ClarityReceipt {
  session_id: string;
  title: string;
  disclaimer: string;
  terms: AgreementTerm[];
  confirmations: PartyConfirmation[];
  completed_at: string;
}

export interface AnalysisParticipant {
  id: string;
  role: PartyRole;
  language: LanguageCode;
}

export interface AnalysisMessage {
  message_id: string;
  speaker_id: string;
  original_text: string;
  original_language: LanguageCode;
  order: number;
  timestamp: string;
}

export interface AgreementAnalysisRequest {
  session_id: string;
  mode: "live";
  participants: [AnalysisParticipant, AnalysisParticipant];
  messages: AnalysisMessage[];
}

export interface AgreementAnalysisResponse {
  session_id: string;
  mode: SessionMode;
  prompt_version: string;
  model: string;
  status: AnalysisStatus;
  warnings: Array<{
    code: AnalysisWarningCode;
    message: string;
  }>;
  terms: AgreementTerm[];
  primary_clarification: ClarificationQuestion | null;
}

export interface AgreementVersion {
  id: string;
  version_number: number;
  meaningful_version_number: number;
  has_meaningful_change: boolean;
  semantic_fingerprint: string;
  parent_version_id: string | null;
  session_id: string;
  mode: "live";
  created_at: string;
  source_message_ids: string[];
  terms: AgreementTerm[];
  unresolved_item_keys: string[];
  prompt_version: string;
  schema_version: string;
  model: string;
  analysis_status: AnalysisStatus;
  warnings: Array<{ code: AnalysisWarningCode; message: string }>;
  primary_clarification: ClarificationQuestion | null;
  changes: AgreementVersionChange[];
  not_applicable_proposals: NotApplicableProposal[];
}

export interface LiveClarification {
  id: string;
  target_item_key: string;
  target_agreement_version_id: string;
  question: string;
  answer_options: string[];
  fingerprint: string;
  semantic_target: string;
  addressed_participant_ids: PartyRole[];
  answers_received_from: PartyRole[];
  responses_revealed: boolean;
  response_message_ids: Partial<Record<PartyRole, string>>;
  status: ClarificationStatus;
  created_at: string;
  resolved_at: string | null;
  resulting_agreement_version_id: string | null;
  attempt_number: number;
}

export interface TeachbackItemResult {
  analysis_item_key: string;
  state: TeachbackComparisonState;
  agreement_summary: string;
  feedback: string;
}

export interface LiveTeachback {
  id: string;
  participant_id: PartyRole;
  agreement_version_id: string;
  original_language: LanguageCode;
  covered_item_keys: string[];
  item_results: TeachbackItemResult[];
  overall_state: TeachbackComparisonState;
  missing_or_contradictory_summary: string | null;
  follow_up_question: string | null;
  acknowledged_unresolved_item_keys: string[];
  created_at: string;
}

export interface LiveConfirmation {
  id: string;
  participant_id: PartyRole;
  agreement_version_id: string;
  teachback_id: string;
  unresolved_item_acknowledgments: string[];
  confirmed_at: string;
  language: LanguageCode;
  request_id: string;
  invalidated_at: string | null;
}

export interface ParticipantReview {
  participant_id: PartyRole;
  status: ParticipantReviewStatus;
  agreement_version_id: string;
  teachback_id: string | null;
}

export interface AgreementVersionChange {
  item_key: string;
  label: string;
  previous_state: MeaningState | null;
  current_state: MeaningState | null;
  resulting_meaning: string;
  new_evidence_reference_ids: string[];
}

export interface LiveGuidance {
  user_stage: LiveUserStage;
  headline: string;
  explanation: string;
  primary_action: LiveGuidanceAction;
  primary_label: string;
  secondary_action: LiveGuidanceAction | null;
  secondary_label: string | null;
  required_issue_count: number;
  optional_missing_count: number;
  acting_participant: PartyRole | null;
  active_clarification_id: string | null;
  target_item_key: string | null;
  required_item_keys: string[];
  optional_item_keys: string[];
}

export interface LiveSessionView {
  id: string;
  stage: LiveSessionStage;
  created_at: string;
  participants: SessionParticipant[];
  messages: AnalysisMessage[];
  agreement_versions: AgreementVersion[];
  current_agreement_version_id: string | null;
  clarifications: LiveClarification[];
  teachbacks: LiveTeachback[];
  confirmations: LiveConfirmation[];
  reviews: Partial<Record<PartyRole, ParticipantReview>>;
  active_participant_id: PartyRole | null;
  receipt_id: string | null;
  receipt_ready: boolean;
  clarification_attempt_limit: number;
  guidance: LiveGuidance;
}

export interface ConfirmationStatusView {
  session_id: string;
  stage: LiveSessionStage;
  current_agreement_version_id: string | null;
  confirmations: LiveConfirmation[];
  receipt_ready: boolean;
}

export interface LiveSessionCreate {
  participants: [AnalysisParticipant, AnalysisParticipant];
  messages: AnalysisMessage[];
}

export interface ReceiptParticipant {
  participant_id: PartyRole;
  role: PartyRole;
  display_name: string;
  language: LanguageCode;
}

export interface ReceiptConfirmation {
  participant_id: PartyRole;
  confirmation_id: string;
  confirmed_at: string;
  language: LanguageCode;
}

export interface ReceiptClarificationSummary {
  clarification_id: string;
  target_item_key: string;
  target_agreement_version_id: string;
  resulting_agreement_version_id: string | null;
  response_message_ids: Partial<Record<PartyRole, string>>;
  status: ClarificationStatus;
}

export interface NotApplicableProposal {
  item_key: string;
  label: string;
  summary: string;
  proposed_by: PartyRole[];
}

export interface ReceiptTeachbackStatus {
  participant_id: PartyRole;
  teachback_id: string;
  result: TeachbackComparisonState;
  completed_at: string;
}

export interface LiveClarityReceipt {
  id: string;
  session_id: string;
  agreement_version_id: string;
  agreement_version_number: number;
  issued_at: string;
  participants: ReceiptParticipant[];
  aligned_terms: AgreementTerm[];
  unresolved_terms: AgreementTerm[];
  one_sided_terms: AgreementTerm[];
  not_applicable_terms: NotApplicableProposal[];
  not_discussed_terms: AgreementTerm[];
  clarification_history: ReceiptClarificationSummary[];
  teachback_status: ReceiptTeachbackStatus[];
  confirmations: ReceiptConfirmation[];
  status: ReceiptStatus;
  application_version: string;
  schema_version: string;
  integrity_hash: string;
  disclaimer: string;
}

export class MeaningSyncApiError extends Error {
  constructor(
    message: string,
    readonly code: AnalysisErrorCode | LiveErrorCode | "request_failed" =
      "request_failed",
    readonly retryable = false,
    readonly status = 0,
    readonly currentAgreementVersionId: string | null = null,
  ) {
    super(message);
    this.name = "MeaningSyncApiError";
  }
}

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as {
      detail?:
        | string
        | {
            code?: AnalysisErrorCode | LiveErrorCode;
            message?: string;
            retryable?: boolean;
            current_agreement_version_id?: string | null;
          };
    } | null;
    const detail = problem?.detail;
    if (detail && typeof detail === "object") {
      throw new MeaningSyncApiError(
        detail.message ?? "MeaningSync could not complete that step.",
        detail.code,
        detail.retryable ?? false,
        response.status,
        detail.current_agreement_version_id ?? null,
      );
    }
    throw new MeaningSyncApiError(
      typeof detail === "string"
        ? detail
        : "MeaningSync could not complete that step.",
      "request_failed",
      response.status >= 500,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

const sessionPath = (sessionId: string) =>
  `/api/v1/demo/sessions/${sessionId}`;
const liveSessionPath = (sessionId: string) =>
  `/api/v1/live/sessions/${encodeURIComponent(sessionId)}`;

export const api = {
  createDemo: (
    participantLanguages: Record<PartyRole, LanguageCode> = {
      hirer: "en",
      worker: "en",
    },
  ) =>
    request<SessionView>("/api/v1/demo/sessions", {
      method: "POST",
      body: JSON.stringify({ participant_languages: participantLanguages }),
    }),
  submitConsent: (sessionId: string, party: PartyRole, accepted = true) =>
    request<SessionView>(`${sessionPath(sessionId)}/consent`, {
      method: "POST",
      body: JSON.stringify({ party, accepted }),
    }),
  analyze: (sessionId: string) =>
    request<SessionView>(`${sessionPath(sessionId)}/analysis`, {
      method: "POST",
    }),
  beginClarification: (sessionId: string) =>
    request<SessionView>(`${sessionPath(sessionId)}/clarifications`, {
      method: "POST",
    }),
  answerClarification: (
    sessionId: string,
    questionId: string,
    party: PartyRole,
    answer: string,
  ) =>
    request<ClarificationResult>(
      `${sessionPath(sessionId)}/clarifications/${questionId}/answers`,
      { method: "POST", body: JSON.stringify({ party, answer }) },
    ),
  confirm: (sessionId: string, party: PartyRole, teachback: string) =>
    request<SessionView>(`${sessionPath(sessionId)}/confirmations`, {
      method: "POST",
      body: JSON.stringify({ party, confirmed: true, teachback }),
    }),
  createReceipt: (sessionId: string) =>
    request<ClarityReceipt>(`${sessionPath(sessionId)}/receipt`, {
      method: "POST",
    }),
  analyzeAgreement: (submission: AgreementAnalysisRequest) =>
    request<AgreementAnalysisResponse>("/api/v1/agreements/analyze", {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  createLiveSession: (submission: LiveSessionCreate) =>
    request<LiveSessionView>("/api/v1/live/sessions", {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  getLiveSession: (sessionId: string) =>
    request<LiveSessionView>(liveSessionPath(sessionId)),
  analyzeLiveSession: (sessionId: string) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/analysis`, {
      method: "POST",
      body: JSON.stringify({ expected_agreement_version_id: null }),
    }),
  listAgreementVersions: (sessionId: string) =>
    request<AgreementVersion[]>(
      `${liveSessionPath(sessionId)}/agreement-versions`,
    ),
  getAgreementVersion: (sessionId: string, versionId: string) =>
    request<AgreementVersion>(
      `${liveSessionPath(sessionId)}/agreement-versions/${encodeURIComponent(versionId)}`,
    ),
  addLiveStatements: (
    sessionId: string,
    submission: {
      expected_agreement_version_id: string;
      messages: AnalysisMessage[];
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/statements`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  proposeNotApplicable: (
    sessionId: string,
    submission: {
      expected_agreement_version_id: string;
      participant_id: PartyRole;
      item_key: string;
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/not-applicable`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  submitLiveClarificationAnswer: (
    sessionId: string,
    clarificationId: string,
    submission: {
      participant_id: PartyRole;
      answer: string;
      expected_agreement_version_id: string;
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(
      `${liveSessionPath(sessionId)}/clarifications/${encodeURIComponent(clarificationId)}/answers`,
      { method: "POST", body: JSON.stringify(submission) },
    ),
  leaveLiveClarificationUnresolved: (
    sessionId: string,
    clarificationId: string,
    submission: {
      expected_agreement_version_id: string;
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(
      `${liveSessionPath(sessionId)}/clarifications/${encodeURIComponent(clarificationId)}/leave-unresolved`,
      { method: "POST", body: JSON.stringify(submission) },
    ),
  reviewOptionalDetails: (
    sessionId: string,
    submission: {
      expected_agreement_version_id: string;
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(
      `${liveSessionPath(sessionId)}/optional-details/reviewed`,
      { method: "POST", body: JSON.stringify(submission) },
    ),
  submitTeachback: (
    sessionId: string,
    submission: {
      participant_id: PartyRole;
      text: string;
      original_language: LanguageCode;
      expected_agreement_version_id: string;
      acknowledged_unresolved_item_keys: string[];
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/teachbacks`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  submitLiveConfirmation: (
    sessionId: string,
    submission: {
      participant_id: PartyRole;
      expected_agreement_version_id: string;
      teachback_id: string;
      decision: "confirm" | "request_change";
      unresolved_item_acknowledgments: string[];
      change_item_key?: string;
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/confirmations`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  getLiveConfirmationStatus: (sessionId: string) =>
    request<ConfirmationStatusView>(
      `${liveSessionPath(sessionId)}/confirmation-status`,
    ),
  beginLiveReview: (
    sessionId: string,
    submission: {
      expected_agreement_version_id: string;
      acknowledged_unresolved_item_keys: string[];
      request_id: string;
    },
  ) =>
    request<LiveSessionView>(`${liveSessionPath(sessionId)}/review`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),
  issueLiveReceipt: (
    sessionId: string,
    expectedAgreementVersionId: string,
    requestId: string,
  ) =>
    request<LiveClarityReceipt>(`${liveSessionPath(sessionId)}/receipt`, {
      method: "POST",
      body: JSON.stringify({
        expected_agreement_version_id: expectedAgreementVersionId,
        request_id: requestId,
      }),
    }),
  getLiveReceipt: (sessionId: string) =>
    request<LiveClarityReceipt>(`${liveSessionPath(sessionId)}/receipt`),
};
