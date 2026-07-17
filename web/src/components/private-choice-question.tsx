"use client";

import type { ReactNode } from "react";

export type ChoiceOptionView = {
  id: string;
  label: string;
  kind: string;
};

const OTHER_TEXT_MIN_LENGTH = 2;
export const OTHER_TEXT_MAX_LENGTH = 280;

export function PrivateChoiceQuestion({
  actorName,
  context,
  explanation,
  eyebrow,
  onBack,
  onOtherTextChange,
  onSelect,
  onSubmit,
  optionId,
  options,
  otherText,
  prompt,
  questionId,
  questionNumber,
  questionCount,
  saving,
  secondaryAction,
}: {
  actorName: string;
  context?: ReactNode;
  explanation: string;
  eyebrow: string;
  onBack?: () => void;
  onOtherTextChange: (text: string) => void;
  onSelect: (optionId: string) => void;
  onSubmit: () => void;
  optionId: string;
  options: ChoiceOptionView[];
  otherText: string;
  prompt: string;
  questionId: string;
  questionNumber?: number;
  questionCount?: number;
  saving: boolean;
  secondaryAction?: { label: string; onClick: () => void };
}) {
  const idPrefix = `choice-${questionId}`.replace(/[^a-zA-Z0-9_-]/g, "-");
  const selected = options.find((option) => option.id === optionId) ?? null;
  const needsOtherText = selected?.kind === "other";
  const trimmedOtherText = otherText.trim();
  const canSubmit =
    Boolean(selected) &&
    (!needsOtherText || trimmedOtherText.length >= OTHER_TEXT_MIN_LENGTH);
  const progress =
    questionNumber && questionCount
      ? `Question ${questionNumber} of ${questionCount}`
      : eyebrow;

  return (
    <section
      className="guided-task choice-question-task"
      aria-labelledby={`${idPrefix}-title`}
    >
      {onBack && (
        <button className="plain-back" type="button" onClick={onBack}>
          ← Back to summary
        </button>
      )}
      <header className="guided-heading">
        <p className="eyebrow">{progress}</p>
        <h1 id={`${idPrefix}-title`}>{prompt}</h1>
        <p>{explanation}</p>
      </header>

      <div className="actor-turn" role="status">
        <span className="avatar small" aria-hidden="true">
          {actorName[0]}
        </span>
        <p>
          <strong>{actorName}’s private turn</strong>
          <span>{eyebrow}</span>
        </p>
      </div>

      {context}

      {options.length ? (
        <form
          aria-busy={saving}
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit && !saving) onSubmit();
          }}
        >
          <fieldset className="answer-options">
            <legend>{actorName}’s choice</legend>
            {options.map((option) => {
              const controlId = `${idPrefix}-${option.id}`.replace(
                /[^a-zA-Z0-9_-]/g,
                "-",
              );
              return (
                <label htmlFor={controlId} key={option.id}>
                  <input
                    checked={optionId === option.id}
                    id={controlId}
                    name={`${idPrefix}-option`}
                    onChange={() => onSelect(option.id)}
                    type="radio"
                    value={option.id}
                  />
                  <span>{option.label}</span>
                </label>
              );
            })}
          </fieldset>

          {needsOtherText && (
            <div className="guided-field">
              <label htmlFor={`${idPrefix}-other-text`}>Add a short explanation</label>
              <textarea
                aria-describedby={`${idPrefix}-other-help`}
                autoComplete="off"
                id={`${idPrefix}-other-text`}
                maxLength={OTHER_TEXT_MAX_LENGTH}
                minLength={OTHER_TEXT_MIN_LENGTH}
                onChange={(event) => onOtherTextChange(event.target.value)}
                required
                rows={3}
                value={otherText}
              />
              <p className="choice-help" id={`${idPrefix}-other-help`}>
                {trimmedOtherText.length}/{OTHER_TEXT_MAX_LENGTH} characters
              </p>
            </div>
          )}

          <div className="guided-actions">
            <button
              className="button primary"
              disabled={!canSubmit || saving}
              type="submit"
            >
              {saving ? "Submitting…" : "Submit my choice"}
              {!saving && <span>→</span>}
            </button>
            {secondaryAction && (
              <button
                className="button text-action"
                disabled={saving}
                onClick={secondaryAction.onClick}
                type="button"
              >
                {secondaryAction.label}
              </button>
            )}
          </div>
        </form>
      ) : (
        <div className="choice-unavailable" role="alert">
          <strong>This question could not be shown safely.</strong>
          <p>Refresh the session before continuing.</p>
        </div>
      )}
    </section>
  );
}
