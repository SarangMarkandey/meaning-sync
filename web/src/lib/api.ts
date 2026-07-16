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
  display_name: string;
  language: LanguageCode;
  requested_display_language: LanguageCode;
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

export class MeaningSyncApiError extends Error {
  constructor(
    message: string,
    readonly code: AnalysisErrorCode | "request_failed" = "request_failed",
    readonly retryable = false,
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
        | { code?: AnalysisErrorCode; message?: string; retryable?: boolean };
    } | null;
    const detail = problem?.detail;
    if (detail && typeof detail === "object") {
      throw new MeaningSyncApiError(
        detail.message ?? "MeaningSync could not complete that step.",
        detail.code,
        detail.retryable ?? false,
      );
    }
    throw new MeaningSyncApiError(
      typeof detail === "string"
        ? detail
        : "MeaningSync could not complete that step.",
    );
  }
  return response.json() as Promise<T>;
}

const sessionPath = (sessionId: string) =>
  `/api/v1/demo/sessions/${sessionId}`;

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
};
