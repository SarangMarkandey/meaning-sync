import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmationSummary } from "@/components/confirmation-summary";
import { ChatMessageList } from "@/components/conversation-view";
import { guidedV5Terms } from "@/test/fixtures/live-guided";

describe("bilingual participant views", () => {
  it("keeps original Hindi visible above a ready English translation", () => {
    render(
      <ChatMessageList
        preferredLanguage="en"
        messages={[
          {
            id: "message-hi",
            role: "hirer",
            roleName: "Sarang · Customer",
            text: "काम आज शुरू हो सकता है।",
            originalLanguage: "hi",
            translatedText: "The work can start today.",
            translationLanguage: "en",
            translationStatus: "ready",
            order: 1,
          },
        ]}
      />,
    );
    expect(screen.getByText("काम आज शुरू हो सकता है।")).toHaveAttribute("lang", "hi");
    expect(screen.getByText("The work can start today.")).toHaveAttribute("lang", "en");
    expect(screen.getByText("Sarang · Customer")).toBeVisible();
  });

  it("shows a safe retry without replacing failed original evidence", () => {
    const retry = vi.fn();
    render(
      <ChatMessageList
        preferredLanguage="hi"
        onRetryTranslation={retry}
        messages={[
          {
            id: "message-en",
            role: "worker",
            roleName: "Service provider",
            text: "Replacement parts are separate.",
            originalLanguage: "en",
            translationStatus: "failed",
            order: 1,
          },
        ]}
      />,
    );
    expect(screen.getByText("Replacement parts are separate.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "अनुवाद फिर से करें" }));
    expect(retry).toHaveBeenCalledWith("message-en");
  });

  it("renders the same semantic confirmation terms in Hindi", () => {
    const terms = guidedV5Terms.map((term) => ({
      ...term,
      localizations: {
        hi: {
          language: "hi" as const,
          label: "मजदूरी की कीमत",
          summary: "मजदूरी की कीमत ₹1,200 है।",
          participant_positions: [],
          provenance: "fixture",
        },
      },
    }));
    render(<ConfirmationSummary terms={terms} language="hi" />);
    expect(screen.getAllByText("मजदूरी की कीमत").length).toBeGreaterThan(0);
    expect(screen.getAllByText("मजदूरी की कीमत ₹1,200 है।").length).toBeGreaterThan(0);
  });
});
