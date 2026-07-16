import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveSessionExperience } from "@/components/live-session-experience";
import {
  api,
  MeaningSyncApiError,
  type TeachbackComparisonState,
} from "@/lib/api";
import {
  guidance,
  guidedV5Session,
  guidedV5Terms,
  optionalTerms,
  requiredScope,
} from "@/test/fixtures/live-guided";

const push = vi.fn();
const privateTeachbackText =
  "The work is the fan and switches for ₹1,200, with parts extra.";
const pendingWarrantyProposal = {
  item_key: "warranty.coverage",
  label: "Warranty",
  summary: "The Homeowner says a warranty does not apply.",
  proposed_by: ["hirer" as const],
};
const mutualCancellationProposal = {
  item_key: "cancellation.policy",
  label: "Cancellation",
  summary: "Both people say cancellation does not apply.",
  proposed_by: ["hirer" as const, "worker" as const],
};
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function finalReviewSession() {
  return guidedV5Session({
    stage: "ready_for_review",
    active_participant_id: null,
    guidance: guidance({
      user_stage: "review",
      headline: "Review what MeaningSync recorded",
      explanation: "Review the final summary, then check each person’s understanding.",
      primary_action: "review_final_understanding",
      primary_label: "Review final understanding",
      secondary_action: "review_optional_details",
      secondary_label: "Add optional details",
      acting_participant: null,
      active_clarification_id: null,
      target_item_key: null,
      required_issue_count: 0,
      required_item_keys: [],
    }),
  });
}

const teachback = (
  participant: "hirer" | "worker",
  state: TeachbackComparisonState = "matches",
) => ({
  id: `teachback-${participant}`,
  participant_id: participant,
  agreement_version_id: "version-5",
  original_language: "en" as const,
  covered_item_keys: ["scope.work", "price.amount", "materials.inclusion"],
  item_results: [
    {
      analysis_item_key: "materials.inclusion",
      state,
      agreement_summary: "Parts cost extra after approval.",
      feedback: state === "matches" ? "Matches." : "Say who pays for parts.",
    },
  ],
  overall_state: state,
  missing_or_contradictory_summary:
    state === "matches" ? null : "One detail is missing.",
  follow_up_question: state === "matches" ? null : "Who pays for replacement parts?",
  acknowledged_unresolved_item_keys: [
    "scope.work",
    ...optionalTerms.map((item) => item.analysis_item_key),
  ],
  created_at: "2026-07-17T10:10:00Z",
});

describe("LiveSessionExperience guided flow", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("renders the exact v5 state as a concise 4/1/5 summary with one primary action", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    const { container } = render(
      <LiveSessionExperience sessionId="live-guided-v5" />,
    );

    expect(await screen.findByRole("heading", { name: "Most of the conversation is clear" })).toBeVisible();
    expect(screen.getByText("4 things match")).toBeVisible();
    expect(screen.getByText("1 answer needed")).toBeVisible();
    expect(screen.getByText("5 optional details were not discussed")).toBeVisible();
    expect(container.querySelectorAll(".guided-task .button.primary")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Answer 1 question/ })).toBeVisible();
    expect(screen.queryByText("Agreement Map v5")).not.toBeInTheDocument();
    expect(screen.queryByText("Work scope")).not.toBeInTheDocument();
  });

  it("shows five human stages and the guidance explanation beside them", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    const progress = await screen.findByRole("navigation", { name: "Live session progress" });
    for (const label of ["Conversation", "Clarify", "Review", "Confirm", "Receipt"]) {
      expect(within(progress).getByText(label)).toBeVisible();
    }
    expect(screen.getByText("Answer one scope question, then choose whether to add optional details.")).toBeVisible();
  });

  it("opens only the required scope clarification with large answer choices", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));

    expect(screen.getByRole("heading", { name: /do you also understand the work/i })).toBeVisible();
    expect(screen.getByText(/Electrician: The Electrician offered/)).toBeVisible();
    expect(screen.getByLabelText("Yes, the work is the fan and two switches")).toBeVisible();
    expect(screen.queryByText("scope.work")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Completion time" })).not.toBeInTheDocument();
  });

  it("submits one participant answer and hides it during handoff", async () => {
    const initial = guidedV5Session();
    const hiddenAnswer = "Yes, the work is the fan and two switches";
    const afterFirst = guidedV5Session({
      active_participant_id: "worker",
      guidance: guidance({ acting_participant: "worker" }),
      clarifications: [
        {
          ...initial.clarifications[0],
          addressed_participant_ids: ["hirer", "worker"],
          answers_received_from: ["hirer"],
          response_message_ids: {},
          status: "answered",
        },
      ],
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    const submit = vi.spyOn(api, "submitLiveClarificationAnswer").mockResolvedValue(afterFirst);
    const { container } = render(
      <LiveSessionExperience sessionId="live-guided-v5" />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    fireEvent.click(screen.getByLabelText(hiddenAnswer));
    fireEvent.click(screen.getByRole("button", { name: /Submit my answer/ }));

    expect(await screen.findByRole("heading", { name: "Pass the device to Electrician." })).toBeVisible();
    await waitFor(() =>
      expect(container.querySelector(".guided-focus-target")).toHaveFocus(),
    );
    expect(screen.getByText(/Homeowner answered/)).toBeVisible();
    expect(screen.queryByText(hiddenAnswer)).not.toBeInTheDocument();
    expect(submit.mock.calls[0][2]).toMatchObject({
      participant_id: "hirer",
      expected_agreement_version_id: "version-5",
    });
  });

  it("starts a fresh below-limit retry instead of treating old answers as a new handoff", async () => {
    const base = guidedV5Session();
    const retry = guidedV5Session({
      guidance: guidance({
        primary_action: "answer_clarification",
        primary_label: "Try one final clarification",
        acting_participant: "hirer",
      }),
      clarifications: [
        {
          ...base.clarifications[0],
          addressed_participant_ids: ["hirer", "worker"],
          answers_received_from: ["hirer", "worker"],
          response_message_ids: {},
          status: "still_unresolved",
          attempt_number: 2,
        },
      ],
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(retry);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    expect(await screen.findByRole("heading", { name: "Pass the device to Homeowner." })).toBeVisible();
    expect(screen.getByText(/earlier answers were still different/i)).toBeVisible();
    expect(screen.queryByText(/Homeowner answered/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /I’m Homeowner — try again/ }));
    expect(screen.getByRole("heading", { name: /do you also understand the work/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /Submit my answer/ })).toBeDisabled();
  });

  it("shows only new supporting evidence for a meaningful clarification update", async () => {
    const initial = guidedV5Session();
    const newEvidence = {
      ...requiredScope.evidence[0],
      source: "clarification" as const,
      reference_id: "scope-new-evidence",
      participant_id: "hirer",
      role: "hirer" as const,
      speaker_name: "Homeowner",
      message_id: "scope-new-evidence",
      original_text: "Yes, the work is repairing the fan and two switches.",
    };
    const resolvedScope = {
      ...requiredScope,
      state: "aligned" as const,
      summary: "Both people confirmed the work is repairing the fan and two switches.",
      participant_positions: [
        ...requiredScope.participant_positions,
        {
          participant_id: "hirer",
          role: "hirer" as const,
          summary: "The work is repairing the fan and two switches.",
          evidence_message_ids: ["scope-new-evidence"],
        },
      ],
      participant_confirmations: {
        hirer: "confirmed" as const,
        worker: "confirmed" as const,
      },
      evidence_message_ids: [
        ...requiredScope.evidence_message_ids,
        "scope-new-evidence",
      ],
      evidence: [...requiredScope.evidence, newEvidence],
      clarification_target: null,
    };
    const previous = initial.agreement_versions[0];
    const changed = {
      ...previous,
      id: "version-6",
      version_number: 6,
      meaningful_version_number: 3,
      parent_version_id: previous.id,
      terms: previous.terms.map((term) =>
        term.analysis_item_key === "scope.work" ? resolvedScope : term,
      ),
      unresolved_item_keys: optionalTerms.map(
        (term) => term.analysis_item_key,
      ),
      changes: [
        {
          item_key: "scope.work",
          label: "Work scope",
          previous_state: "stated_by_one" as const,
          current_state: "aligned" as const,
          resulting_meaning: resolvedScope.summary,
          new_evidence_reference_ids: ["scope-new-evidence"],
        },
      ],
    };
    const resolved = guidedV5Session({
      stage: "ready_for_review",
      agreement_versions: [previous, changed],
      current_agreement_version_id: changed.id,
      active_participant_id: null,
      clarifications: [
        {
          ...initial.clarifications[0],
          answers_received_from: ["hirer"],
          status: "resolved",
          responses_revealed: true,
          resolved_at: "2026-07-17T10:05:00Z",
          resulting_agreement_version_id: changed.id,
        },
      ],
      guidance: guidance({
        user_stage: "review",
        primary_action: "review_final_understanding",
        primary_label: "Review final understanding",
        secondary_action: "review_optional_details",
        secondary_label: "Add optional details",
        required_issue_count: 0,
        required_item_keys: [],
        acting_participant: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    vi.spyOn(api, "submitLiveClarificationAnswer").mockResolvedValue(resolved);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    fireEvent.click(
      screen.getByLabelText("Yes, the work is the fan and two switches"),
    );
    fireEvent.click(screen.getByRole("button", { name: /Submit my answer/ }));

    expect(await screen.findByRole("heading", { name: "This detail is now clear" })).toBeVisible();
    expect(screen.getByText(`Updated: ${resolvedScope.summary}`)).toBeVisible();
    expect(screen.getByText(newEvidence.original_text)).not.toBeVisible();
    fireEvent.click(screen.getByText("New supporting evidence"));
    expect(screen.getByText(newEvidence.original_text)).toBeVisible();
    expect(screen.queryByText("scope-new-evidence")).not.toBeInTheDocument();
  });

  it("can explicitly leave the one required point unresolved", async () => {
    const initial = guidedV5Session();
    const optional = guidedV5Session({
      guidance: guidance({
        primary_action: "review_optional_details",
        primary_label: "Review optional details",
        secondary_action: null,
        secondary_label: null,
        required_issue_count: 0,
        required_item_keys: [],
        active_clarification_id: null,
        target_item_key: null,
        acting_participant: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    const leave = vi.spyOn(api, "leaveLiveClarificationUnresolved").mockResolvedValue(optional);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: "Continue with this unresolved" }));
    await waitFor(() => expect(leave).toHaveBeenCalledWith(
      "live-guided-v5",
      "clarification-scope",
      expect.objectContaining({ expected_agreement_version_id: "version-5" }),
    ));
    expect(await screen.findByRole("heading", { name: "Add anything else?" })).toBeVisible();
  });

  it("shows no answer form when the clarification limit requires leaving the point open", async () => {
    const base = guidedV5Session();
    const limited = guidedV5Session({
      guidance: guidance({
        primary_action: "leave_unresolved",
        primary_label: "Leave this unresolved",
        secondary_action: null,
        secondary_label: null,
        acting_participant: null,
      }),
      clarifications: [
        {
          ...base.clarifications[0],
          answers_received_from: ["hirer"],
          status: "still_unresolved",
          attempt_number: 3,
        },
      ],
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(limited);
    const leave = vi.spyOn(api, "leaveLiveClarificationUnresolved").mockResolvedValue(limited);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    expect(await screen.findByRole("heading", { name: "This point is still different" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /Submit my answer/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Leave this unresolved/ }));
    await waitFor(() => expect(leave).toHaveBeenCalledTimes(1));
  });

  it("skips all optional details with one review marker call", async () => {
    const optional = guidedV5Session({
      guidance: guidance({
        primary_action: "review_optional_details",
        primary_label: "Review optional details",
        required_issue_count: 0,
        required_item_keys: [],
        active_clarification_id: null,
        target_item_key: null,
        acting_participant: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(optional);
    const add = vi.spyOn(api, "addLiveStatements").mockResolvedValue(optional);
    const reviewed = vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(finalReviewSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: "Skip optional details" }));
    await waitFor(() => expect(reviewed).toHaveBeenCalledTimes(1));
    expect(add).not.toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Review what MeaningSync recorded" })).toBeVisible();
  });

  it("batches optional statements into one re-analysis and keeps not-applicable separate", async () => {
    const optional = guidedV5Session({
      guidance: guidance({
        primary_action: "review_optional_details",
        primary_label: "Review optional details",
        required_issue_count: 0,
        required_item_keys: [],
        active_clarification_id: null,
        target_item_key: null,
        acting_participant: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(optional);
    const add = vi.spyOn(api, "addLiveStatements").mockResolvedValue(optional);
    const propose = vi.spyOn(api, "proposeNotApplicable").mockResolvedValue(optional);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(finalReviewSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    await screen.findByRole("heading", { name: "Add anything else?" });

    const completion = screen.getByRole("heading", { name: "Completion time" }).closest("article")!;
    fireEvent.click(within(completion).getByRole("button", { name: "Add detail" }));
    fireEvent.change(within(completion).getByLabelText("Completion time detail"), { target: { value: "Finish by 5 pm." } });

    const payment = screen.getByRole("heading", { name: "Payment timing" }).closest("article")!;
    fireEvent.click(within(payment).getByRole("button", { name: "Add detail" }));
    fireEvent.change(within(payment).getByLabelText("Payment timing detail"), { target: { value: "Pay after completion." } });

    const warranty = screen.getByRole("heading", { name: "Warranty" }).closest("article")!;
    fireEvent.click(within(warranty).getByRole("button", { name: "Not applicable" }));
    fireEvent.click(within(warranty).getByLabelText("Homeowner"));
    expect(within(warranty).getByText(/remains pending for the other person/)).toBeVisible();
    fireEvent.click(within(warranty).getByLabelText("Electrician"));
    fireEvent.click(screen.getByRole("button", { name: /Review final understanding/ }));

    await waitFor(() => expect(add).toHaveBeenCalledTimes(1));
    expect(add.mock.calls[0][1].messages).toHaveLength(2);
    expect(propose).toHaveBeenCalledTimes(2);
  });

  it("shows each term once at final review and keeps meaningful history collapsed", async () => {
    const base = finalReviewSession();
    const meaningful = base.agreement_versions[0];
    const noOpCurrent = {
      ...meaningful,
      id: "version-6-no-op",
      version_number: 6,
      parent_version_id: meaningful.id,
      has_meaningful_change: false,
      not_applicable_proposals: [
        pendingWarrantyProposal,
        mutualCancellationProposal,
      ],
    };
    const state = {
      ...base,
      agreement_versions: [meaningful, noOpCurrent],
      current_agreement_version_id: noOpCurrent.id,
    };
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(state);
    vi.spyOn(api, "beginLiveReview").mockResolvedValue({
      ...state,
      stage: "awaiting_teachbacks",
      active_participant_id: "hirer",
      guidance: guidance({
        user_stage: "review",
        primary_action: "submit_teachback",
        primary_label: "Submit my explanation",
        secondary_action: null,
        secondary_label: null,
        acting_participant: "hirer",
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Review final understanding/ }));
    await screen.findByRole("heading", { name: "Review what MeaningSync recorded" });
    for (const term of guidedV5Terms) {
      expect(screen.getAllByText(term.summary)).toHaveLength(1);
    }
    fireEvent.click(screen.getByText("Not discussed"));
    expect(screen.getByText("Warranty marked not applicable")).toBeVisible();
    expect(screen.getByText(pendingWarrantyProposal.summary)).toBeVisible();
    expect(screen.getByText(/still pending for Electrician/)).toBeVisible();
    expect(screen.getByText("4 optional details left open")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Both marked not applicable" })).toBeVisible();
    expect(screen.getByText(mutualCancellationProposal.summary)).toBeVisible();
    expect(screen.getByText("Version history")).not.toBeVisible();
    fireEvent.click(screen.getByText("Advanced details"));
    expect(screen.getByText("Version history")).toBeVisible();
    expect(screen.queryByText("version-5")).not.toBeInTheDocument();
    expect(screen.getAllByText("Recorded understanding 2 · current")).toHaveLength(1);
    fireEvent.click(screen.getByText(/I reviewed this section/));
    fireEvent.click(
      screen.getByRole("button", {
        name: /Check each person’s understanding/,
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Pass the device to Homeowner.",
      }),
    ).toBeVisible();
  });

  it("checks understanding one participant at a time and asks only the focused follow-up", async () => {
    const state = guidedV5Session({
      stage: "awaiting_teachbacks",
      teachbacks: [teachback("hirer", "partially_matches")],
      guidance: guidance({
        user_stage: "review",
        primary_action: "submit_teachback",
        primary_label: "Submit my explanation",
        secondary_action: null,
        secondary_label: null,
        acting_participant: "hirer",
        active_clarification_id: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Homeowner/ }));
    expect(screen.getByRole("heading", { name: "One detail is missing from your explanation." })).toBeVisible();
    expect(screen.getByLabelText("Who pays for replacement parts?")).toBeVisible();
    expect(screen.queryByText(privateTeachbackText)).not.toBeInTheDocument();
  });

  it("identifies the acting confirmation participant and never exposes the first answer", async () => {
    const base = guidedV5Session();
    const state = guidedV5Session({
      stage: "awaiting_confirmations",
      agreement_versions: [
        {
          ...base.agreement_versions[0],
          not_applicable_proposals: [
            pendingWarrantyProposal,
            mutualCancellationProposal,
          ],
        },
      ],
      teachbacks: [teachback("hirer"), teachback("worker")],
      confirmations: [
        {
          id: "confirmation-hirer",
          participant_id: "hirer",
          agreement_version_id: "version-5",
          teachback_id: "teachback-hirer",
          unresolved_item_acknowledgments: [],
          confirmed_at: "2026-07-17T10:20:00Z",
          language: "en",
          request_id: "request-confirm-hirer",
          invalidated_at: null,
        },
      ],
      guidance: guidance({
        user_stage: "confirm",
        primary_action: "submit_confirmation",
        primary_label: "Confirm my understanding",
        secondary_action: null,
        secondary_label: null,
        acting_participant: "worker",
        active_clarification_id: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    const submit = vi.spyOn(api, "submitLiveConfirmation").mockResolvedValue(state);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Electrician/ }));
    expect(screen.getByRole("heading", { name: "Confirm your understanding" })).toBeVisible();
    expect(screen.getByText("Warranty marked not applicable")).toBeVisible();
    expect(screen.getByText(/still pending for Electrician/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Both marked not applicable" })).toBeVisible();
    expect(screen.getByText(mutualCancellationProposal.summary)).toBeVisible();
    expect(screen.queryByText(privateTeachbackText)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/I understand the receipt/));
    fireEvent.click(screen.getByRole("button", { name: /Confirm my understanding/ }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(submit.mock.calls[0][1]).toMatchObject({ participant_id: "worker" });
    expect(submit.mock.calls[0][1].expected_agreement_version_id).toBe("version-5");
  });

  it("treats only the stale-version code as stale when handling 409 errors", async () => {
    const state = finalReviewSession();
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(state);
    vi.spyOn(api, "beginLiveReview").mockRejectedValue(
      new MeaningSyncApiError("Review is not ready.", "invalid_state", false, 409),
    );
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Review final understanding/ }));
    await screen.findByRole("heading", { name: "Review what MeaningSync recorded" });
    fireEvent.click(await screen.findByText(/I reviewed this section/));
    fireEvent.click(screen.getByRole("button", { name: /Check each person’s understanding/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That step could not be completed");
    expect(screen.getByRole("alert")).toHaveTextContent("Review is not ready.");
    expect(screen.queryByText("This understanding changed")).not.toBeInTheDocument();
  });

  it("truthfully recovers when the in-memory session is missing", async () => {
    vi.spyOn(api, "getLiveSession").mockRejectedValue(
      new MeaningSyncApiError("Session not found", "session_not_found", false, 404),
    );
    render(<LiveSessionExperience sessionId="missing" />);
    expect(await screen.findByRole("heading", { name: "This live session is no longer available." })).toBeVisible();
    expect(screen.getByText(/stored only for this server run/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Start a new live session" })).toHaveAttribute("href", "/live/setup");
  });
});
