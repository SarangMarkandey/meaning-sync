import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("MeaningSync landing page", () => {
  it("keeps language setup and implementation text off the homepage", () => {
    render(<Home />);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByText("Demo languages")).not.toBeInTheDocument();
    expect(screen.queryByText("English-first milestone")).not.toBeInTheDocument();
  });

  it("routes Try Demo to setup and keeps Live Mode disabled", () => {
    render(<Home />);

    expect(screen.getByRole("link", { name: /Try Demo/ })).toHaveAttribute(
      "href",
      "/demo/setup",
    );
    expect(
      screen.getByRole("button", { name: /Start Live Session/ }),
    ).toBeDisabled();
    expect(screen.getByLabelText("Agreement map preview")).toBeVisible();
  });
});
