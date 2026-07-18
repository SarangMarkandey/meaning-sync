import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveWaitingRoom } from "@/components/live-waiting-room";
import { api } from "@/lib/api";
import { guidedV5Session } from "@/test/fixtures/live-guided";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

const waitingSession = (connected = false) =>
  guidedV5Session({
    id: "separate-1",
    stage: "conversation_draft",
    messages: [],
    participation_mode: "separate_devices",
    creator_role: "hirer",
    viewer_role: "hirer",
    participant_presence: [
      { role: "hirer", status: "connected", last_seen_at: "2026-07-18T10:00:00Z" },
      { role: "worker", status: connected ? "connected" : "waiting", last_seen_at: connected ? "2026-07-18T10:00:02Z" : null },
    ],
  });

describe("LiveWaitingRoom", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    replace.mockReset();
    sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("renders one coherent invitation card without exposing the secret", async () => {
    sessionStorage.setItem(
      "meaningsync.live.separate-1.hirer",
      "host-access-token",
    );
    window.history.replaceState(
      null,
      "",
      "/live/separate-1/waiting#invite=private-worker-invite&expires=2026-07-18T10%3A00%3A00Z&role=worker",
    );
    vi.spyOn(api, "getLiveSession").mockResolvedValue(waitingSession());
    render(<LiveWaitingRoom sessionId="separate-1" />);
    expect(await screen.findByRole("heading", { name: "Invite the Service provider" })).toBeVisible();
    expect(screen.getByLabelText("Service provider joining QR code")).toBeVisible();
    expect(screen.getByText("Waiting for Service provider…")).toBeVisible();
    expect(screen.getByText("Customer")).toBeVisible();
    expect(screen.getByText("Connected")).toBeVisible();
    expect(screen.getByText("Waiting to join")).toBeVisible();
    expect(screen.getByText(/Invitation expires/)).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(document.body).not.toHaveTextContent("private-worker-invite");
    expect(screen.queryByRole("button", { name: /Continue/ })).not.toBeInTheDocument();
  });

  it("automatically opens the conversation as soon as the invitee joins", async () => {
    sessionStorage.setItem(
      "meaningsync.live.separate-1.hirer",
      "host-access-token",
    );
    window.history.replaceState(
      null,
      "",
      "/live/separate-1/waiting#invite=private-worker-invite&expires=2026-07-18T10%3A00%3A00Z&role=worker",
    );
    vi.spyOn(api, "getLiveSession").mockResolvedValue(waitingSession(true));
    render(<LiveWaitingRoom sessionId="separate-1" />);
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/live/separate-1"),
    );
  });
});
