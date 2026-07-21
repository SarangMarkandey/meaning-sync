import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DemoSetup } from "@/components/demo-setup";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("DemoSetup", () => {
  beforeEach(() => push.mockReset());

  it("shows deterministic English and bilingual presets", () => {
    render(<DemoSetup />);

    expect(
      screen.getByRole("heading", { name: "Choose a prepared demo" }),
    ).toBeVisible();
    expect(screen.getByLabelText(/English Demo/)).toBeChecked();
    expect(screen.getByLabelText(/English \/ Hindi Demo/)).not.toBeChecked();
    expect(screen.getByText("English ↔ English")).toBeVisible();
    expect(screen.getAllByText("Demo setup")).toHaveLength(1);
  });

  it("starts the demo with both independent language values", () => {
    render(<DemoSetup />);

    fireEvent.click(screen.getByRole("button", { name: /Start Demo/ }));
    expect(push).toHaveBeenCalledWith(
      "/demo?hirer_language=en&worker_language=en&currency=INR",
    );
  });

  it("starts the prepared Hindi and English flow", () => {
    render(<DemoSetup />);

    fireEvent.click(screen.getByLabelText(/English \/ Hindi Demo/));
    expect(screen.getByText("Hindi ↔ English")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Start Demo/ }));
    expect(push).toHaveBeenCalledWith(
      "/demo?hirer_language=hi&worker_language=en&currency=INR",
    );
  });

  it("links back to the homepage", () => {
    render(<DemoSetup />);
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
