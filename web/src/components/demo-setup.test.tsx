import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DemoSetup } from "@/components/demo-setup";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("DemoSetup", () => {
  beforeEach(() => push.mockReset());

  it("shows independent participant controls defaulted to English", () => {
    render(<DemoSetup />);

    expect(
      screen.getByRole("heading", { name: "Choose the conversation languages" }),
    ).toBeVisible();
    expect(screen.getByText("Participant 1")).toBeVisible();
    expect(screen.getByText("Participant 2")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Homeowner" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Electrician" })).toBeVisible();
    const [homeownerLanguage, electricianLanguage] =
      screen.getAllByLabelText("Language");
    expect(homeownerLanguage).toHaveValue("en");
    expect(electricianLanguage).toHaveValue("en");
    expect(screen.getByText("English ↔ English")).toBeVisible();
    expect(screen.getAllByText("Demo setup")).toHaveLength(1);
  });

  it("starts the demo with both independent language values", () => {
    render(<DemoSetup />);

    fireEvent.click(screen.getByRole("button", { name: /Start Demo/ }));
    expect(push).toHaveBeenCalledWith(
      "/demo?hirer_language=en&worker_language=en",
    );
  });

  it("does not allow an unsupported Hindi flow to start", () => {
    render(<DemoSetup />);

    const [homeownerLanguage] = screen.getAllByLabelText("Language");
    for (const option of screen.getAllByRole("option", { name: /Hindi/ })) {
      expect(option).toBeDisabled();
    }
    fireEvent.change(homeownerLanguage, { target: { value: "hi" } });
    expect(screen.getByRole("button", { name: /Start Demo/ })).toBeDisabled();
    expect(push).not.toHaveBeenCalled();
  });

  it("links back to the homepage", () => {
    render(<DemoSetup />);
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
