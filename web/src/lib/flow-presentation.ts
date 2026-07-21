import type {
  LiveSessionStage,
  LiveSessionView,
  PartyRole,
  SessionParticipant,
} from "@/lib/api";

export type VisibleFlowStage =
  | "preferences"
  | "participation"
  | "conversation"
  | "check_understanding"
  | "confirm"
  | "receipt";

export const visibleFlowSteps: Array<{
  id: VisibleFlowStage;
  label: string;
}> = [
  { id: "preferences", label: "Preferences" },
  { id: "participation", label: "Participation" },
  { id: "conversation", label: "Conversation" },
  { id: "check_understanding", label: "Check understanding" },
  { id: "confirm", label: "Confirm" },
  { id: "receipt", label: "Receipt" },
];

const stageMap: Record<LiveSessionStage, VisibleFlowStage> = {
  conversation_draft: "conversation",
  analyzing: "check_understanding",
  needs_clarification: "check_understanding",
  ready_for_understanding_check: "check_understanding",
  awaiting_understanding_checks: "check_understanding",
  awaiting_confirmations: "confirm",
  confirmed: "confirm",
  receipt_issued: "receipt",
};

export function presentLiveStage(stage: LiveSessionStage): VisibleFlowStage {
  return stageMap[stage];
}

export function roleLabel(
  role: PartyRole,
  mode: "live" | "demo" = "live",
  language: "en" | "hi" = "en",
) {
  if (mode === "demo") return role === "hirer" ? "Homeowner" : "Electrician";
  if (language === "hi") return role === "hirer" ? "ग्राहक" : "सेवा प्रदाता";
  return role === "hirer" ? "Customer" : "Service provider";
}

export function participantLabel(
  participant: Pick<SessionParticipant, "role" | "display_name" | "language">,
): string {
  const role = roleLabel(participant.role, "live", participant.language);
  return participant.display_name ? `${participant.display_name} · ${role}` : role;
}

export function otherRole(role: PartyRole): PartyRole {
  return role === "hirer" ? "worker" : "hirer";
}

export function presentationFor(session: LiveSessionView) {
  const stage = presentLiveStage(session.stage);
  const title =
    stage === "conversation"
      ? "Talk about the agreement"
      : stage === "check_understanding"
        ? "Check your shared understanding"
        : stage === "confirm"
          ? "Confirm this shared record"
          : "Your clarity receipt";
  return { stage, title };
}
