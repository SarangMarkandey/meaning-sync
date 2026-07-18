import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSessionExperience } from "@/components/live-session-experience";
import { api } from "@/lib/api";
import { guidedV5Session } from "@/test/fixtures/live-guided";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const workerConversation = guidedV5Session({
  stage: "conversation_draft",
  participation_mode: "separate_devices",
  viewer_role: "worker",
  creator_role: "hirer",
  participant_readiness: { hirer: false, worker: false },
  agreement_versions: [],
  current_agreement_version_id: null,
  questions: [],
  active_participant_id: null,
  messages: [],
  guidance: {
    ...guidedV5Session().guidance,
    user_stage: "conversation",
    acting_participant: null,
    active_question_id: null,
    active_clarification_id: null,
    target_item_key: null,
  },
});

describe("separate-device conversation", () => {
  beforeEach(() => {
    sessionStorage.setItem(
      "meaningsync.live.live-guided-v5.worker",
      "worker-access-token",
    );
  });
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it("submits only as the viewer role with that role credential", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(workerConversation);
    const add = vi.spyOn(api, "addDraftStatement").mockResolvedValue({
      ...workerConversation,
      messages: [
        {
          message_id: "m1",
          speaker_id: "worker",
          original_text: "I can do the work tomorrow.",
          original_language: "en",
          order: 1,
          timestamp: "2026-07-18T10:00:00Z",
        },
      ],
    });
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.change(await screen.findByLabelText("Message as Service provider"), {
      target: { value: "I can do the work tomorrow." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(add).toHaveBeenCalled());
    expect(add.mock.calls[0][3]).toBe("worker-access-token");
    expect(screen.queryByRole("button", { name: "Customer" })).not.toBeInTheDocument();
  });

  it("does not expose another participant’s private decision controls", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(
      guidedV5Session({
        participation_mode: "separate_devices",
        viewer_role: "worker",
        creator_role: "hirer",
        active_participant_id: "hirer",
      }),
    );
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    expect(await screen.findByText("Waiting for Customer to answer privately.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Submit my choice" })).not.toBeInTheDocument();
  });
});
