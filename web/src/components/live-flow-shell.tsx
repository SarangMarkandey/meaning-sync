import Link from "next/link";

import type { LiveUserStage } from "@/lib/api";

const stages: Array<{ id: LiveUserStage; label: string }> = [
  { id: "conversation", label: "Conversation" },
  { id: "clarify", label: "Clarify" },
  { id: "check_understanding", label: "Check understanding" },
  { id: "confirm", label: "Confirm" },
  { id: "receipt", label: "Receipt" },
];

export function LiveProgress({
  currentStage,
  explanation,
}: {
  currentStage: LiveUserStage;
  explanation: string;
}) {
  const currentIndex = stages.findIndex((stage) => stage.id === currentStage);

  return (
    <div className="guided-progress-wrap">
      <nav className="guided-progress" aria-label="Live session progress">
        {stages.map((stage, index) => {
          const complete = index < currentIndex;
          const current = index === currentIndex;
          return (
            <span
              className={complete ? "complete" : current ? "current" : "future"}
              key={stage.id}
              aria-current={current ? "step" : undefined}
              aria-disabled={!complete && !current ? "true" : undefined}
            >
              <i aria-hidden="true">{complete ? "✓" : index + 1}</i>
              <strong>{stage.label}</strong>
            </span>
          );
        })}
      </nav>
      <p className="guided-next" role="status">{explanation}</p>
    </div>
  );
}

export function LiveBrandBar({ trailing }: { trailing?: React.ReactNode }) {
  return (
    <nav className="topbar guided-topbar">
      <Link className="brand" href="/">
        <span className="brand-mark">M</span>
        <span>MeaningSync</span>
      </Link>
      {trailing}
    </nav>
  );
}
