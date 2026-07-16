import { readFileSync } from "node:fs";

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveExperience } from "@/components/live-experience";
import {
  api,
  MeaningSyncApiError,
  type AgreementAnalysisResponse,
  type EvidenceReference,
} from "@/lib/api";

const evidence = (
  id: string,
  role: "hirer" | "worker",
  text: string,
  order: number,
): EvidenceReference => ({
  source: "transcript",
  reference_id: id,
  participant_id: role,
  role,
  speaker_name: role === "hirer" ? "Homeowner" : "Electrician",
  message_id: id,
  original_text: text,
  original_language: "en",
  order,
  timestamp: `2026-07-16T09:0${order}:00Z`,
});

const analysis: AgreementAnalysisResponse = {
  session_id: "live-session",
  mode: "live",
  prompt_version: "agreement-analysis-v3",
  model: "gpt-5.6",
  status: "complete",
  warnings: [],
  terms: [
    {
      id: "timing-1",
      analysis_item_key: "timing.start",
      topic: "timing",
      facet: "start",
      label: "Start timing",
      summary: "Both participants agree work can start today.",
      state: "aligned",
      participant_positions: [
        {
          participant_id: "hirer",
          role: "hirer",
          summary: "Start today.",
          evidence_message_ids: ["message-3"],
        },
        {
          participant_id: "worker",
          role: "worker",
          summary: "Can start today.",
          evidence_message_ids: ["message-4"],
        },
      ],
      participant_confirmations: { hirer: "confirmed", worker: "confirmed" },
      evidence_message_ids: ["message-3", "message-4"],
      evidence: [
        evidence("message-3", "hirer", "The work can start today.", 3),
        evidence("message-4", "worker", "Yes, I can start today.", 4),
      ],
      clarification_target: null,
    },
    {
      id: "materials-2",
      analysis_item_key: "materials.inclusion",
      topic: "materials",
      facet: "inclusion",
      label: "Materials and replacement parts",
      summary: "The participants disagree about replacement parts.",
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
      participant_confirmations: {
        hirer: "conflicting",
        worker: "conflicting",
      },
      evidence_message_ids: ["message-1", "message-2"],
      evidence: [
        evidence("message-1", "hirer", "Parts are included.", 1),
        evidence("message-2", "worker", "Parts are separate.", 2),
      ],
      clarification_target: "materials.inclusion",
    },
    {
      id: "warranty-3",
      analysis_item_key: "warranty.coverage",
      topic: "warranty",
      facet: "coverage",
      label: "Warranty",
      summary: "Warranty was not discussed.",
      state: "not_discussed",
      participant_positions: [],
      participant_confirmations: {
        hirer: "not_stated",
        worker: "not_stated",
      },
      evidence_message_ids: [],
      evidence: [],
      clarification_target: null,
    },
  ],
  primary_clarification: {
    id: "clarify-materials",
    term_id: "materials-2",
    target_item_key: "materials.inclusion",
    target: "materials",
    facet: "inclusion",
    evidence_message_ids: ["message-1", "message-2"],
    prompt: "Does ₹1,200 include replacement parts?",
    options: [],
  },
};

describe("LiveExperience", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders the centered workspace structure with explicit field labels", () => {
    const { container } = render(
      <LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />,
    );

    const page = container.querySelector(".live-page");
    const workspace = container.querySelector(".live-workspace");
    expect(page).not.toBeNull();
    expect(workspace?.children).toHaveLength(2);
    expect(workspace?.children[0]).toHaveClass("statement-composer");
    expect(workspace?.children[1]).toHaveClass("conversation-panel");

    const speaker = screen.getByLabelText("Speaker");
    const statement = screen.getByLabelText("Original statement");
    expect(speaker.id).not.toBe("");
    expect(statement.id).not.toBe("");
    expect(container.querySelector(`label[for="${speaker.id}"]`)).toBeVisible();
    expect(container.querySelector(`label[for="${statement.id}"]`)).toBeVisible();
  });

  it("keeps the live container, card grid, and mobile stack CSS contract", () => {
    const css = readFileSync("src/app/globals.css", "utf8");

    expect(css).toMatch(/\.live-page \{[^}]*max-width: 1100px/);
    expect(css).toMatch(/\.live-workspace \{[^}]*display: grid/);
    expect(css).toMatch(
      /\.statement-composer, \.conversation-panel \{[^}]*border:[^}]*border-radius:[^}]*padding:/,
    );
    expect(css).toMatch(
      /@media \(min-width: 920px\)[\s\S]*?\.live-workspace \{[^}]*grid-template-columns:/,
    );
    expect(css).toMatch(
      /@media \(max-width: 540px\)[\s\S]*?\.preview-notice, \.analysis-gate, \.analysis-error \{[^}]*flex-direction: column/,
    );
  });

  it("adds, edits, and removes speaker-attributed statements", () => {
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);

    const textarea = screen.getByLabelText("Original statement");
    fireEvent.change(textarea, { target: { value: "Repair the fan." } });
    fireEvent.click(screen.getByRole("button", { name: "Add statement" }));
    expect(screen.getByText("Repair the fan.")).toBeVisible();

    fireEvent.change(screen.getByLabelText("Speaker"), {
      target: { value: "worker" },
    });
    fireEvent.change(textarea, { target: { value: "I can repair the fan." } });
    fireEvent.click(screen.getByRole("button", { name: "Add statement" }));
    expect(screen.getByRole("button", { name: "Analyze Agreement" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Edit statement 1" }));
    fireEvent.change(screen.getByLabelText("Original statement"), {
      target: { value: "Repair the fan and switches." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByText("Repair the fan and switches.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Remove statement 1" }));
    expect(screen.queryByText("Repair the fan and switches.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Agreement" })).toBeDisabled();
  });

  it("loads the sample and renders validated results with evidence", async () => {
    const analyzeAgreement = vi
      .spyOn(api, "analyzeAgreement")
      .mockResolvedValue(analysis);
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Load sample conversation" }),
    );
    expect(screen.getByText("4 statements")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Analyze Agreement" }));

    expect(await screen.findByText("Does ₹1,200 include replacement parts?")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Confirmed" })).toBeVisible();
    expect(screen.getAllByText("Parts are included.")[0]).toBeVisible();
    expect(screen.getByText("Warranty was not discussed.")).toBeVisible();
    expect(screen.getAllByText("The work can start today.")[0]).toBeInTheDocument();
    expect(analyzeAgreement).toHaveBeenCalledTimes(1);
    const request = analyzeAgreement.mock.calls[0][0];
    expect(request.mode).toBe("live");
    expect(request.messages).toHaveLength(4);
    expect(request.participants.map((participant) => participant.language)).toEqual([
      "en",
      "en",
    ]);
  });

  it("shows a loading state while analysis is in progress", async () => {
    let resolveAnalysis: (value: AgreementAnalysisResponse) => void = () => {};
    vi.spyOn(api, "analyzeAgreement").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnalysis = resolve;
        }),
    );
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Load sample conversation" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze Agreement" }));

    expect(screen.getByRole("button", { name: "Analyzing agreement" })).toBeDisabled();
    await act(async () => resolveAnalysis(analysis));
    expect(await screen.findByText("Validated analysis")).toBeVisible();
  });

  it("keeps a partial agreement map visible when clarification is unavailable", async () => {
    const partialAnalysis: AgreementAnalysisResponse = {
      ...analysis,
      status: "partial",
      warnings: [
        {
          code: "clarification_unavailable",
          message:
            "The agreement map is ready, but a clarification question could not be generated. Review the highlighted conflict.",
        },
      ],
      primary_clarification: null,
    };
    vi.spyOn(api, "analyzeAgreement").mockResolvedValue(partialAnalysis);
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Load sample conversation" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze Agreement" }));

    expect(await screen.findByText("Partial analysis")).toBeVisible();
    expect(screen.getByText("Clarification unavailable").closest("article")).toHaveTextContent(
      "The agreement map is ready, but a clarification question could not be generated.",
    );
    expect(screen.getByRole("heading", { name: "Needs clarification" })).toBeVisible();
    expect(screen.getByText("The participants disagree about replacement parts.")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe retry state and retries successfully", async () => {
    vi.spyOn(api, "analyzeAgreement")
      .mockRejectedValueOnce(
        new MeaningSyncApiError("Live analysis timed out.", "timeout", true),
      )
      .mockResolvedValueOnce(analysis);
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Load sample conversation" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze Agreement" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live analysis timed out.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(
        screen.getByText("Does ₹1,200 include replacement parts?"),
      ).toBeVisible(),
    );
  });
});
