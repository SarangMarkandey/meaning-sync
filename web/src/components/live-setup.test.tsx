import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSetup } from "@/components/live-setup";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("LiveSetup", () => {
  beforeEach(() => push.mockReset());

  it("shows independent English controls and disabled Hindi", () => {
    render(<LiveSetup />);

    const controls = screen.getAllByLabelText("Language");
    expect(controls).toHaveLength(2);
    expect(controls[0]).toHaveValue("en");
    expect(controls[1]).toHaveValue("en");
    for (const option of screen.getAllByRole("option", { name: /Hindi/ })) {
      expect(option).toBeDisabled();
    }
    expect(screen.getByText("English ↔ English")).toBeVisible();
    expect(screen.getByText(/No microphone/)).toBeVisible();
  });

  it("starts the supported live text preview", () => {
    render(<LiveSetup />);

    fireEvent.click(
      screen.getByRole("button", { name: /^Continue/ }),
    );
    expect(push).toHaveBeenCalledWith(
      "/live?hirer_language=en&worker_language=en",
    );
  });
});
