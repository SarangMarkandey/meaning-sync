import { readFileSync } from "node:fs";

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveExperience } from "@/components/live-experience";
import { api, MeaningSyncApiError, type LiveSessionView } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const liveSession: LiveSessionView = {
  id: "server-session-1",
  stage: "conversation_draft",
  created_at: "2026-07-16T10:00:00Z",
  participants: [
    { id: "hirer", role: "hirer", language: "en", display_name: "Homeowner" },
    { id: "worker", role: "worker", language: "en", display_name: "Electrician" },
  ],
  messages: [],
  agreement_versions: [],
  current_agreement_version_id: null,
  questions: [],
  understanding_reviews: {},
  active_participant_id: null,
  confirmations: [],
  receipt_id: null,
  receipt_ready: false,
  clarification_attempt_limit: 3,
  guidance: {
    user_stage: "conversation",
    headline: "Add what each person said",
    explanation: "Add at least one meaningful statement from each person.",
    primary_action: "submit_selection",
    primary_label: "Check understanding",
    secondary_action: null,
    secondary_label: null,
    required_issue_count: 0,
    optional_missing_count: 0,
    acting_participant: null,
    active_question_id: null,
    active_clarification_id: null,
    target_item_key: null,
    required_item_keys: [],
    optional_item_keys: [],
  },
};

describe("LiveExperience", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("renders the centered workspace structure with explicit field labels", () => {
    const { container } = render(
      <LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />,
    );

    expect(container.querySelector(".live-page")).not.toBeNull();
    expect(container.querySelector(".live-workspace")?.children).toHaveLength(2);
    const speaker = screen.getByLabelText("Speaker");
    const statement = screen.getByLabelText("Original statement");
    expect(container.querySelector(`label[for="${speaker.id}"]`)).toBeVisible();
    expect(container.querySelector(`label[for="${statement.id}"]`)).toBeVisible();
  });

  it("keeps the live container, card grid, and mobile stack CSS contract", () => {
    const css = readFileSync("src/app/globals.css", "utf8");
    expect(css).toMatch(/\.live-page \{[^}]*max-width: 1100px/);
    expect(css).toMatch(/\.live-workspace \{[^}]*display: grid/);
    expect(css).toMatch(/@media \(min-width: 920px\)[\s\S]*?\.live-workspace \{[^}]*grid-template-columns:/);
    expect(css).toMatch(/@media \(max-width: 540px\)[\s\S]*?\.preview-notice, \.analysis-gate, \.analysis-error \{[^}]*flex-direction: column/);
  });

  it("adds, edits, and removes speaker-attributed statements", () => {
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);
    const textarea = screen.getByLabelText("Original statement");
    fireEvent.change(textarea, { target: { value: "Repair the fan." } });
    fireEvent.click(screen.getByRole("button", { name: "Add statement" }));
    fireEvent.change(screen.getByLabelText("Speaker"), { target: { value: "worker" } });
    fireEvent.change(textarea, { target: { value: "I can repair the fan." } });
    fireEvent.click(screen.getByRole("button", { name: "Add statement" }));
    expect(screen.getByRole("button", { name: "Check understanding" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Edit statement 1" }));
    fireEvent.change(textarea, { target: { value: "Repair the fan and switches." } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByText("Repair the fan and switches.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Remove statement 1" }));
    expect(screen.getByRole("button", { name: "Check understanding" })).toBeDisabled();
  });

  it("creates a server session, deliberately analyzes it, then opens its route", async () => {
    const create = vi.spyOn(api, "createLiveSession").mockResolvedValue(liveSession);
    const analyze = vi
      .spyOn(api, "analyzeLiveSession")
      .mockResolvedValue({ ...liveSession, stage: "needs_clarification" });
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Load sample conversation" }));
    fireEvent.click(screen.getByRole("button", { name: "Check understanding" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/live/server-session-1"));
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0].messages).toHaveLength(4);
    expect(analyze).toHaveBeenCalledWith("server-session-1");
  });

  it("prevents a double submit while analysis is pending", async () => {
    let resolveCreate: (value: LiveSessionView) => void = () => {};
    vi.spyOn(api, "createLiveSession").mockImplementation(
      () => new Promise((resolve) => { resolveCreate = resolve; }),
    );
    vi.spyOn(api, "analyzeLiveSession").mockResolvedValue(liveSession);
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Load sample conversation" }));
    fireEvent.click(screen.getByRole("button", { name: "Check understanding" }));
    expect(screen.getByRole("heading", { name: "Comparing both people’s statements…" })).toBeVisible();
    await act(async () => resolveCreate(liveSession));
    await waitFor(() => expect(push).toHaveBeenCalled());
  });

  it("shows a safe retry state when session creation fails", async () => {
    vi.spyOn(api, "createLiveSession").mockRejectedValue(
      new MeaningSyncApiError("Live analysis timed out.", "timeout", true, 504),
    );
    render(<LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Load sample conversation" }));
    fireEvent.click(screen.getByRole("button", { name: "Check understanding" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Live analysis timed out.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
    expect(push).not.toHaveBeenCalled();
  });
});
