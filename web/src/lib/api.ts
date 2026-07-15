export type SessionMode = "demo" | "live";
export type PartyRole = "hirer" | "worker";
export type LanguageCode = "en" | "hi";
export type ConsentStatus = "pending" | "accepted" | "declined";
export type TermStatus = "confirmed" | "conflict" | "missing";
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
  timestamp: string;
  translations: Partial<Record<LanguageCode, string>>;
}

export interface EvidenceReference {
  source: "transcript" | "clarification";
  reference_id: string;
  participant_id: PartyRole;
  message_id: string | null;
  original_text: string;
}

export interface AgreementTerm {
  id: string;
  label: string;
  status: TermStatus;
  value: string | null;
  evidence: EvidenceReference[];
  participant_confirmations: Record<
    PartyRole,
    "confirmed" | "conflicting" | "not_stated"
  >;
}

export interface ClarificationQuestion {
  id: string;
  term_id: string;
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
      detail?: string;
    } | null;
    throw new Error(problem?.detail ?? "MeaningSync could not complete that step.");
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
  confirm: (
    sessionId: string,
    party: PartyRole,
    teachback: string,
  ) =>
    request<SessionView>(`${sessionPath(sessionId)}/confirmations`, {
      method: "POST",
      body: JSON.stringify({ party, confirmed: true, teachback }),
    }),
  createReceipt: (sessionId: string) =>
    request<ClarityReceipt>(`${sessionPath(sessionId)}/receipt`, {
      method: "POST",
    }),
};
