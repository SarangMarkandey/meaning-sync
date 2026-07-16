import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgreementMap } from "@/components/agreement-map";
import type { AgreementTerm, EvidenceReference } from "@/lib/api";

const evidence = (
  messageId: string,
  role: "hirer" | "worker",
  text: string,
  order: number,
): EvidenceReference => ({
  source: "transcript",
  reference_id: messageId,
  participant_id: role,
  role,
  speaker_name: role === "hirer" ? "Homeowner" : "Electrician",
  message_id: messageId,
  original_text: text,
  original_language: "en",
  order,
  timestamp: `2026-07-16T09:0${order}:00Z`,
});

const terms: AgreementTerm[] = [
  {
    id: "scope-1",
    analysis_item_key: "scope.work",
    topic: "scope",
    facet: "work",
    label: "Scope of work",
    summary: "Repair one fan and two switches",
    state: "aligned",
    participant_positions: [
      {
        participant_id: "hirer",
        role: "hirer",
        summary: "Repair the fan and switches.",
        evidence_message_ids: ["message-1"],
      },
      {
        participant_id: "worker",
        role: "worker",
        summary: "Repair the fan and switches.",
        evidence_message_ids: ["message-2"],
      },
    ],
    evidence_message_ids: ["message-1", "message-2"],
    evidence: [
      evidence("message-1", "hirer", "Repair the fan and two switches.", 1),
      evidence("message-2", "worker", "I will repair those items.", 2),
    ],
    participant_confirmations: { hirer: "confirmed", worker: "confirmed" },
    clarification_target: null,
  },
  {
    id: "materials-2",
    analysis_item_key: "materials.inclusion",
    topic: "materials",
    facet: "inclusion",
    label: "Materials",
    summary: "Different expectations about replacement parts",
    state: "conflicting",
    participant_positions: [
      {
        participant_id: "hirer",
        role: "hirer",
        summary: "Parts are included.",
        evidence_message_ids: ["message-1"],
      },
      {
        participant_id: "worker",
        role: "worker",
        summary: "Parts are separate.",
        evidence_message_ids: ["message-2"],
      },
    ],
    evidence_message_ids: ["message-1", "message-2"],
    evidence: [
      evidence("message-1", "hirer", "Parts are included.", 1),
      evidence("message-2", "worker", "Replacement parts are separate.", 2),
    ],
    participant_confirmations: {
      hirer: "conflicting",
      worker: "conflicting",
    },
    clarification_target: "materials.inclusion",
  },
  {
    id: "payment-3",
    analysis_item_key: "payment.timing",
    topic: "payment",
    facet: "timing",
    label: "Payment timing",
    summary: "Only the homeowner states payment timing.",
    state: "stated_by_one",
    participant_positions: [
      {
        participant_id: "hirer",
        role: "hirer",
        summary: "Payment follows completion.",
        evidence_message_ids: ["message-3"],
      },
    ],
    evidence_message_ids: ["message-3"],
    evidence: [evidence("message-3", "hirer", "I will pay after the work.", 3)],
    participant_confirmations: { hirer: "stated", worker: "not_stated" },
    clarification_target: null,
  },
  {
    id: "completion-4",
    analysis_item_key: "completion.deadline",
    topic: "completion",
    facet: "deadline",
    label: "Completion time",
    summary: "Completion time was not discussed.",
    state: "not_discussed",
    participant_positions: [],
    evidence_message_ids: [],
    evidence: [],
    participant_confirmations: { hirer: "not_stated", worker: "not_stated" },
    clarification_target: null,
  },
];

describe("AgreementMap", () => {
  it("renders confirmed, clarification, and not-discussed sections", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getByRole("heading", { name: "Confirmed" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Needs clarification" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Not discussed" }),
    ).toBeVisible();
    expect(screen.getByText("Repair one fan and two switches")).toBeVisible();
    expect(screen.getByText("Stated by one person")).toBeVisible();
  });

  it("shows participant positions for conflicts", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getAllByText("Parts are included.")[0]).toBeVisible();
    expect(screen.getByText("Parts are separate.")).toBeVisible();
  });

  it("shows original evidence metadata", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getAllByText(/Homeowner · original · English/).length).toBeGreaterThan(0);
    const quote = screen.getByText("Repair the fan and two switches.");
    expect(quote).not.toBeVisible();
    fireEvent.click(screen.getAllByText(/View evidence/)[0]);
    expect(quote).toBeVisible();
    expect(screen.getAllByText(/message 1/).length).toBeGreaterThan(0);
  });

  it("shows evidence controls only for discussed terms", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getAllByText(/View evidence/)).toHaveLength(3);
    const completionCard = screen.getByText("Completion time").closest("article");
    expect(completionCard).not.toBeNull();
    expect(
      within(completionCard as HTMLElement).queryByText(/View evidence/),
    ).not.toBeInTheDocument();
  });

  it("provides an empty state", () => {
    render(<AgreementMap terms={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "No agreement terms are available yet.",
    );
  });
});
