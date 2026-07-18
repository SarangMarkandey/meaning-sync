import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoExperience } from "@/components/demo-experience";
import { api } from "@/lib/api";

describe("DemoExperience", () => {
  afterEach(() => vi.restoreAllMocks());

  it("passes the selected languages into demo session creation", async () => {
    const createDemo = vi
      .spyOn(api, "createDemo")
      .mockImplementation(() => new Promise(() => undefined));

    render(
      <DemoExperience
        participantLanguages={{ hirer: "en", worker: "en" }}
        currency="INR"
      />,
    );

    await waitFor(() =>
      expect(createDemo).toHaveBeenCalledWith(
        { hirer: "en", worker: "en" },
        "INR",
      ),
    );
  });
});
