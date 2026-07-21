import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSetup } from "@/components/live-setup";
import { api, type LiveSessionCreateResult } from "@/lib/api";
import { guidedV5Session } from "@/test/fixtures/live-guided";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("LiveSetup", () => {
  beforeEach(() => push.mockReset());

  it("shows independent English and Hindi controls with currency", () => {
    render(<LiveSetup />);

    const controls = screen.getAllByLabelText("Language");
    expect(controls).toHaveLength(2);
    expect(controls[0]).toHaveValue("en");
    expect(controls[1]).toHaveValue("en");
    for (const option of screen.getAllByRole("option", { name: /Hindi/ })) {
      expect(option).toBeEnabled();
    }
    expect(screen.getByRole("combobox", { name: /Session currency/ })).toHaveValue("INR");
    expect(screen.getByText(/No currency conversion/)).toBeVisible();
  });

  it("moves from Preferences to Participation without creating early", () => {
    render(<LiveSetup />);
    fireEvent.click(screen.getByRole("button", { name: /^Continue/ }));
    expect(screen.getByRole("heading", { name: "Who are you?" })).toBeVisible();
    expect(screen.getByLabelText("I am the Customer")).toBeChecked();
    expect(screen.getByLabelText(/What should MeaningSync call you/)).toBeVisible();
    expect(push).not.toHaveBeenCalled();
  });

  it("creates a durable invitation before opening separate-device waiting", async () => {
    const created: LiveSessionCreateResult = {
      ...guidedV5Session({
        id: "separate-1",
        stage: "conversation_draft",
        messages: [],
        participation_mode: "separate_devices",
        viewer_role: "hirer",
      }),
      access_credentials: [
        {
          role: "hirer",
          access_token: "host-access-token-123456789012345678901234",
          expires_at: "2026-07-18T10:00:00Z",
        },
      ],
      invitation: {
        role: "worker",
        invitation: "private-invite-1234567890123456789012345678",
        expires_at: "2026-07-17T10:15:00Z",
      },
    };
    const create = vi.spyOn(api, "createLiveSession").mockResolvedValue(created);
    render(<LiveSetup />);

    fireEvent.click(screen.getByRole("button", { name: /^Continue/ }));
    fireEvent.click(screen.getByLabelText(/Use separate devices/));
    fireEvent.click(screen.getByRole("button", { name: /Start conversation/ }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0][0]).toMatchObject({
      messages: [],
      participation_mode: "separate_devices",
      currency: "INR",
      creator_role: "hirer",
    });
    expect(push).toHaveBeenCalledWith(
      expect.stringMatching(/^\/live\/separate-1\/waiting#invite=.*&role=worker$/),
    );
    expect(sessionStorage.getItem("meaningsync.live.separate-1.hirer")).toBe(
      "host-access-token-123456789012345678901234",
    );
  });
});
