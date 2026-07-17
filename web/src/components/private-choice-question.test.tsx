import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  OTHER_TEXT_MAX_LENGTH,
  PrivateChoiceQuestion,
  type ChoiceOptionView,
} from "@/components/private-choice-question";

const options: ChoiceOptionView[] = [
  { id: "recorded", label: "Labour only; parts cost extra", kind: "recorded_meaning" },
  { id: "other", label: "Something else", kind: "other" },
  { id: "unsure", label: "I’m not sure", kind: "unsure" },
];

function renderQuestion({
  optionId = "",
  otherText = "",
}: {
  optionId?: string;
  otherText?: string;
} = {}) {
  const onSelect = vi.fn();
  const onOtherTextChange = vi.fn();
  const onSubmit = vi.fn();
  render(
    <PrivateChoiceQuestion
      actorName="Homeowner"
      explanation="Choose the meaning you understood. Your choice stays private until both people answer."
      eyebrow="Choose one meaning"
      onOtherTextChange={onOtherTextChange}
      onSelect={onSelect}
      onSubmit={onSubmit}
      optionId={optionId}
      options={options}
      otherText={otherText}
      prompt="Which statement matches what you understood?"
      questionCount={2}
      questionId="question-1"
      questionNumber={1}
      saving={false}
    />,
  );
  return { onOtherTextChange, onSelect, onSubmit };
}

describe("PrivateChoiceQuestion", () => {
  it("offers accessible choices without free text on the normal path", () => {
    const { onSelect } = renderQuestion();

    expect(screen.getByText("Question 1 of 2")).toBeVisible();
    expect(screen.getByRole("group", { name: "Homeowner’s choice" })).toBeVisible();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeDisabled();

    fireEvent.click(screen.getByLabelText("Labour only; parts cost extra"));
    expect(onSelect).toHaveBeenCalledWith("recorded");
  });

  it("shows and requires short text only for Something else", () => {
    const { onOtherTextChange } = renderQuestion({ optionId: "other" });
    const other = screen.getByLabelText("Add a short explanation");

    expect(other).toHaveAttribute("maxlength", String(OTHER_TEXT_MAX_LENGTH));
    expect(other).toBeRequired();
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeDisabled();
    fireEvent.change(other, { target: { value: "A different price" } });
    expect(onOtherTextChange).toHaveBeenCalledWith("A different price");

    cleanup();
    const { onSubmit } = renderQuestion({
      optionId: "other",
      otherText: "A different price",
    });
    fireEvent.click(screen.getByRole("button", { name: /Submit my choice/ }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not reveal a text field for uncertainty", () => {
    renderQuestion({ optionId: "unsure" });
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit my choice/ })).toBeEnabled();
  });

  it("fails closed when no validated choices are available", () => {
    render(
      <PrivateChoiceQuestion
        actorName="Electrician"
        explanation="Choose the meaning you understood."
        eyebrow="Choose one meaning"
        onOtherTextChange={vi.fn()}
        onSelect={vi.fn()}
        onSubmit={vi.fn()}
        optionId=""
        options={[]}
        otherText=""
        prompt="Which statement matches?"
        questionId="missing-options"
        saving={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This question could not be shown safely.",
    );
    expect(screen.queryByRole("button", { name: /Submit my choice/ })).not.toBeInTheDocument();
  });
});
