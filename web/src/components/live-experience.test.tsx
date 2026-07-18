import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LiveExperience } from "@/components/live-experience";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("LiveExperience compatibility entry", () => {
  it("routes the legacy entry into the canonical Preferences setup", () => {
    render(
      <LiveExperience participantLanguages={{ hirer: "en", worker: "en" }} />,
    );
    expect(screen.getByRole("heading", { name: "Set up the conversation" })).toBeVisible();
    expect(screen.getAllByText("Preferences").length).toBeGreaterThan(0);
  });
});
