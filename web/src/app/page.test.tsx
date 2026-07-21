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

  it("routes Demo and Live actions to their setup flows", () => {
    render(<Home />);

    expect(screen.getAllByRole("link", { name: /Try the demo/ })[0]).toHaveAttribute(
      "href",
      "/demo/setup",
    );
    expect(screen.getByRole("link", { name: /Start a live conversation/ })).toHaveAttribute(
      "href",
      "/live/setup",
    );
    expect(screen.getByLabelText("Example agreement map")).toBeVisible();
    expect(screen.getByText(/English and Hindi · Text and audio/)).toBeVisible();
  });
});
