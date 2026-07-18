import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSessionExperience } from "@/components/live-session-experience";
import { api, type LiveSessionView } from "@/lib/api";
import { guidedV5Session } from "@/test/fixtures/live-guided";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const conversationSession = (): LiveSessionView =>
  guidedV5Session({
    stage: "conversation_draft",
    agreement_versions: [],
    current_agreement_version_id: null,
    questions: [],
    active_participant_id: null,
    participant_readiness: { hirer: false, worker: false },
    messages: [
      {
        message_id: "m1",
        speaker_id: "hirer",
        original_text: "Please repair the fan.",
        original_language: "en",
        order: 1,
        timestamp: "2026-07-18T09:00:00Z",
      },
      {
        message_id: "m2",
        speaker_id: "worker",
        original_text: "The labour price is ₹1,200.",
        original_language: "en",
        order: 2,
        timestamp: "2026-07-18T09:01:00Z",
      },
    ],
    guidance: {
      ...guidedV5Session().guidance,
      user_stage: "conversation",
      acting_participant: null,
      active_question_id: null,
      active_clarification_id: null,
      target_item_key: null,
    },
  });

describe("LiveSessionExperience conversation-first flow", () => {
  beforeEach(() => {
    window.sessionStorage.setItem(
      "meaningsync.live.live-guided-v5.hirer",
      "test-access-token",
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
    push.mockReset();
  });

  it("renders exactly the six canonical visible steps", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(conversationSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    expect(await screen.findByText("Talk about the agreement")).toBeVisible();
    const progress = screen.getByRole("navigation", {
      name: "Live session progress",
    });
    for (const label of [
      "Preferences",
      "Participation",
      "Conversation",
      "Check understanding",
      "Confirm",
      "Receipt",
    ]) {
      expect(progress).toHaveTextContent(label);
    }
    expect(progress.querySelectorAll(":scope > span")).toHaveLength(6);
    expect(screen.queryByText("Clarify")).not.toBeInTheDocument();
  });

  it("renders a real chat and role-scoped composer with generic Live roles", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(conversationSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    expect(await screen.findByText("Please repair the fan.")).toBeVisible();
    expect(screen.getAllByText("Customer").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Service provider").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Message as Customer")).toBeVisible();
    expect(screen.queryByText("Homeowner")).not.toBeInTheDocument();
  });

  it("requires both readiness flags before the creator can compare", async () => {
    const session = conversationSession();
    vi.spyOn(api, "getLiveSession").mockResolvedValue(session);
    const readiness = vi
      .spyOn(api, "setLiveReadiness")
      .mockResolvedValue({
        ...session,
        participant_readiness: { hirer: true, worker: false },
      });
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    const compare = await screen.findByRole("button", {
      name: /Compare our understanding/,
    });
    expect(compare).toBeDisabled();
    fireEvent.click(screen.getAllByRole("button", { name: "I’m ready to review" })[0]);
    await waitFor(() => expect(readiness).toHaveBeenCalled());
  });

  it("renders matches, decisions, and not-discussed sections with evidence", async () => {
    const session = guidedV5Session();
    vi.spyOn(api, "getLiveSession").mockResolvedValue(session);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    expect(await screen.findByRole("heading", { name: "What matches" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Needs a decision" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Not discussed" })).toBeVisible();
    expect(screen.getAllByText(/View conversation evidence/).length).toBeGreaterThan(0);
    expect(screen.getByText("I will repair the fan and two switches.")).toBeInTheDocument();
  });

  it("shows only the addressed participant a private bounded choice", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    expect(await screen.findByText("Private choice · Customer")).toBeVisible();
    expect(screen.getByText(/stays hidden/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Submit my choice" }),
    ).toBeDisabled();
  });
});
