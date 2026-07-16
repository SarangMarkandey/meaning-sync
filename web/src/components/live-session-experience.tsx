"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import {
  EvidenceDisclosure,
  GuidedTermList,
  ParticipantPositions,
} from "@/components/live-guided-terms";
import {
  api,
  MeaningSyncApiError,
  type AgreementTerm,
  type AgreementVersion,
  type AgreementVersionChange,
  type LiveClarification,
  type LiveGuidanceAction,
  type LiveSessionView,
  type PartyRole,
} from "@/lib/api";

const roleNames: Record<PartyRole, string> = {
  hirer: "Homeowner",
  worker: "Electrician",
};

type DetailView = "summary" | "clarification" | "optional" | "review";
type OptionalChoice = {
  kind: "open" | "not_applicable" | "add";
  speaker: PartyRole;
  text: string;
  proposedBy: PartyRole[];
};

function requestId() {
  return globalThis.crypto?.randomUUID?.() ?? `request-${Date.now()}`;
}

function currentVersion(session: LiveSessionView): AgreementVersion | null {
  return (
    session.agreement_versions.find(
      (version) => version.id === session.current_agreement_version_id,
    ) ?? null
  );
}

function keyedTerms(version: AgreementVersion | null, keys: string[]) {
  if (!version) return [];
  const lookup = new Map(version.terms.map((term) => [term.analysis_item_key, term]));
  return keys.flatMap((key) => {
    const term = lookup.get(key);
    return term ? [term] : [];
  });
}

function latestTeachbackFor(
  session: LiveSessionView,
  participant: PartyRole | null,
) {
  if (!participant) return null;
  return (
    [...session.teachbacks]
      .reverse()
      .find(
        (item) =>
          item.participant_id === participant &&
          item.agreement_version_id === session.current_agreement_version_id,
      ) ?? null
  );
}

function FlowError({
  error,
  onRetry,
}: {
  error: MeaningSyncApiError;
  onRetry: () => void;
}) {
  const stale = error.code === "stale_agreement_version";
  return (
    <section className="guided-error" role="alert">
      <div>
        <strong>{stale ? "This understanding changed" : "That step could not be completed"}</strong>
        <p>
          {stale
            ? "Refresh before continuing so you review the latest recorded meaning."
            : error.message}
        </p>
      </div>
      <button className="button secondary" type="button" onClick={onRetry}>
        {stale ? "Refresh" : "Try again"}
      </button>
    </section>
  );
}

export function LiveSessionExperience({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const taskFocusRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<LiveSessionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<MeaningSyncApiError | null>(null);
  const [detailView, setDetailView] = useState<DetailView>("summary");
  const [clarificationDismissed, setClarificationDismissed] = useState(false);
  const [handoffReady, setHandoffReady] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [customAnswer, setCustomAnswer] = useState("");
  const [clarificationOutcome, setClarificationOutcome] = useState<
    "resolved" | "still_unresolved" | null
  >(null);
  const [outcomeClarificationId, setOutcomeClarificationId] = useState<string | null>(null);
  const [outcomeWasShared, setOutcomeWasShared] = useState(false);
  const [optionalChoices, setOptionalChoices] = useState<
    Record<string, OptionalChoice>
  >({});
  const [unresolvedAcknowledged, setUnresolvedAcknowledged] = useState(false);
  const [teachbackText, setTeachbackText] = useState("");
  const [changeItemKey, setChangeItemKey] = useState("");

  const loadSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSession(await api.getLiveSession(sessionId));
      setDetailView("summary");
      setClarificationDismissed(false);
    } catch (caught) {
      setError(
        caught instanceof MeaningSyncApiError
          ? caught
          : new MeaningSyncApiError("This live session could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    let current = true;
    void api
      .getLiveSession(sessionId)
      .then((next) => {
        if (!current) return;
        setSession(next);
        setDetailView("summary");
        setClarificationDismissed(false);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!current) return;
        setError(
          caught instanceof MeaningSyncApiError
            ? caught
            : new MeaningSyncApiError("This live session could not be loaded."),
        );
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [sessionId]);

  const version = session ? currentVersion(session) : null;
  const guidance = session?.guidance ?? null;
  const actor = guidance?.acting_participant ?? null;
  const activeTerm = useMemo(
    () =>
      version?.terms.find(
        (term) => term.analysis_item_key === guidance?.target_item_key,
      ) ?? null,
    [guidance?.target_item_key, version],
  );
  const optionalTerms = useMemo(
    () => keyedTerms(version, guidance?.optional_item_keys ?? []),
    [guidance?.optional_item_keys, version],
  );
  const unresolvedTerms = useMemo(
    () =>
      version?.terms.filter(
        (term) =>
          term.state === "conflicting" || term.state === "stated_by_one",
      ) ?? [],
    [version],
  );
  const activeClarification =
    session && guidance?.active_clarification_id
      ? session.clarifications.find(
          (item) => item.id === guidance.active_clarification_id,
        ) ?? null
      : null;

  useEffect(() => {
    if (!loading && session && guidance) {
      taskFocusRef.current?.focus();
    }
  }, [
    actor,
    clarificationOutcome,
    detailView,
    error,
    guidance,
    handoffReady,
    loading,
    session,
  ]);

  const setMutationError = (caught: unknown) => {
    setError(
      caught instanceof MeaningSyncApiError
        ? caught
        : new MeaningSyncApiError("MeaningSync could not complete that step."),
    );
  };

  const leaveUnresolved = async (clarificationId?: string) => {
    if (!session || !version) return;
    const targetId =
      clarificationId ??
      activeClarification?.id ??
      [...session.clarifications]
        .reverse()
        .find((item) => item.status === "still_unresolved")?.id;
    if (!targetId) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.leaveLiveClarificationUnresolved(
        session.id,
        targetId,
        {
          expected_agreement_version_id: version.id,
          request_id: requestId(),
        },
      );
      setSession(next);
      setDetailView("summary");
      setClarificationOutcome(null);
      setOutcomeClarificationId(null);
      setHandoffReady(false);
      setClarificationDismissed(false);
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const submitClarification = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !version || !activeClarification || !actor) return;
    const answer =
      selectedAnswer === "__custom__" ? customAnswer.trim() : selectedAnswer.trim();
    if (answer.length < 2) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.submitLiveClarificationAnswer(
        session.id,
        activeClarification.id,
        {
          participant_id: actor,
          answer,
          expected_agreement_version_id: version.id,
          request_id: requestId(),
        },
      );
      const updated = next.clarifications.find(
        (item) => item.id === activeClarification.id,
      );
      setSession(next);
      setSelectedAnswer("");
      setCustomAnswer("");
      setHandoffReady(false);
      if (updated?.status === "resolved" || updated?.status === "still_unresolved") {
        setClarificationOutcome(updated.status);
        setOutcomeClarificationId(updated.id);
        setOutcomeWasShared(activeClarification.addressed_participant_ids.length > 1);
      }
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const updateOptionalChoice = (
    itemKey: string,
    update: Partial<OptionalChoice>,
  ) => {
    setOptionalChoices((current) => ({
      ...current,
      [itemKey]: {
        ...(current[itemKey] ?? {
          kind: "open",
          speaker: "hirer",
          text: "",
          proposedBy: [],
        }),
        ...update,
      },
    }));
  };

  const finishOptionalDetails = async ({ skip = false }: { skip?: boolean } = {}) => {
    if (!session || !version) return;
    let next = session;
    setSaving(true);
    setError(null);
    try {
      if (!skip) {
        for (const term of optionalTerms) {
          const choice = optionalChoices[term.analysis_item_key];
          if (choice?.kind !== "not_applicable") continue;
          for (const participant of choice.proposedBy) {
            const nextVersion = currentVersion(next);
            if (!nextVersion) throw new MeaningSyncApiError("The current understanding is unavailable.");
            next = await api.proposeNotApplicable(next.id, {
              expected_agreement_version_id: nextVersion.id,
              participant_id: participant,
              item_key: term.analysis_item_key,
              request_id: requestId(),
            });
            setSession(next);
          }
        }

        const additions = optionalTerms.flatMap((term) => {
          const choice = optionalChoices[term.analysis_item_key];
          const text = choice?.text.trim() ?? "";
          return choice?.kind === "add" && text.length >= 2
            ? [{ term, choice, text }]
            : [];
        });
        if (additions.length) {
          const nextVersion = currentVersion(next);
          if (!nextVersion) throw new MeaningSyncApiError("The current understanding is unavailable.");
          const highestOrder = next.messages.reduce(
            (highest, message) => Math.max(highest, message.order),
            0,
          );
          const startedAt = Date.now();
          next = await api.addLiveStatements(next.id, {
            expected_agreement_version_id: nextVersion.id,
            request_id: requestId(),
            messages: additions.map(({ choice, text }, index) => ({
              message_id: `optional-${startedAt}-${index + 1}`,
              speaker_id: choice.speaker,
              original_text: text,
              original_language:
                next.participants.find((item) => item.role === choice.speaker)
                  ?.language ?? "en",
              order: highestOrder + index + 1,
              timestamp: new Date(startedAt + index).toISOString(),
            })),
          });
          setSession(next);
        }
      }

      if (
        next.guidance.primary_action === "answer_clarification" ||
        next.guidance.primary_action === "leave_unresolved"
      ) {
        setDetailView("summary");
        setOptionalChoices({});
        return;
      }

      const nextVersion = currentVersion(next);
      if (!nextVersion) throw new MeaningSyncApiError("The current understanding is unavailable.");
      next = await api.reviewOptionalDetails(next.id, {
        expected_agreement_version_id: nextVersion.id,
        request_id: requestId(),
      });
      setSession(next);
      setDetailView("review");
      setOptionalChoices({});
    } catch (caught) {
      setSession(next);
      if (
        next.guidance.primary_action === "answer_clarification" ||
        next.guidance.primary_action === "leave_unresolved"
      ) {
        setDetailView("summary");
      }
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const openFinalReview = async () => {
    if (!session || !version) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.reviewOptionalDetails(session.id, {
        expected_agreement_version_id: version.id,
        request_id: requestId(),
      });
      setSession(next);
      setDetailView("review");
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const beginUnderstandingCheck = async () => {
    if (!session || !version) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.beginLiveReview(session.id, {
        expected_agreement_version_id: version.id,
        acknowledged_unresolved_item_keys: unresolvedTerms.map(
          (term) => term.analysis_item_key,
        ),
        request_id: requestId(),
      });
      setSession(next);
      setDetailView("summary");
      setHandoffReady(false);
      setUnresolvedAcknowledged(false);
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const submitTeachback = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !version || !actor) return;
    const typed = teachbackText.trim();
    if (typed.length < 12) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.submitTeachback(session.id, {
        participant_id: actor,
        text: typed,
        original_language: "en",
        expected_agreement_version_id: version.id,
        acknowledged_unresolved_item_keys: unresolvedTerms.map(
          (term) => term.analysis_item_key,
        ),
        request_id: requestId(),
      });
      setSession(next);
      setTeachbackText("");
      setHandoffReady(false);
      setUnresolvedAcknowledged(false);
      setDetailView("summary");
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const submitConfirmation = async (decision: "confirm" | "request_change") => {
    if (!session || !version || !actor) return;
    const teachback = latestTeachbackFor(session, actor);
    if (!teachback || (decision === "request_change" && !changeItemKey)) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.submitLiveConfirmation(session.id, {
        participant_id: actor,
        expected_agreement_version_id: version.id,
        teachback_id: teachback.id,
        decision,
        unresolved_item_acknowledgments: unresolvedTerms.map(
          (term) => term.analysis_item_key,
        ),
        change_item_key: decision === "request_change" ? changeItemKey : undefined,
        request_id: requestId(),
      });
      setSession(next);
      setChangeItemKey("");
      setHandoffReady(false);
      setUnresolvedAcknowledged(false);
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const issueReceipt = async () => {
    if (!session || !version) return;
    setSaving(true);
    setError(null);
    try {
      await api.issueLiveReceipt(session.id, version.id, requestId());
      router.push(`/live/${encodeURIComponent(session.id)}/receipt`);
    } catch (caught) {
      setMutationError(caught);
    } finally {
      setSaving(false);
    }
  };

  const runGuidanceAction = (action: LiveGuidanceAction) => {
    if (action === "answer_clarification") {
      setClarificationDismissed(false);
      setDetailView("clarification");
      return;
    }
    if (action === "leave_unresolved") {
      void leaveUnresolved();
      return;
    }
    if (action === "review_optional_details") {
      setDetailView("optional");
      return;
    }
    if (action === "review_final_understanding") {
      void openFinalReview();
      return;
    }
    if (action === "issue_receipt") {
      void issueReceipt();
      return;
    }
    if (action === "view_receipt" && session) {
      router.push(`/live/${encodeURIComponent(session.id)}/receipt`);
    }
  };

  if (loading) {
    return (
      <main className="app-shell">
        <LiveBrandBar />
        <div className="guided-loading" role="status"><span /> Loading this conversation…</div>
      </main>
    );
  }

  if (!session || !guidance) {
    const missing = error?.code === "session_not_found" || error?.status === 404;
    return (
      <main className="app-shell">
        <LiveBrandBar />
        <section className="session-recovery" role="alert">
          <span>{missing ? "Session unavailable" : "Could not load session"}</span>
          <h1>
            {missing
              ? "This live session is no longer available."
              : "We could not open this live session."}
          </h1>
          <p>
            {missing
              ? "Live sessions are stored only for this server run. Start again if the server restarted or the session expired."
              : error?.message ?? "The session did not include the guidance needed to continue safely."}
          </p>
          <div>
            <Link className="button primary" href="/live/setup">Start a new live session</Link>
            {!missing && <button className="button secondary" type="button" onClick={() => void loadSession()}>Try again</button>}
          </div>
        </section>
      </main>
    );
  }

  const forceClarification =
    detailView === "clarification" ||
    (Boolean(activeClarification?.answers_received_from.length) &&
      !clarificationDismissed);
  const showOptional =
    detailView === "optional" ||
    guidance.primary_action === "review_optional_details";
  const outcomeClarification = session.clarifications.find(
    (item) => item.id === outcomeClarificationId,
  );
  const outcomeChange = version?.has_meaningful_change
    ? version.changes.find(
        (change) =>
          change.item_key === outcomeClarification?.target_item_key,
      ) ?? null
    : null;
  const outcomeTerm = outcomeChange
    ? version?.terms.find(
        (term) => term.analysis_item_key === outcomeChange.item_key,
      ) ?? null
    : null;

  let task: React.ReactNode;
  if (clarificationOutcome) {
    task = (
      <ClarificationOutcome
        outcome={clarificationOutcome}
        sharedAnswers={outcomeWasShared}
        change={outcomeChange}
        changedTerm={outcomeTerm}
        guidance={guidance}
        saving={saving}
        onContinue={() => {
          if (guidance.primary_action === "leave_unresolved") {
            void leaveUnresolved(outcomeClarificationId ?? undefined);
            return;
          }
          setClarificationOutcome(null);
          setOutcomeClarificationId(null);
          if (guidance.primary_action === "answer_clarification") {
            setDetailView("clarification");
          } else if (guidance.primary_action === "review_optional_details") {
            setDetailView("optional");
          } else {
            setDetailView("summary");
          }
        }}
        canLeave={
          Boolean(outcomeClarificationId) &&
          guidance.secondary_action === "leave_unresolved"
        }
        onLeave={() => void leaveUnresolved(outcomeClarificationId ?? undefined)}
      />
    );
  } else if (
    guidance.primary_action === "leave_unresolved" &&
    activeClarification &&
    forceClarification
  ) {
    task = (
      <StillDifferentTask
        clarification={activeClarification}
        term={activeTerm}
        label={guidance.primary_label}
        saving={saving}
        onLeave={() => void leaveUnresolved(activeClarification.id)}
        onBack={() => {
          setDetailView("summary");
          setClarificationDismissed(true);
        }}
      />
    );
  } else if (
    guidance.primary_action === "answer_clarification" &&
    forceClarification &&
    activeClarification
  ) {
    task = (
      <ClarificationTask
        clarification={activeClarification}
        term={activeTerm}
        actor={actor}
        handoffReady={handoffReady}
        saving={saving}
        selectedAnswer={selectedAnswer}
        customAnswer={customAnswer}
        onHandoff={() => setHandoffReady(true)}
        onSelectAnswer={setSelectedAnswer}
        onCustomAnswer={setCustomAnswer}
        onSubmit={submitClarification}
        onBack={() => {
          setDetailView("summary");
          setClarificationDismissed(true);
          setHandoffReady(false);
        }}
        onLeave={() => void leaveUnresolved()}
      />
    );
  } else if (showOptional) {
    task = (
      <OptionalDetails
        terms={optionalTerms}
        choices={optionalChoices}
        saving={saving}
        onChange={updateOptionalChoice}
        onSubmit={() => void finishOptionalDetails()}
        onSkip={() => void finishOptionalDetails({ skip: true })}
      />
    );
  } else if (detailView === "review") {
    task = (
      <FinalReview
        session={session}
        version={version}
        acknowledged={unresolvedAcknowledged}
        saving={saving}
        onAcknowledge={setUnresolvedAcknowledged}
        onContinue={() => void beginUnderstandingCheck()}
        onBack={() => setDetailView(optionalTerms.length ? "optional" : "summary")}
      />
    );
  } else if (guidance.primary_action === "submit_teachback" && actor) {
    task = (
      <UnderstandingCheck
        session={session}
        actor={actor}
        version={version}
        handoffReady={handoffReady}
        text={teachbackText}
        acknowledged={unresolvedAcknowledged}
        saving={saving}
        onHandoff={() => setHandoffReady(true)}
        onText={setTeachbackText}
        onAcknowledge={setUnresolvedAcknowledged}
        onSubmit={submitTeachback}
        onLock={() => setHandoffReady(false)}
      />
    );
  } else if (guidance.primary_action === "submit_confirmation" && actor) {
    task = (
      <ConfirmationTask
        session={session}
        actor={actor}
        version={version}
        handoffReady={handoffReady}
        acknowledged={unresolvedAcknowledged}
        changeItemKey={changeItemKey}
        saving={saving}
        onHandoff={() => setHandoffReady(true)}
        onAcknowledge={setUnresolvedAcknowledged}
        onChangeItem={setChangeItemKey}
        onSubmit={submitConfirmation}
      />
    );
  } else if (
    guidance.primary_action === "issue_receipt" ||
    guidance.primary_action === "view_receipt"
  ) {
    task = (
      <ReceiptReady
        session={session}
        action={guidance.primary_action}
        label={guidance.primary_label}
        saving={saving}
        onIssue={() => void issueReceipt()}
      />
    );
  } else {
    task = (
      <ResultSummary
        version={version}
        guidance={guidance}
        saving={saving}
        onPrimary={() => runGuidanceAction(guidance.primary_action)}
        onSecondary={
          guidance.secondary_action
            ? () => runGuidanceAction(guidance.secondary_action!)
            : undefined
        }
      />
    );
  }

  return (
    <main className="app-shell">
      <LiveBrandBar trailing={<span className="guided-mode-note">Live · text only</span>} />
      <section className="guided-flow-page">
        <LiveProgress
          currentStage={guidance.user_stage}
          explanation={guidance.explanation}
        />
        <div
          className="guided-focus-target"
          ref={taskFocusRef}
          tabIndex={-1}
        >
          {error && <FlowError error={error} onRetry={() => void loadSession()} />}
          {task}
        </div>
        <footer className="guided-disclaimer">
          MeaningSync compares stated meaning. It does not provide legal advice,
          verify identity, or create a legal contract.
        </footer>
      </section>
    </main>
  );
}

function ResultSummary({
  version,
  guidance,
  saving,
  onPrimary,
  onSecondary,
}: {
  version: AgreementVersion | null;
  guidance: LiveSessionView["guidance"];
  saving: boolean;
  onPrimary: () => void;
  onSecondary?: () => void;
}) {
  const aligned = version?.terms.filter((term) => term.state === "aligned") ?? [];
  return (
    <section className="guided-task result-summary" aria-labelledby="result-title">
      <header className="guided-heading">
        <p className="eyebrow">Conversation checked</p>
        <h1 id="result-title">Most of the conversation is clear</h1>
        <p>MeaningSync found where both people used the same meaning and what still needs attention.</p>
      </header>
      <div className="result-counts" aria-label="Understanding summary">
        <div className="match"><p className="sr-only">{aligned.length} {aligned.length === 1 ? "thing matches" : "things match"}</p><strong aria-hidden="true">{aligned.length}</strong><span aria-hidden="true">{aligned.length === 1 ? "thing matches" : "things match"}</span></div>
        <div className="required"><p className="sr-only">{guidance.required_issue_count} {guidance.required_issue_count === 1 ? "answer needed" : "answers needed"}</p><strong aria-hidden="true">{guidance.required_issue_count}</strong><span aria-hidden="true">{guidance.required_issue_count === 1 ? "answer needed" : "answers needed"}</span></div>
        <div className="optional"><p className="sr-only">{guidance.optional_missing_count} optional details were not discussed</p><strong aria-hidden="true">{guidance.optional_missing_count}</strong><span aria-hidden="true">optional details were not discussed</span></div>
      </div>
      <section className="aligned-preview" aria-labelledby="matches-title">
        <header><span aria-hidden="true">✓</span><div><h2 id="matches-title">What already matches</h2><p>Open any item to see the original statements.</p></div></header>
        <GuidedTermList terms={aligned.slice(0, 4)} emptyMessage="No matching terms were recorded yet." />
      </section>
      <div className="guided-actions">
        <button className="button primary" type="button" disabled={saving} onClick={onPrimary}>
          {guidance.primary_label} <span>→</span>
        </button>
        {guidance.secondary_label && onSecondary && (
          <button className="button text-action" type="button" disabled={saving} onClick={onSecondary}>
            {guidance.secondary_label}
          </button>
        )}
      </div>
    </section>
  );
}

function ClarificationTask({
  clarification,
  term,
  actor,
  handoffReady,
  saving,
  selectedAnswer,
  customAnswer,
  onHandoff,
  onSelectAnswer,
  onCustomAnswer,
  onSubmit,
  onBack,
  onLeave,
}: {
  clarification: LiveClarification;
  term: AgreementTerm | null;
  actor: PartyRole | null;
  handoffReady: boolean;
  saving: boolean;
  selectedAnswer: string;
  customAnswer: string;
  onHandoff: () => void;
  onSelectAnswer: (answer: string) => void;
  onCustomAnswer: (answer: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBack: () => void;
  onLeave: () => void;
}) {
  const retrying = clarification.status === "still_unresolved";
  const someoneAnswered =
    !retrying && clarification.answers_received_from.length > 0;
  if (retrying && !handoffReady && actor) {
    return (
      <section className="guided-task handoff-task" aria-labelledby="retry-handoff-title">
        <div className="handoff-symbol" aria-hidden="true">↗</div>
        <p className="eyebrow">Try one fresh clarification</p>
        <h1 id="retry-handoff-title">Pass the device to {roleNames[actor]}.</h1>
        <p>The earlier answers were still different. They remain hidden while {roleNames[actor]} starts a fresh answer.</p>
        <button className="button primary" type="button" onClick={onHandoff}>
          I’m {roleNames[actor]} — try again <span>→</span>
        </button>
        <small>This same-device handoff is not identity verification or strong privacy.</small>
      </section>
    );
  }
  if (someoneAnswered && !handoffReady && actor) {
    const completed = clarification.answers_received_from[0];
    return (
      <section className="guided-task handoff-task" aria-labelledby="handoff-title">
        <div className="handoff-symbol" aria-hidden="true">↗</div>
        <p className="eyebrow">Answer hidden</p>
        <h1 id="handoff-title">Pass the device to {roleNames[actor]}.</h1>
        <p>{completed ? `${roleNames[completed]} answered. Their response stays hidden until both people answer.` : "The first response is hidden."}</p>
        <button className="button primary" type="button" onClick={onHandoff}>
          I’m {roleNames[actor]} — answer the question <span>→</span>
        </button>
        <small>This same-device handoff is not identity verification or strong privacy.</small>
      </section>
    );
  }

  if (!actor) {
    return <section className="guided-task"><p className="guided-empty">Both answers were received. MeaningSync is checking them.</p></section>;
  }

  const options = clarification.answer_options.filter(
    (option) => !/write a different answer/i.test(option),
  );
  const answer = selectedAnswer === "__custom__" ? customAnswer.trim() : selectedAnswer.trim();
  return (
    <section className="guided-task clarification-task" aria-labelledby="clarification-title">
      <button className="plain-back" type="button" onClick={onBack}>← Back to summary</button>
      <header className="guided-heading">
        <p className="eyebrow">One detail needs a clear answer</p>
        <h1 id="clarification-title">{clarification.question}</h1>
        {term && (
          <p className="clarification-reason">
            {term.participant_positions.map((position) => `${roleNames[position.role]}: ${position.summary}`).join(" ")}
          </p>
        )}
      </header>
      <div className="actor-turn" role="status"><span className={`avatar small ${actor === "worker" ? "worker" : ""}`}>{roleNames[actor][0]}</span><p><strong>{roleNames[actor]}’s turn</strong><span>Choose the answer that reflects what you mean.</span></p></div>
      {term && <ParticipantPositions term={term} />}
      {term && <EvidenceDisclosure term={term} />}
      <form onSubmit={onSubmit}>
        <fieldset className="answer-options">
          <legend>{roleNames[actor]}’s answer</legend>
          {options.map((option) => (
            <label key={option}>
              <input type="radio" name="clarification-answer" value={option} checked={selectedAnswer === option} onChange={() => onSelectAnswer(option)} />
              <span>{option}</span>
            </label>
          ))}
          <label>
            <input type="radio" name="clarification-answer" value="__custom__" checked={selectedAnswer === "__custom__"} onChange={() => onSelectAnswer("__custom__")} />
            <span>Write a different answer</span>
          </label>
        </fieldset>
        {(selectedAnswer === "__custom__" || !options.length) && (
          <div className="guided-field">
            <label htmlFor="custom-clarification-answer">Your answer</label>
            <textarea id="custom-clarification-answer" rows={4} value={customAnswer} onChange={(event) => { onCustomAnswer(event.target.value); if (!selectedAnswer) onSelectAnswer("__custom__"); }} placeholder="State what you mean in your own words…" />
          </div>
        )}
        <div className="guided-actions">
          <button className="button primary" type="submit" disabled={saving || answer.length < 2}>Submit my answer <span>→</span></button>
          <button className="button text-action" type="button" disabled={saving} onClick={onLeave}>Leave this unresolved</button>
        </div>
      </form>
    </section>
  );
}

function ClarificationOutcome({
  outcome,
  sharedAnswers,
  change,
  changedTerm,
  guidance,
  saving,
  onContinue,
  canLeave,
  onLeave,
}: {
  outcome: "resolved" | "still_unresolved";
  sharedAnswers: boolean;
  change: AgreementVersionChange | null;
  changedTerm: AgreementTerm | null;
  guidance: LiveSessionView["guidance"];
  saving: boolean;
  onContinue: () => void;
  canLeave: boolean;
  onLeave: () => void;
}) {
  const resolved = outcome === "resolved";
  return (
    <section className={`guided-task outcome-task ${resolved ? "success" : "open"}`} aria-labelledby="outcome-title">
      <div className="outcome-symbol" aria-hidden="true">{resolved ? "✓" : "↔"}</div>
      <p className="eyebrow">{sharedAnswers ? "Both answers checked" : "Answer checked"}</p>
      <h1 id="outcome-title">{resolved ? "This detail is now clear" : "The answers are still different"}</h1>
      <p>{resolved ? "MeaningSync updated the recorded understanding using both people’s answers." : "MeaningSync has kept this point unresolved. It will not be shown as agreement."}</p>
      {resolved && change && (
        <div className="outcome-update">
          <div className="plain-success">Updated: {change.resulting_meaning}</div>
          <NewSupportingEvidence change={change} term={changedTerm} />
        </div>
      )}
      <div className="guided-actions">
        <button className="button primary" type="button" disabled={saving} onClick={onContinue}>{guidance.primary_label} <span>→</span></button>
        {!resolved && canLeave && <button className="button text-action" type="button" disabled={saving} onClick={onLeave}>Leave it unresolved</button>}
      </div>
    </section>
  );
}

function NewSupportingEvidence({
  change,
  term,
}: {
  change: AgreementVersionChange;
  term: AgreementTerm | null;
}) {
  const evidence =
    term?.evidence.filter((reference) =>
      change.new_evidence_reference_ids.includes(reference.reference_id),
    ) ?? [];
  if (!evidence.length) return null;
  return (
    <details className="guided-evidence new-evidence">
      <summary>New supporting evidence</summary>
      <ul>
        {evidence.map((reference) => (
          <li key={`${reference.source}-${reference.reference_id}`}>
            <span>{reference.speaker_name || roleNames[reference.role]}</span>
            <q>{reference.original_text}</q>
          </li>
        ))}
      </ul>
    </details>
  );
}

function StillDifferentTask({
  clarification,
  term,
  label,
  saving,
  onLeave,
  onBack,
}: {
  clarification: LiveClarification;
  term: AgreementTerm | null;
  label: string;
  saving: boolean;
  onLeave: () => void;
  onBack: () => void;
}) {
  return (
    <section className="guided-task outcome-task open" aria-labelledby="still-different-title">
      <button className="plain-back" type="button" onClick={onBack}>← Back to summary</button>
      <div className="outcome-symbol" aria-hidden="true">↔</div>
      <p className="eyebrow">Clarification checked</p>
      <h1 id="still-different-title">This point is still different</h1>
      <p>{clarification.question}</p>
      {term && <ParticipantPositions term={term} />}
      {term && <EvidenceDisclosure term={term} />}
      <div className="guided-actions">
        <button className="button primary" type="button" disabled={saving} onClick={onLeave}>{label} <span>→</span></button>
      </div>
    </section>
  );
}

function OptionalDetails({
  terms,
  choices,
  saving,
  onChange,
  onSubmit,
  onSkip,
}: {
  terms: AgreementTerm[];
  choices: Record<string, OptionalChoice>;
  saving: boolean;
  onChange: (itemKey: string, update: Partial<OptionalChoice>) => void;
  onSubmit: () => void;
  onSkip: () => void;
}) {
  const invalid = terms.some((term) => {
    const choice = choices[term.analysis_item_key];
    return (
      (choice?.kind === "add" && choice.text.trim().length < 2) ||
      (choice?.kind === "not_applicable" && choice.proposedBy.length === 0)
    );
  });
  return (
    <section className="guided-task optional-task" aria-labelledby="optional-title">
      <header className="guided-heading">
        <p className="eyebrow">Optional details</p>
        <h1 id="optional-title">Add anything else?</h1>
        <p>These details were not discussed. You can add them now or leave them open.</p>
      </header>
      <div className="optional-list">
        {terms.map((term) => {
          const choice = choices[term.analysis_item_key] ?? { kind: "open", speaker: "hirer", text: "", proposedBy: [] };
          return (
            <article className="optional-card" key={term.analysis_item_key}>
              <div><h2>{term.label}</h2><p>{term.summary}</p></div>
              <div className="optional-choice-row" aria-label={`Choose how to handle ${term.label}`}>
                <button className={choice.kind === "add" ? "selected" : ""} type="button" aria-pressed={choice.kind === "add"} onClick={() => onChange(term.analysis_item_key, { kind: "add" })}>Add detail</button>
                <button className={choice.kind === "not_applicable" ? "selected" : ""} type="button" aria-pressed={choice.kind === "not_applicable"} onClick={() => onChange(term.analysis_item_key, { kind: "not_applicable" })}>Not applicable</button>
                <button className={choice.kind === "open" ? "selected" : ""} type="button" aria-pressed={choice.kind === "open"} onClick={() => onChange(term.analysis_item_key, { kind: "open" })}>Leave open</button>
              </div>
              {choice.kind === "add" && (
                <div className="optional-detail-fields">
                  <label><span>Who said it?</span><select aria-label={`${term.label} speaker`} value={choice.speaker} onChange={(event) => onChange(term.analysis_item_key, { speaker: event.target.value as PartyRole })}><option value="hirer">Homeowner</option><option value="worker">Electrician</option></select></label>
                  <label><span>What did they say?</span><textarea aria-label={`${term.label} detail`} rows={3} value={choice.text} onChange={(event) => onChange(term.analysis_item_key, { text: event.target.value })} /></label>
                </div>
              )}
              {choice.kind === "not_applicable" && (
                <div className="optional-na-review">
                  <span>Who says this does not apply?</span>
                  {(["hirer", "worker"] as PartyRole[]).map((party) => (
                    <label key={party}>
                      <input
                        type="checkbox"
                        checked={choice.proposedBy.includes(party)}
                        onChange={() =>
                          onChange(term.analysis_item_key, {
                            proposedBy: choice.proposedBy.includes(party)
                              ? choice.proposedBy.filter((item) => item !== party)
                              : [...choice.proposedBy, party],
                          })
                        }
                      />
                      <span>{roleNames[party]}</span>
                    </label>
                  ))}
                  <p className="optional-note">
                    {choice.proposedBy.length === 2
                      ? "Both people marked this not applicable."
                      : choice.proposedBy.length === 1
                        ? `${roleNames[choice.proposedBy[0]]} marked this not applicable. It remains pending for the other person.`
                        : "Select each person who says this does not apply."}
                  </p>
                </div>
              )}
            </article>
          );
        })}
      </div>
      <div className="guided-actions">
        <button className="button primary" type="button" disabled={saving || invalid} onClick={onSubmit}>Review final understanding <span>→</span></button>
        <button className="button text-action" type="button" disabled={saving} onClick={onSkip}>Skip optional details</button>
      </div>
    </section>
  );
}

function FinalReview({
  session,
  version,
  acknowledged,
  saving,
  onAcknowledge,
  onContinue,
  onBack,
}: {
  session: LiveSessionView;
  version: AgreementVersion | null;
  acknowledged: boolean;
  saving: boolean;
  onAcknowledge: (checked: boolean) => void;
  onContinue: () => void;
  onBack: () => void;
}) {
  const aligned = version?.terms.filter((term) => term.state === "aligned") ?? [];
  const unresolved = version?.terms.filter((term) => term.state === "conflicting" || term.state === "stated_by_one") ?? [];
  const missing = version?.terms.filter((term) => term.state === "not_discussed") ?? [];
  const mutualProposalKeys = new Set(
    version?.not_applicable_proposals
      .filter((proposal) => proposal.proposed_by.length === 2)
      .map((proposal) => proposal.item_key) ?? [],
  );
  const openMissing = missing.filter(
    (term) => !mutualProposalKeys.has(term.analysis_item_key),
  );
  const mutualNotApplicable = missing.filter((term) =>
    mutualProposalKeys.has(term.analysis_item_key),
  );
  const meaningfulVersions = Array.from(
    new Map(
      session.agreement_versions
        .filter((item) => item.has_meaningful_change)
        .map((item) => [item.meaningful_version_number, item]),
    ).values(),
  );
  return (
    <section className="guided-task final-review" aria-labelledby="review-title">
      <header className="guided-heading"><p className="eyebrow">Final review</p><h1 id="review-title">Review what MeaningSync recorded</h1><p>Each item appears once. Open the evidence when you want to check the original words.</p></header>
      <section className="review-section matches"><header><span>✓</span><div><h2>You both said the same thing</h2><p>{aligned.length} recorded {aligned.length === 1 ? "meaning" : "meanings"}</p></div></header><GuidedTermList terms={aligned} /></section>
      {unresolved.length > 0 && (
        <section className="review-section unresolved"><header><span>!</span><div><h2>Still unresolved</h2><p>You can continue, but the receipt will clearly show that these points remain unresolved.</p></div></header><GuidedTermList terms={unresolved} showState /><label className="section-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => onAcknowledge(event.target.checked)} /><span>I reviewed this section and understand these points remain unresolved.</span></label></section>
      )}
      {openMissing.length > 0 && <details className="review-section missing"><summary><span>○</span><div><h2>Not discussed</h2><p>{openMissing.length} optional {openMissing.length === 1 ? "detail" : "details"} left open</p></div></summary><GuidedTermList terms={openMissing} proposals={version?.not_applicable_proposals ?? []} /></details>}
      {mutualNotApplicable.length > 0 && <section className="review-section mutual-na"><header><span>✓</span><div><h2>Both marked not applicable</h2><p>{mutualNotApplicable.length} optional {mutualNotApplicable.length === 1 ? "detail does" : "details do"} not apply</p></div></header><GuidedTermList terms={mutualNotApplicable} proposals={version?.not_applicable_proposals ?? []} /></section>}
      <details className="advanced-details"><summary>Advanced details</summary><div><h2>Version history</h2><p>MeaningSync keeps earlier meaningful records so changes can be reviewed.</p><ol>{meaningfulVersions.map((item) => <li key={item.id}>Recorded understanding {item.meaningful_version_number}{item.meaningful_version_number === version?.meaningful_version_number ? " · current" : ""}</li>)}</ol></div></details>
      <div className="guided-actions"><button className="button primary" type="button" disabled={saving || (unresolved.length > 0 && !acknowledged)} onClick={onContinue}>Check each person’s understanding <span>→</span></button><button className="button text-action" type="button" onClick={onBack}>Go back and make changes</button></div>
    </section>
  );
}

function UnderstandingCheck({
  session,
  actor,
  version,
  handoffReady,
  text,
  acknowledged,
  saving,
  onHandoff,
  onText,
  onAcknowledge,
  onSubmit,
  onLock,
}: {
  session: LiveSessionView;
  actor: PartyRole;
  version: AgreementVersion | null;
  handoffReady: boolean;
  text: string;
  acknowledged: boolean;
  saving: boolean;
  onHandoff: () => void;
  onText: (text: string) => void;
  onAcknowledge: (checked: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onLock: () => void;
}) {
  if (!handoffReady) {
    const complete = session.teachbacks.some((item) => item.participant_id !== actor && item.agreement_version_id === version?.id);
    return <section className="guided-task handoff-task"><div className="handoff-symbol" aria-hidden="true">↗</div><p className="eyebrow">Check understanding</p><h1>Pass the device to {roleNames[actor]}.</h1><p>{complete ? "The other person’s explanation is hidden. Now it is this person’s turn." : "Only this person should see and complete the next screen."}</p><button className="button primary" type="button" onClick={onHandoff}>I’m {roleNames[actor]} — start <span>→</span></button><small>This is a guided same-device handoff, not identity verification.</small></section>;
  }
  const previous = latestTeachbackFor(session, actor);
  const focused = previous?.overall_state === "partially_matches" || previous?.overall_state === "insufficient";
  const unresolved = version?.terms.filter((term) => term.state === "conflicting" || term.state === "stated_by_one") ?? [];
  const followUp = previous?.follow_up_question ?? previous?.missing_or_contradictory_summary;
  return (
    <section className="guided-task understanding-task" aria-labelledby="understanding-title">
      <header className="guided-heading"><p className="eyebrow">{roleNames[actor]} · private turn</p><h1 id="understanding-title">{focused ? "One detail is missing from your explanation." : "Explain the agreement in your own words"}</h1><p>{focused ? followUp : "This checks that both people understood the same terms. It does not change the agreement."}</p></header>
      {previous?.overall_state === "matches" && <div className="plain-success" role="status">Your understanding matches the recorded terms.</div>}
      <form onSubmit={onSubmit}>
        <div className="guided-field"><label htmlFor="understanding-text">{focused ? (followUp ?? "Add the missing detail") : `${roleNames[actor]}’s explanation`}</label><textarea id="understanding-text" rows={focused ? 4 : 7} value={text} maxLength={4000} onChange={(event) => onText(event.target.value)} placeholder={focused ? "Add only the missing detail…" : "For example: I understand that the work includes…"} /></div>
        {unresolved.length > 0 && <label className="section-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => onAcknowledge(event.target.checked)} /><span>I understand the final record will show {unresolved.length === 1 ? "this point" : "these points"} as unresolved.</span></label>}
        <div className="guided-actions"><button className="button primary" type="submit" disabled={saving || text.trim().length < 12 || (unresolved.length > 0 && !acknowledged)}>{focused ? "Submit this detail" : "Submit my explanation"} <span>→</span></button><button className="button text-action" type="button" onClick={onLock}>Lock and return to handoff</button></div>
      </form>
    </section>
  );
}

function ConfirmationTask({
  session,
  actor,
  version,
  handoffReady,
  acknowledged,
  changeItemKey,
  saving,
  onHandoff,
  onAcknowledge,
  onChangeItem,
  onSubmit,
}: {
  session: LiveSessionView;
  actor: PartyRole;
  version: AgreementVersion | null;
  handoffReady: boolean;
  acknowledged: boolean;
  changeItemKey: string;
  saving: boolean;
  onHandoff: () => void;
  onAcknowledge: (checked: boolean) => void;
  onChangeItem: (key: string) => void;
  onSubmit: (decision: "confirm" | "request_change") => void;
}) {
  const otherConfirmation = session.confirmations.find((item) => item.participant_id !== actor && item.agreement_version_id === version?.id && item.invalidated_at === null);
  if (!handoffReady) {
    return <section className="guided-task handoff-task"><div className="handoff-symbol" aria-hidden="true">↗</div><p className="eyebrow">Separate confirmation</p><h1>{otherConfirmation ? `${roleNames[otherConfirmation.participant_id]} confirmed. Pass the device to ${roleNames[actor]}.` : `Pass the device to ${roleNames[actor]}.`}</h1><p>Only {roleNames[actor]} should use the next confirmation controls.</p><button className="button primary" type="button" onClick={onHandoff}>I’m {roleNames[actor]} — review <span>→</span></button><small>MeaningSync does not verify identity.</small></section>;
  }
  const unresolved = version?.terms.filter((term) => term.state === "conflicting" || term.state === "stated_by_one") ?? [];
  const mutualProposalKeys = new Set(
    version?.not_applicable_proposals
      .filter((proposal) => proposal.proposed_by.length === 2)
      .map((proposal) => proposal.item_key) ?? [],
  );
  const regularTerms =
    version?.terms.filter(
      (term) => !mutualProposalKeys.has(term.analysis_item_key),
    ) ?? [];
  const mutualNotApplicable =
    version?.terms.filter((term) =>
      mutualProposalKeys.has(term.analysis_item_key),
    ) ?? [];
  return (
    <section className="guided-task confirmation-task" aria-labelledby="confirm-title">
      <header className="guided-heading"><p className="eyebrow">{roleNames[actor]} · separate confirmation</p><h1 id="confirm-title">Confirm your understanding</h1><p>This records that you reviewed the displayed summary. It is not a signature or identity check.</p></header>
      <div className="confirmation-summary">
        <GuidedTermList terms={regularTerms} proposals={version?.not_applicable_proposals ?? []} />
        {mutualNotApplicable.length > 0 && <section className="confirmation-mutual-na"><h2>Both marked not applicable</h2><GuidedTermList terms={mutualNotApplicable} proposals={version?.not_applicable_proposals ?? []} /></section>}
      </div>
      {unresolved.length > 0 && <label className="section-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => onAcknowledge(event.target.checked)} /><span>I understand the receipt will keep {unresolved.length === 1 ? "this point" : "these points"} unresolved.</span></label>}
      <div className="change-control"><label htmlFor="change-item">If something is wrong, choose what needs to change</label><select id="change-item" value={changeItemKey} onChange={(event) => onChangeItem(event.target.value)}><option value="">Choose a recorded item</option>{version?.terms.map((term) => <option key={term.analysis_item_key} value={term.analysis_item_key}>{term.label}</option>)}</select></div>
      <div className="guided-actions"><button className="button primary" type="button" disabled={saving || (unresolved.length > 0 && !acknowledged)} onClick={() => onSubmit("confirm")}>Confirm my understanding <span>→</span></button><button className="button text-action" type="button" disabled={saving || !changeItemKey} onClick={() => onSubmit("request_change")}>I need to change something</button></div>
    </section>
  );
}

function ReceiptReady({
  session,
  action,
  label,
  saving,
  onIssue,
}: {
  session: LiveSessionView;
  action: "issue_receipt" | "view_receipt";
  label: string;
  saving: boolean;
  onIssue: () => void;
}) {
  return (
    <section className="guided-task receipt-ready" aria-labelledby="receipt-ready-title">
      <div className="outcome-symbol" aria-hidden="true">✓</div>
      <p className="eyebrow">Both people confirmed</p>
      <h1 id="receipt-ready-title">Both understandings are recorded.</h1>
      <ParticipantStatus session={session} />
      <p>The clarity receipt keeps matching, unresolved, and not-discussed points exactly as reviewed. It is not a legal contract.</p>
      {action === "view_receipt" ? <Link className="button primary" href={`/live/${encodeURIComponent(session.id)}/receipt`}>{label} <span>→</span></Link> : <button className="button primary" type="button" disabled={saving || !session.receipt_ready} onClick={onIssue}>{label} <span>→</span></button>}
    </section>
  );
}

function ParticipantStatus({ session }: { session: LiveSessionView }) {
  return (
    <div className="guided-participant-status" aria-label="Participant confirmation status">
      {(["hirer", "worker"] as PartyRole[]).map((party) => {
        const confirmed = session.confirmations.some((item) => item.participant_id === party && item.agreement_version_id === session.current_agreement_version_id && item.invalidated_at === null);
        return <div key={party}><span className={`avatar small ${party === "worker" ? "worker" : ""}`}>{roleNames[party][0]}</span><p><strong>{roleNames[party]}</strong><span>{confirmed ? "Confirmed" : "Not confirmed yet"}</span></p><i aria-label={confirmed ? "Confirmed" : "Pending"}>{confirmed ? "✓" : "○"}</i></div>;
      })}
    </div>
  );
}
