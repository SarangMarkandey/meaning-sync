import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgreementMap } from "@/components/agreement-map";
import type { AgreementTerm } from "@/lib/api";

const terms: AgreementTerm[] = [
  {
    id: "scope",
    label: "Scope of work",
    status: "confirmed",
    value: "Repair one fan and two switches",
    evidence: [
      {
        source: "transcript",
        reference_id: "message-1",
        participant_id: "hirer",
        message_id: "message-1",
        original_text: "Repair the fan and two switches.",
      },
    ],
    participant_confirmations: { hirer: "confirmed", worker: "confirmed" },
  },
  {
    id: "materials",
    label: "Replacement parts",
    status: "conflict",
    value: "Different expectations",
    evidence: [
      {
        source: "transcript",
        reference_id: "message-2",
        participant_id: "worker",
        message_id: "message-2",
        original_text: "Replacement parts are separate.",
      },
    ],
    participant_confirmations: { hirer: "conflicting", worker: "conflicting" },
  },
  {
    id: "completion",
    label: "Completion time",
    status: "missing",
    value: null,
    evidence: [],
    participant_confirmations: { hirer: "not_stated", worker: "not_stated" },
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
  });

  it("shows the original statement and participant for evidence", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getByText("Homeowner · original")).toBeInTheDocument();
    expect(
      screen.getByText("“Repair the fan and two switches.”"),
    ).toBeInTheDocument();
  });

  it("shows evidence controls only for non-missing terms", () => {
    render(<AgreementMap terms={terms} />);

    expect(screen.getAllByText(/View evidence/)).toHaveLength(2);
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
