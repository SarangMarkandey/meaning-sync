import Link from "next/link";

import {
  type VisibleFlowStage,
  visibleFlowSteps,
} from "@/lib/flow-presentation";

export function LiveProgress({
  currentStage,
  explanation,
}: {
  currentStage: VisibleFlowStage;
  explanation: string;
}) {
  const currentIndex = visibleFlowSteps.findIndex(
    (stage) => stage.id === currentStage,
  );

  return (
    <div className="guided-progress-wrap">
      <nav className="guided-progress" aria-label="Live session progress">
        {visibleFlowSteps.map((stage, index) => {
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
