import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgreementMap } from "@/components/agreement-map";
import type { AgreementTerm } from "@/lib/api";

const terms: AgreementTerm[] = [
  {
    id: "scope",
    label: "Scope of work",
    status: "confirmed",
    value: "Repair fan and two switches",
    evidence: [
      {
        source: "transcript",
        reference_id: "turn-1",
        excerpt: "fan aur do switches",
      },
    ],
  },
  {
    id: "materials",
    label: "Replacement parts",
    status: "conflict",
    value: "Different expectations",
    evidence: [
      {
        source: "transcript",
        reference_id: "turn-3",
        excerpt: "parts included",
      },
    ],
  },
  {
    id: "completion",
    label: "Completion time",
    status: "missing",
    value: null,
    evidence: [],
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
    expect(screen.getByText("Repair fan and two switches")).toBeVisible();
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
