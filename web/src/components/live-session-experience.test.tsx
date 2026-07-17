import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LiveSessionExperience } from "@/components/live-session-experience";
import {
  api,
  MeaningSyncApiError,
  type LiveSessionView,
  type PartyRole,
  type UnderstandingQuestion,
} from "@/lib/api";
import {
  guidance,
  guidedV5Session,
  guidedV5Terms,
  optionalTerms,
} from "@/test/fixtures/live-guided";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function question(
  overrides: Partial<UnderstandingQuestion> = {},
): UnderstandingQuestion {
  return {
    ...guidedV5Session().questions[0],
    ...overrides,
  };
}

function understandingQuestion(
  overrides: Partial<UnderstandingQuestion> = {},
): UnderstandingQuestion {
  return question({
    id: "understanding-price",
    agreement_item_id: "price.amount",
    kind: "understanding_check",
    prompt: "Which statement matches what you understood about the ₹1,200?",
    options: [
      {
        id: "labour-only",
        label: "It covers labour only; replacement parts cost extra",
        kind: "recorded_meaning",
      },
      {
        id: "labour-and-parts",
        label: "It covers labour and replacement parts",
        kind: "recorded_position",
      },
      { id: "price-other", label: "Something else", kind: "other" },
      { id: "price-unsure", label: "I’m not sure", kind: "unsure" },
    ],
    evidence_reference_ids: ["price.amount-hirer", "price.amount-worker"],
    addressed_participant_ids: ["hirer", "worker"],
    answered_participant_ids: [],
    responses_revealed: false,
    status: "pending",
    question_number: 1,
    question_count: 1,
    outcome: null,
    ...overrides,
  });
}

function participantReview(
  participant: PartyRole,
  status: "checking" | "completed" | "skipped" | "ready_to_confirm" =
    "checking",
) {
  return {
    id: `review-${participant}`,
    participant_id: participant,
    agreement_version_id: "version-5",
    status,
    completed_question_ids:
      status === "checking" || status === "skipped" ? [] : ["understanding-price"],
    created_at: "2026-07-17T10:05:00Z",
    completed_at: status === "checking" ? null : "2026-07-17T10:10:00Z",
  } as const;
}

function questionSession({
  actor = "hirer",
  activeQuestion = understandingQuestion(),
  overrides = {},
}: {
  actor?: PartyRole;
  activeQuestion?: UnderstandingQuestion;
  overrides?: Partial<LiveSessionView>;
} = {}): LiveSessionView {
  return guidedV5Session({
    stage: "awaiting_understanding_checks",
    questions: [activeQuestion],
    active_participant_id: actor,
    understanding_reviews: {
      hirer: participantReview("hirer"),
      worker: participantReview("worker"),
    },
    guidance: guidance({
      user_stage: "check_understanding",
      headline: "Check each person’s understanding",
      explanation:
        "Choose the meaning you understood. Your choice stays private until both people answer.",
      primary_action: "submit_selection",
      primary_label: "Submit my choice",
      secondary_action: "leave_unresolved",
      secondary_label: "Leave this unresolved",
      acting_participant: actor,
      active_question_id: activeQuestion.id,
      active_clarification_id:
        activeQuestion.kind === "clarification" ? activeQuestion.id : null,
      target_item_key: activeQuestion.agreement_item_id,
      required_issue_count: 0,
      required_item_keys: [],
    }),
    ...overrides,
  });
}

function finalReviewSession(): LiveSessionView {
  return guidedV5Session({
    stage: "ready_for_understanding_check",
    active_participant_id: null,
    questions: [],
    guidance: guidance({
      user_stage: "check_understanding",
      headline: "Review what MeaningSync recorded",
      explanation: "Review the final summary before the private understanding check.",
      primary_action: "start_understanding_check",
      primary_label: "Review final understanding",
      secondary_action: "review_optional_details",
      secondary_label: "Add optional details",
      acting_participant: null,
      active_question_id: null,
      active_clarification_id: null,
      target_item_key: null,
      required_issue_count: 0,
      required_item_keys: [],
    }),
  });
}

describe("LiveSessionExperience choice-based flow", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("renders the exact v5 state with one server-owned next action", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    const { container } = render(
      <LiveSessionExperience sessionId="live-guided-v5" />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Most of the conversation is clear",
      }),
    ).toBeVisible();
    expect(screen.getByText("4 things match")).toBeVisible();
    expect(screen.getByText("1 answer needed")).toBeVisible();
    expect(screen.getByText("5 optional details were not discussed")).toBeVisible();
    expect(container.querySelectorAll(".guided-task .button.primary")).toHaveLength(1);
    expect(screen.queryByText("Agreement Map v5")).not.toBeInTheDocument();
  });

  it("shows the five plain-language stages without truncating Review terminology", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    const progress = await screen.findByRole("navigation", {
      name: "Live session progress",
    });
    for (const label of [
      "Conversation",
      "Clarify",
      "Check understanding",
      "Confirm",
      "Receipt",
    ]) {
      expect(within(progress).getByText(label)).toBeVisible();
    }
    expect(within(progress).queryByText("Teach-back")).not.toBeInTheDocument();
  });

  it("uses stable option IDs for clarification and needs no text on the normal path", async () => {
    const initial = guidedV5Session();
    const completed = guidedV5Session({
      questions: [
        question({
          answered_participant_ids: ["hirer"],
          responses_revealed: true,
          status: "completed",
          outcome: {
            state: "aligned",
            positions: [
              {
                participant_id: "hirer",
                option_id: "scope-recorded",
                label: "Yes, the work is the fan and two switches",
              },
            ],
          },
        }),
      ],
      guidance: guidance({
        primary_action: "review_optional_details",
        primary_label: "Review optional details",
        secondary_action: null,
        secondary_label: null,
        acting_participant: null,
        active_question_id: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    const submit = vi
      .spyOn(api, "submitUnderstandingSelection")
      .mockResolvedValue(completed);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Leave this unresolved" }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByLabelText("Yes, the work is the fan and two switches"),
    );
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit.mock.calls[0][2]).toMatchObject({
      participant_id: "hirer",
      option_id: "scope-recorded",
      expected_agreement_version_id: "version-5",
    });
    expect(submit.mock.calls[0][2]).not.toHaveProperty("other_text");
  });

  it("keeps the first selection out of the second participant handoff", async () => {
    const shared = guidedV5Session({
      questions: [
        question({ addressed_participant_ids: ["hirer", "worker"] }),
      ],
    });
    const afterFirst = guidedV5Session({
      active_participant_id: "worker",
      questions: [
        question({
          addressed_participant_ids: ["hirer", "worker"],
          answered_participant_ids: ["hirer"],
          status: "partially_answered",
        }),
      ],
      guidance: guidance({ acting_participant: "worker" }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(shared);
    vi.spyOn(api, "submitUnderstandingSelection").mockResolvedValue(afterFirst);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    fireEvent.click(
      screen.getByLabelText("Yes, the work is the fan and two switches"),
    );
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));

    expect(
      await screen.findByRole("heading", { name: "Pass the device to Electrician." }),
    ).toBeVisible();
    expect(screen.getByText(/Homeowner chose privately/)).toBeVisible();
    expect(
      screen.queryByText("Yes, the work is the fan and two switches"),
    ).not.toBeInTheDocument();
    expect(afterFirst.questions[0].outcome).toBeNull();
  });

  it("shows one understanding question at a time with progress and no mandatory text", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(
      questionSession({
        activeQuestion: understandingQuestion({
          question_number: 1,
          question_count: 2,
        }),
      }),
    );
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    fireEvent.click(await screen.findByRole("button", { name: /I’m Homeowner — start/ }));
    expect(screen.getByText("Question 1 of 2")).toBeVisible();
    expect(
      screen.getAllByText(
        "Choose the meaning you understood. Your choice stays private until both people answer.",
      ),
    ).toHaveLength(2);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Leave this unresolved" }),
    ).not.toBeInTheDocument();
  });

  it("reveals short text only after Something else is selected", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(questionSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Homeowner — start/ }));
    fireEvent.click(screen.getByLabelText("Something else"));
    const other = screen.getByLabelText("Add a short explanation");
    expect(other).toBeRequired();
    expect(other).toHaveAttribute("maxlength", "280");
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeDisabled();
    fireEvent.change(other, { target: { value: "₹1,200 includes one replacement part." } });
  });

  it("shows uncertainty as unresolved rather than aligned", async () => {
    const initial = questionSession();
    const unsureQuestion = understandingQuestion({
      answered_participant_ids: ["hirer", "worker"],
      responses_revealed: true,
      status: "unsure",
      outcome: {
        state: "unsure",
        positions: [
          {
            participant_id: "hirer",
            option_id: "price-unsure",
            label: "I’m not sure",
          },
          {
            participant_id: "worker",
            option_id: "labour-only",
            label: "It covers labour only; replacement parts cost extra",
          },
        ],
      },
    });
    const after = questionSession({
      activeQuestion: unsureQuestion,
      overrides: {
        guidance: guidance({
          user_stage: "check_understanding",
          primary_action: "submit_selection",
          primary_label: "Choose again",
          secondary_action: "leave_unresolved",
          secondary_label: "Leave this unresolved",
          acting_participant: "hirer",
          active_question_id: unsureQuestion.id,
          active_clarification_id: null,
          target_item_key: "price.amount",
        }),
      },
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    vi.spyOn(api, "submitUnderstandingSelection").mockResolvedValue(after);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Homeowner — start/ }));
    fireEvent.click(screen.getByLabelText("I’m not sure"));
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));
    expect(
      await screen.findByRole("heading", { name: "This point is still unclear" }),
    ).toBeVisible();
    expect(screen.getByText("Uncertainty is not agreement. Review the recorded statements before choosing again or leaving this unresolved.")).toBeVisible();
  });

  it("reveals different positions neutrally only after both answer", async () => {
    const different = understandingQuestion({
      answered_participant_ids: ["hirer", "worker"],
      responses_revealed: true,
      status: "needs_clarification",
      outcome: {
        state: "different",
        positions: [
          { participant_id: "hirer", option_id: "labour-and-parts", label: "It covers labour and replacement parts" },
          { participant_id: "worker", option_id: "labour-only", label: "It covers labour only; replacement parts cost extra" },
        ],
      },
    });
    const initial = questionSession({ actor: "worker" });
    const retryClarification = understandingQuestion({
      id: "clarify-price-retry",
      kind: "clarification",
      prompt: "What will the recorded price cover?",
      answered_participant_ids: [],
      responses_revealed: false,
      status: "pending",
      outcome: null,
    });
    const after = questionSession({
      actor: "hirer",
      activeQuestion: retryClarification,
      overrides: {
        stage: "needs_clarification",
        questions: [different, retryClarification],
        guidance: guidance({
          user_stage: "clarify",
          primary_action: "submit_selection",
          primary_label: "Clarify this point",
          acting_participant: "hirer",
          active_question_id: retryClarification.id,
          active_clarification_id: retryClarification.id,
          target_item_key: "price.amount",
        }),
      },
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(initial);
    vi.spyOn(api, "submitUnderstandingSelection").mockResolvedValue(after);
    const leave = vi
      .spyOn(api, "leaveLiveQuestionUnresolved")
      .mockResolvedValue(after);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Electrician — start/ }));
    fireEvent.click(screen.getByLabelText("It covers labour only; replacement parts cost extra"));
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));

    expect(
      await screen.findByRole("heading", { name: "You understood this differently" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Recorded choices")).toHaveTextContent(
      "HomeownerIt covers labour and replacement parts",
    );
    expect(screen.getByLabelText("Recorded choices")).toHaveTextContent(
      "ElectricianIt covers labour only; replacement parts cost extra",
    );
    expect(
      screen.queryByRole("button", { name: "Leave it unresolved" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(
      await screen.findByRole("heading", { name: "Pass the device to Homeowner." }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /I’m Homeowner — start/ }));
    expect(
      screen.getByRole("button", { name: "Leave this unresolved" }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Leave this unresolved" }),
    );
    await waitFor(() => expect(leave).toHaveBeenCalledTimes(1));
    expect(leave.mock.calls[0][1]).toBe("clarify-price-retry");
  });

  it("shows a changed version when both choose the same alternative meaning", async () => {
    const base = questionSession();
    const current = base.agreement_versions[0];
    const changedVersion = {
      ...current,
      id: "version-6",
      version_number: 6,
      meaningful_version_number: 3,
      parent_version_id: current.id,
      changes: [
        {
          item_key: "price.amount",
          label: "Labour price",
          previous_state: "aligned" as const,
          current_state: "aligned" as const,
          resulting_meaning: "₹1,200 covers labour and replacement parts.",
          new_evidence_reference_ids: [],
        },
      ],
    };
    const changedQuestion = understandingQuestion({
      answered_participant_ids: ["hirer", "worker"],
      responses_revealed: true,
      status: "completed",
      outcome: {
        state: "meaning_changed",
        positions: [
          { participant_id: "hirer", option_id: "labour-and-parts", label: "It covers labour and replacement parts" },
          { participant_id: "worker", option_id: "labour-and-parts", label: "It covers labour and replacement parts" },
        ],
        resulting_agreement_version_id: "version-6",
      },
    });
    const after = questionSession({
      activeQuestion: changedQuestion,
      overrides: {
        agreement_versions: [current, changedVersion],
        current_agreement_version_id: "version-6",
        guidance: guidance({
          user_stage: "confirm",
          primary_action: "submit_confirmation",
          primary_label: "Review the change",
          acting_participant: "hirer",
          active_question_id: null,
          active_clarification_id: null,
          target_item_key: null,
        }),
      },
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(base);
    vi.spyOn(api, "submitUnderstandingSelection").mockResolvedValue(after);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Homeowner — start/ }));
    fireEvent.click(screen.getByLabelText("It covers labour and replacement parts"));
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));
    expect(
      await screen.findByRole("heading", { name: "The recorded meaning changed" }),
    ).toBeVisible();
    expect(screen.getByText("Updated: ₹1,200 covers labour and replacement parts.")).toBeVisible();
    expect(screen.getByRole("button", { name: /Continue/ })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /Submit my choice/ }),
    ).not.toBeInTheDocument();
  });

  it("reuses the same idempotency key when a selection retry fails", async () => {
    const state = guidedV5Session();
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    const submit = vi
      .spyOn(api, "submitUnderstandingSelection")
      .mockRejectedValueOnce(
        new MeaningSyncApiError("Please try again.", "request_failed", true, 503),
      )
      .mockResolvedValueOnce(state);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    fireEvent.click(screen.getByLabelText("Yes, the work is the fan and two switches"));
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please try again.");
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    expect(submit.mock.calls[0][2].request_id).toBe(
      submit.mock.calls[1][2].request_id,
    );
  });

  it("can skip directly to confirmation when no additional question is needed", async () => {
    const review = finalReviewSession();
    const skipped = guidedV5Session({
      stage: "awaiting_confirmations",
      questions: [],
      understanding_reviews: {
        hirer: participantReview("hirer", "skipped"),
        worker: participantReview("worker", "skipped"),
      },
      active_participant_id: "hirer",
      guidance: guidance({
        user_stage: "confirm",
        headline: "The important difference is already clarified",
        explanation: "The completed clarification already covered the important difference, so no additional understanding question was needed. Each person can now confirm this exact version.",
        primary_action: "submit_confirmation",
        primary_label: "Confirm my understanding",
        secondary_action: null,
        secondary_label: null,
        acting_participant: "hirer",
        active_question_id: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(review);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(review);
    vi.spyOn(api, "beginUnderstandingCheck").mockResolvedValue(skipped);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Review final understanding/ }));
    fireEvent.click(await screen.findByText(/I reviewed this section/));
    fireEvent.click(screen.getByRole("button", { name: /Check each person’s understanding/ }));
    expect(
      await screen.findByRole("heading", { name: "Pass the device to Homeowner." }),
    ).toBeVisible();
    const skipHeadline = screen.getByText(
      "The important difference is already clarified",
    );
    const skipNotice = skipHeadline.parentElement;
    expect(skipHeadline).toBeVisible();
    expect(skipNotice).not.toBeNull();
    expect(
      within(skipNotice!).getByText(
        /The completed clarification already covered the important difference/,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/Question 1 of/)).not.toBeInTheDocument();
  });

  it("shows one final-check copy after a completed clarification", async () => {
    const ready = guidedV5Session({
      stage: "ready_for_understanding_check",
      questions: [],
      active_participant_id: null,
      guidance: guidance({
        user_stage: "check_understanding",
        headline: "One final understanding check",
        explanation: "The important difference is already clarified. MeaningSync will ask at most one final question before separate confirmation.",
        primary_action: "start_understanding_check",
        primary_label: "One final understanding check",
        secondary_action: null,
        secondary_label: null,
        acting_participant: null,
        active_question_id: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(ready);

    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    expect(
      await screen.findByRole("button", {
        name: /One final understanding check/,
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/will ask at most one final question/),
    ).toBeVisible();
  });

  it("keeps optional details grouped and outside the mandatory question flow", async () => {
    const optional = guidedV5Session({
      guidance: guidance({
        primary_action: "review_optional_details",
        primary_label: "Review optional details",
        required_issue_count: 0,
        required_item_keys: [],
        acting_participant: null,
        active_question_id: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(optional);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(finalReviewSession());
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    expect(await screen.findByRole("heading", { name: "Add anything else?" })).toBeVisible();
    for (const term of optionalTerms) {
      expect(screen.getByRole("heading", { name: term.label })).toBeVisible();
    }
    expect(screen.queryByText(/Question 1 of/)).not.toBeInTheDocument();
  });

  it("binds separate confirmation to the participant understanding review", async () => {
    const state = guidedV5Session({
      stage: "awaiting_confirmations",
      questions: [],
      understanding_reviews: {
        hirer: participantReview("hirer", "ready_to_confirm"),
        worker: participantReview("worker", "ready_to_confirm"),
      },
      active_participant_id: "worker",
      confirmations: [
        {
          id: "confirmation-hirer",
          participant_id: "hirer",
          agreement_version_id: "version-5",
          understanding_review_id: "review-hirer",
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
        active_question_id: null,
        active_clarification_id: null,
        target_item_key: null,
      }),
    });
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    const submit = vi.spyOn(api, "submitLiveConfirmation").mockResolvedValue(state);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /I’m Electrician/ }));
    fireEvent.click(screen.getByText(/I understand the receipt/));
    fireEvent.click(screen.getByRole("button", { name: /Confirm my understanding/ }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit.mock.calls[0][1]).toMatchObject({
      participant_id: "worker",
      understanding_review_id: "review-worker",
      expected_agreement_version_id: "version-5",
    });
  });

  it("shows controlled stale-version recovery without advancing the question", async () => {
    vi.spyOn(api, "getLiveSession").mockResolvedValue(guidedV5Session());
    vi.spyOn(api, "submitUnderstandingSelection").mockRejectedValue(
      new MeaningSyncApiError(
        "Agreement version changed",
        "stale_agreement_version",
        false,
        409,
      ),
    );
    render(<LiveSessionExperience sessionId="live-guided-v5" />);

    fireEvent.click(await screen.findByRole("button", { name: /Answer 1 question/ }));
    fireEvent.click(
      screen.getByLabelText("Yes, the work is the fan and two switches"),
    );
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This understanding changed");
    expect(alert).toHaveTextContent("review the latest recorded meaning");
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeVisible();
  });

  it("shows controlled missing-session recovery", async () => {
    vi.spyOn(api, "getLiveSession").mockRejectedValue(
      new MeaningSyncApiError(
        "Session not found",
        "session_not_found",
        false,
        404,
      ),
    );
    render(<LiveSessionExperience sessionId="missing" />);
    expect(
      await screen.findByRole("heading", {
        name: "This live session is no longer available.",
      }),
    ).toBeVisible();
    expect(screen.getByText(/stored only for this server run/i)).toBeVisible();
  });

  it("shows every term once in final review and keeps advanced history collapsed", async () => {
    const state = finalReviewSession();
    vi.spyOn(api, "getLiveSession").mockResolvedValue(state);
    vi.spyOn(api, "reviewOptionalDetails").mockResolvedValue(state);
    render(<LiveSessionExperience sessionId="live-guided-v5" />);
    fireEvent.click(await screen.findByRole("button", { name: /Review final understanding/ }));
    await screen.findByRole("heading", { name: "Review what MeaningSync recorded" });
    for (const term of guidedV5Terms) {
      expect(screen.getAllByText(term.summary)).toHaveLength(1);
    }
    expect(screen.getByText("Version history")).not.toBeVisible();
  });
});
