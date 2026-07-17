import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ClarityReceiptView } from "@/components/clarity-receipt-view";
import {
  api,
  MeaningSyncApiError,
  type AgreementTerm,
  type LiveClarityReceipt,
} from "@/lib/api";

const term = (state: AgreementTerm["state"], label: string): AgreementTerm => ({
  id: `${state}-${label}`,
  analysis_item_key: `${state}.detail`,
  topic: "other",
  facet: "detail",
  label,
  summary: `${label} recorded meaning.`,
  state,
  participant_positions: [],
  participant_confirmations: {
    hirer: state === "aligned" ? "confirmed" : "not_stated",
    worker: state === "aligned" ? "confirmed" : "not_stated",
  },
  evidence_message_ids: state === "not_discussed" ? [] : ["message-1"],
  evidence:
    state === "not_discussed"
      ? []
      : [
          {
            source: "transcript",
            reference_id: "message-1",
            participant_id: "hirer",
            role: "hirer",
            speaker_name: "Homeowner",
            message_id: "message-1",
            original_text: "The recorded statement.",
            original_language: "en",
            order: 1,
            timestamp: "2026-07-16T10:00:00Z",
          },
        ],
  clarification_target: null,
});

const integrityHash = "a".repeat(64);

const receipt: LiveClarityReceipt = {
  id: "receipt-123",
  session_id: "live-1",
  agreement_version_id: "version-2",
  agreement_version_number: 2,
  issued_at: "2026-07-16T11:00:00Z",
  participants: [
    { participant_id: "hirer", role: "hirer", display_name: "Homeowner", language: "en" },
    { participant_id: "worker", role: "worker", display_name: "Electrician", language: "en" },
  ],
  aligned_terms: [term("aligned", "Labour price")],
  unresolved_terms: [term("conflicting", "Materials inclusion")],
  one_sided_terms: [],
  not_applicable_terms: [
    {
      item_key: "warranty.coverage",
      label: "Warranty",
      summary: "No warranty applies to this repair.",
      proposed_by: ["hirer", "worker"],
    },
  ],
  not_discussed_terms: [term("not_discussed", "Completion time")],
  clarification_history: [
    {
      clarification_id: "clarification-1",
      target_item_key: "materials.inclusion",
      target_agreement_version_id: "version-1",
      resulting_agreement_version_id: "version-2",
      response_message_ids: { hirer: "c1", worker: "c2" },
      status: "still_unresolved",
      fingerprint: "materials-conflict",
      semantic_target: "materials inclusion",
    },
  ],
  understanding_status: [
    { participant_id: "hirer", review_id: "review-1", result: "completed", completed_at: "2026-07-16T10:50:00Z", question_ids: ["question-1"] },
    { participant_id: "worker", review_id: "review-2", result: "completed", completed_at: "2026-07-16T10:52:00Z", question_ids: ["question-1"] },
  ],
  confirmations: [
    { participant_id: "hirer", confirmation_id: "confirm-1", confirmed_at: "2026-07-16T10:55:00Z", language: "en" },
    { participant_id: "worker", confirmation_id: "confirm-2", confirmed_at: "2026-07-16T10:58:00Z", language: "en" },
  ],
  status: "contains_unresolved_items",
  application_version: "meaningsync-m4",
  schema_version: "clarity-receipt-v1",
  integrity_hash: integrityHash,
  disclaimer:
    "This clarity receipt records the participants’ stated understanding. MeaningSync does not provide legal advice, and this receipt is not presented as a legally enforceable contract.",
};

describe("ClarityReceiptView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not open a receipt before both confirmations", async () => {
    vi.spyOn(api, "getLiveReceipt").mockRejectedValue(
      new MeaningSyncApiError("Receipt is not ready.", "receipt_not_ready", false, 409),
    );
    render(<ClarityReceiptView sessionId="live-1" />);
    expect(await screen.findByRole("heading", { name: "Both participants must confirm first." })).toBeVisible();
    expect(screen.getByRole("link", { name: "Return to session" })).toHaveAttribute("href", "/live/live-1");
  });

  it("shows aligned and unresolved terms with the required warning", async () => {
    vi.spyOn(api, "getLiveReceipt").mockResolvedValue(receipt);
    render(<ClarityReceiptView sessionId="live-1" />);
    expect((await screen.findAllByText("Some points remain unresolved"))[0]).toBeVisible();
    expect(screen.getByText("Labour price recorded meaning.")).toBeVisible();
    expect(screen.getByText("Materials inclusion recorded meaning.")).toBeVisible();
    expect(screen.getByText("Completion time recorded meaning.")).not.toBeVisible();
    fireEvent.click(screen.getByText("Not discussed or proposed not applicable"));
    expect(screen.getByText("Completion time recorded meaning.")).toBeVisible();
    expect(screen.getByText(receipt.disclaimer)).toBeVisible();
    expect(screen.getByText(integrityHash)).not.toBeVisible();
    fireEvent.click(screen.getByText("Advanced details"));
    expect(screen.getByText(integrityHash)).toBeVisible();
    expect(screen.getByText(/not a digital signature/i)).toBeVisible();
  });

  it("distinguishes a fully aligned receipt", async () => {
    vi.spyOn(api, "getLiveReceipt").mockResolvedValue({
      ...receipt,
      status: "fully_aligned",
      unresolved_terms: [],
      not_discussed_terms: [],
    });
    render(<ClarityReceiptView sessionId="live-1" />);
    expect(await screen.findByRole("heading", { name: "Both people confirmed this understanding" })).toBeVisible();
    expect(screen.queryByText("Unresolved items remain unresolved")).not.toBeInTheDocument();
  });

  it("names each not-applicable detail and who marked it", async () => {
    vi.spyOn(api, "getLiveReceipt").mockResolvedValue(receipt);
    render(<ClarityReceiptView sessionId="live-1" />);
    fireEvent.click(await screen.findByText("Not discussed or proposed not applicable"));
    expect(screen.getByText("Warranty")).toBeVisible();
    expect(
      screen.getByText((_, element) =>
        element?.tagName === "P" &&
        Boolean(element.textContent?.includes("No warranty applies to this repair.")) &&
        Boolean(element.textContent?.includes("Homeowner and Electrician")),
      ),
    ).toBeVisible();
  });

  it("provides browser print/save and return-home actions", async () => {
    vi.spyOn(api, "getLiveReceipt").mockResolvedValue(receipt);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<ClarityReceiptView sessionId="live-1" />);
    const printActions = await screen.findAllByRole("button", { name: "Print / Save" });
    fireEvent.click(printActions[0]);
    expect(print).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
  });
});
