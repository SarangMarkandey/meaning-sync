import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveJoin } from "@/components/live-join";
import { api, MeaningSyncApiError } from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

describe("LiveJoin", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    replace.mockReset();
    sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("removes the fragment, records explicit notice acceptance, and stores only access", async () => {
    window.history.replaceState(
      null,
      "",
      "/live/join#invite=one-time-private-invitation&role=worker",
    );
    const exchange = vi.spyOn(api, "exchangeLiveInvitation").mockResolvedValue({
      session_id: "live-separate-1",
      role: "worker",
      access_token: "worker-access-token-12345678901234567890",
      expires_at: "2026-07-18T10:00:00Z",
    });

    render(<LiveJoin />);

    expect(
      await screen.findByRole("heading", {
        name: "Join as Service provider",
      }),
    ).toBeVisible();
    expect(exchange).not.toHaveBeenCalled();
    expect(window.location.hash).toBe("");
    fireEvent.click(screen.getByRole("button", { name: /Join as Service provider/ }));

    await screen.findByText("Connecting you to this MeaningSync session…");
    expect(exchange).toHaveBeenCalledWith("one-time-private-invitation");
    expect(replace).toHaveBeenCalledWith("/live/live-separate-1");
    expect(window.location.hash).toBe("");
    expect(document.body).not.toHaveTextContent("one-time-private-invitation");
    expect(sessionStorage.getItem("meaningsync.live.live-separate-1.worker")).toBe(
      "worker-access-token-12345678901234567890",
    );
  });

  it("shows a truthful state for an expired invitation", async () => {
    window.history.replaceState(null, "", "/live/join#invite=expired-private-link&role=worker");
    vi.spyOn(api, "exchangeLiveInvitation").mockRejectedValue(
      new MeaningSyncApiError(
        "This joining invitation has expired. Ask the host for a new one.",
        "invitation_expired",
        false,
        410,
      ),
    );

    render(<LiveJoin />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Join as Service provider/ }),
    );

    expect(
      await screen.findByText("This joining invitation has expired. Ask the host for a new one."),
    ).toBeVisible();
    expect(window.location.hash).toBe("");
    expect(screen.getByRole("link", { name: "Return home" })).toBeVisible();
  });

  it("distinguishes an invitation that was already used", async () => {
    window.history.replaceState(null, "", "/live/join#invite=used-private-link&role=worker");
    vi.spyOn(api, "exchangeLiveInvitation").mockRejectedValue(
      new MeaningSyncApiError(
        "This joining invitation has already been used.",
        "invitation_used",
        false,
        409,
      ),
    );

    render(<LiveJoin />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Join as Service provider/ }),
    );

    expect(
      await screen.findByText("This joining invitation has already been used."),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "This link cannot be used" })).toBeVisible();
  });
});
