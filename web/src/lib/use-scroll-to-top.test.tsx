import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useScrollToTop } from "@/lib/use-scroll-to-top";

function FlowScreen({ transitionKey }: { transitionKey: string }) {
  useScrollToTop(transitionKey);
  return <main>{transitionKey}</main>;
}

describe("useScrollToTop", () => {
  beforeEach(() => {
    vi.mocked(window.scrollTo).mockClear();
  });

  it("resets the viewport when the flow advances to another screen", async () => {
    const view = render(<FlowScreen transitionKey="participation" />);
    await waitFor(() => expect(window.scrollTo).toHaveBeenCalled());
    vi.mocked(window.scrollTo).mockClear();

    view.rerender(<FlowScreen transitionKey="conversation" />);

    await waitFor(() =>
      expect(window.scrollTo).toHaveBeenCalledWith({
        top: 0,
        left: 0,
        behavior: "auto",
      }),
    );
  });

  it("does not reset the viewport for ordinary rerenders of one screen", async () => {
    const view = render(<FlowScreen transitionKey="conversation" />);
    await waitFor(() => expect(window.scrollTo).toHaveBeenCalled());
    vi.mocked(window.scrollTo).mockClear();

    view.rerender(<FlowScreen transitionKey="conversation" />);

    expect(window.scrollTo).not.toHaveBeenCalled();
  });
});
