"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import { ConfirmationSummary } from "@/components/confirmation-summary";
import { ChatMessageList, ConversationGuide } from "@/components/conversation-view";
import { LiveAudioComposer } from "@/components/live-audio-composer";
import { AgreementMap } from "@/components/agreement-map";
import {
  api,
  MeaningSyncApiError,
  type AgreementVersion,
  type LiveSessionView,
  type PartyRole,
  type UnderstandingQuestion,
} from "@/lib/api";
import {
  otherRole,
  participantLabel,
  presentationFor,
  roleLabel,
} from "@/lib/flow-presentation";
import { getAnyLiveAccess, getLiveAccess } from "@/lib/live-access";
import { useScrollToTop } from "@/lib/use-scroll-to-top";
import { t } from "@/lib/i18n";

const roles: PartyRole[] = ["hirer", "worker"];
const requestId = () =>
  globalThis.crypto?.randomUUID?.() ?? `request-${Date.now()}`;

function currentVersion(session: LiveSessionView): AgreementVersion | null {
  return (
    session.agreement_versions.find(
      (version) => version.id === session.current_agreement_version_id,
    ) ?? null
  );
}

function requiredOpenKeys(version: AgreementVersion) {
  return version.terms
    .filter(
      (term) =>
        term.state === "conflicting" || term.state === "stated_by_one",
    )
    .map((term) => term.analysis_item_key);
}

export function LiveSessionExperience({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [session, setSession] = useState<LiveSessionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [composerRole, setComposerRole] = useState<PartyRole>("hirer");
  const [message, setMessage] = useState("");
  const [selectedOption, setSelectedOption] = useState("");
  const [otherText, setOtherText] = useState("");
  const [changeItem, setChangeItem] = useState("");
  const [handoffComplete, setHandoffComplete] = useState(
    () =>
      typeof window !== "undefined" &&
      window.sessionStorage.getItem(
        `meaningsync-name-handoff:${sessionId}`,
      ) === "complete",
  );

  useScrollToTop(
    session
      ? [
          "live",
          session.stage,
          session.guidance.active_question_id ?? "none",
          session.active_participant_id ?? "none",
          session.current_agreement_version_id ?? "none",
        ].join(":")
      : "live:loading",
  );

  const tokenFor = useCallback(
    (role?: PartyRole | null) =>
      (role ? getLiveAccess(sessionId, role) : null) ??
      getAnyLiveAccess(sessionId)?.token ??
      "",
    [sessionId],
  );

  const load = useCallback(async () => {
    try {
      const next = await api.getLiveSession(sessionId, tokenFor());
      setSession(next);
      if (next.participation_mode === "separate_devices" && next.viewer_role) {
        setComposerRole(next.viewer_role);
      }
      setLoadError(null);
    } catch (caught) {
      if (
        caught instanceof MeaningSyncApiError &&
        [
          "session_expired",
          "access_required",
          "access_invalid",
          "access_expired",
          "access_revoked",
        ].includes(caught.code)
      ) {
        setSession(null);
      }
      setLoadError(
        caught instanceof Error
          ? caught.message
          : "This Live session could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId, tokenFor]);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 1500);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [load]);

  const mutate = async (operation: () => Promise<LiveSessionView>) => {
    setSaving(true);
    setOperationError(null);
    try {
      setSession(await operation());
    } catch (caught) {
      setOperationError(
        caught instanceof MeaningSyncApiError
          ? caught.message
          : "MeaningSync could not complete that step.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingSession />;
  }

  if (!session) {
    return (
      <main className="app-shell">
        <LiveBrandBar />
        <section className="session-recovery" role="alert">
          <span>Session unavailable</span>
          <h1>We could not open this Live session.</h1>
          <p>{loadError}</p>
          <div>
            <Link className="button primary" href="/live/setup">Start a new session</Link>
            <button className="button secondary" type="button" onClick={() => { setLoading(true); void load(); }}>Try again</button>
          </div>
        </section>
      </main>
    );
  }

  const version = currentVersion(session);
  const error = operationError ?? loadError;
  const presentation = presentationFor(session);
  const activeQuestion = session.guidance.active_question_id
    ? session.questions.find(
        (question) => question.id === session.guidance.active_question_id,
      ) ?? null
    : null;
  const flowLanguage = session.participants.find(
    (participant) =>
      participant.role ===
      (session.active_participant_id ?? session.viewer_role ?? session.creator_role),
  )?.language ?? "en";

  const sharedParticipantRole = otherRole(session.creator_role);
  const sharedParticipant = session.participants.find(
    (participant) => participant.role === sharedParticipantRole,
  );
  if (
    session.participation_mode === "same_device" &&
    !handoffComplete &&
    !sharedParticipant?.display_name
  ) {
    const participantRole = sharedParticipantRole;
    return (
      <SharedDeviceNameHandoff
        role={participantRole}
        saving={saving}
        onSubmit={(displayName) =>
          void mutate(async () => {
            const next = await api.updateParticipantProfile(
              session.id,
              displayName,
              requestId(),
              tokenFor(participantRole),
            );
            window.sessionStorage.setItem(
              `meaningsync-name-handoff:${sessionId}`,
              "complete",
            );
            setHandoffComplete(true);
            return next;
          })
        }
      />
    );
  }

  return (
    <main className="app-shell">
      <LiveBrandBar trailing={<span className="guided-mode-note">Live · text or audio</span>} />
      <section className="guided-flow-page conversation-first-flow">
        <LiveProgress
          currentStage={presentation.stage}
          language={flowLanguage}
          explanation={
            presentation.stage === "conversation"
              ? "Add messages naturally, then both people mark themselves ready."
              : presentation.stage === "check_understanding"
                ? "Only genuine differences and open points need action."
                : presentation.stage === "confirm"
                  ? "Each person confirms the same version separately."
                  : "The shared record is complete."
          }
        />
        {error ? <div className="guided-error" role="alert"><p>{error}</p><button className="text-action" type="button" onClick={() => { setOperationError(null); void load(); }}>Dismiss and refresh</button></div> : null}

        {session.stage === "analyzing" ? (
          <AnalysisLoading />
        ) : presentation.stage === "conversation" ? (
          <ConversationStep
            session={session}
            version={version}
            composerRole={composerRole}
            message={message}
            saving={saving}
            onComposerRole={setComposerRole}
            onMessage={setMessage}
            onSession={setSession}
            accessToken={tokenFor(composerRole)}
            onSend={() => {
              const text = message.trim();
              if (text.length < 2) return;
              void mutate(async () => {
                const next = await api.addDraftStatement(
                  session.id,
                  text,
                  requestId(),
                  tokenFor(composerRole),
                );
                setMessage("");
                return next;
              });
            }}
            onReady={(role, ready) =>
              void mutate(() =>
                api.setLiveReadiness(
                  session.id,
                  ready,
                  requestId(),
                  tokenFor(role),
                ),
              )
            }
            onCompare={() =>
              void mutate(() =>
                api.analyzeLiveSession(
                  session.id,
                  session.current_agreement_version_id,
                  tokenFor(session.creator_role),
                ),
              )
            }
          />
        ) : presentation.stage === "check_understanding" && version ? (
          <UnderstandingStep
            session={session}
            version={version}
            question={activeQuestion}
            selectedOption={selectedOption}
            otherText={otherText}
            saving={saving}
            onOption={setSelectedOption}
            onOtherText={setOtherText}
            onSubmitChoice={() => {
              if (!activeQuestion || !session.active_participant_id) return;
              const option = activeQuestion.options.find(
                (item) => item.id === selectedOption,
              );
              if (!option) return;
              const actor = session.active_participant_id;
              void mutate(async () => {
                const next = await api.submitUnderstandingSelection(
                  session.id,
                  activeQuestion.id,
                  {
                    participant_id: actor,
                    option_id: option.id,
                    ...(option.kind === "other"
                      ? { other_text: otherText.trim() }
                      : {}),
                    expected_agreement_version_id: version.id,
                    request_id: requestId(),
                  },
                  tokenFor(actor),
                );
                setSelectedOption("");
                setOtherText("");
                return next;
              });
            }}
            onLeave={() => {
              if (!activeQuestion || !session.active_participant_id) return;
              const actor = session.active_participant_id;
              void mutate(() =>
                api.leaveLiveQuestionUnresolved(
                  session.id,
                  activeQuestion.id,
                  {
                    participant_id: actor,
                    expected_agreement_version_id: version.id,
                    request_id: requestId(),
                  },
                  tokenFor(actor),
                ),
              );
            }}
            onDiscuss={(itemKey) =>
              void mutate(() =>
                api.reenterLiveConversation(
                  session.id,
                  version.id,
                  itemKey,
                  requestId(),
                  tokenFor(),
                ),
              )
            }
            onContinue={() =>
              void mutate(() =>
                api.beginUnderstandingCheck(
                  session.id,
                  {
                    expected_agreement_version_id: version.id,
                    acknowledged_unresolved_item_keys: requiredOpenKeys(version),
                    request_id: requestId(),
                  },
                  tokenFor(session.creator_role),
                ),
              )
            }
          />
        ) : presentation.stage === "confirm" && version ? (
          <ConfirmStep
            session={session}
            version={version}
            saving={saving}
            changeItem={changeItem}
            onChangeItem={setChangeItem}
            onConfirm={(decision) => {
              const actor = session.active_participant_id;
              if (!actor) return;
              const review = session.understanding_reviews[actor];
              if (!review) return;
              void mutate(() =>
                api.submitLiveConfirmation(
                  session.id,
                  {
                    participant_id: actor,
                    expected_agreement_version_id: version.id,
                    understanding_review_id: review.id,
                    decision,
                    unresolved_item_acknowledgments: requiredOpenKeys(version),
                    ...(decision === "request_change"
                      ? { change_item_key: changeItem }
                      : {}),
                    request_id: requestId(),
                  },
                  tokenFor(actor),
                ),
              );
            }}
            onReceipt={async () => {
              setSaving(true);
              try {
                await api.issueLiveReceipt(
                  session.id,
                  version.id,
                  requestId(),
                  tokenFor(session.creator_role),
                );
                router.push(`/live/${encodeURIComponent(session.id)}/receipt`);
              } catch (caught) {
                setOperationError(caught instanceof Error ? caught.message : "The receipt could not be created.");
                setSaving(false);
              }
            }}
          />
        ) : (
          <section className="guided-task">
            <h1>The clarity receipt is ready</h1>
            <Link className="button primary" href={`/live/${encodeURIComponent(session.id)}/receipt`}>View receipt</Link>
          </section>
        )}

        <footer className="guided-disclaimer">
          MeaningSync compares stated meaning. It does not provide legal advice,
          verify identity, or create a legal contract.
        </footer>
      </section>
    </main>
  );
}

function ConversationStep({
  session,
  version,
  composerRole,
  message,
  saving,
  onComposerRole,
  onMessage,
  onSession,
  accessToken,
  onSend,
  onReady,
  onCompare,
}: {
  session: LiveSessionView;
  version: AgreementVersion | null;
  composerRole: PartyRole;
  message: string;
  saving: boolean;
  onComposerRole: (role: PartyRole) => void;
  onMessage: (value: string) => void;
  onSession: (session: LiveSessionView) => void;
  accessToken: string;
  onSend: () => void;
  onReady: (role: PartyRole, ready: boolean) => void;
  onCompare: () => void;
}) {
  const [inputMode, setInputMode] = useState<"type" | "speak">("type");
  const separate = session.participation_mode === "separate_devices";
  const canCompose = !separate || composerRole === session.viewer_role;
  const contributors = new Set(session.messages.map((item) => item.speaker_id));
  const bothReady = roles.every((role) => session.participant_readiness[role]);
  const readyRole = roles.find((role) => session.participant_readiness[role]);
  const bothSpoke = roles.every((role) => contributors.has(role));
  const creatorCanCompare = !separate || session.viewer_role === session.creator_role;
  const focusTerm = version?.terms.find(
    (term) => term.analysis_item_key === session.conversation_reentry_item_key,
  );
  const composerParticipant = session.participants.find((item) => item.role === composerRole);
  const composerLanguage = composerParticipant?.language ?? "en";

  return (
    <section className="guided-task conversation-step" aria-labelledby="conversation-title">
      <header className="guided-heading">
        <p className="eyebrow">{t(composerLanguage, "conversation")}</p>
        <h1 id="conversation-title">{t(composerLanguage, "talkTitle")}</h1>
        <p>{t(composerLanguage, "talkHelp")}</p>
      </header>
      <ConversationGuide />
      {focusTerm ? (
        <div className="conversation-focus" role="status">
          <strong>Revisit: {focusTerm.label}</strong>
          <span>{focusTerm.summary}</span>
        </div>
      ) : null}
      <ChatMessageList
        preferredLanguage={session.participants.find((item) => item.role === (session.viewer_role ?? composerRole))?.language ?? "en"}
        onRetryTranslation={(messageId) => void api.retryMessageTranslation(session.id, messageId, requestId(), accessToken).then(onSession)}
        messages={session.messages.map((item) => {
          const speaker = session.participants.find((participant) => participant.id === item.speaker_id);
          const preferredLanguage = session.participants.find((participant) => participant.role === (session.viewer_role ?? composerRole))?.language ?? "en";
          const translation = item.translations?.[preferredLanguage];
          return {
            id: item.message_id,
            role: item.speaker_id as PartyRole,
            roleName: speaker ? participantLabel(speaker) : roleLabel(item.speaker_id as PartyRole),
            text: item.effective_text ?? item.original_text,
            order: item.order,
            timestamp: item.timestamp,
            inputSource: item.input_source ?? "text",
            rawTranscript: item.raw_transcript,
            correctedText: item.corrected_text,
            originalLanguage: item.original_language,
            translatedText: translation?.translated_text,
            translationStatus: translation?.status,
            translationLanguage: translation?.target_language,
          };
        })}
      />
      {!separate ? (
        <div className="composer-role-tabs" aria-label="Choose who is speaking">
          {roles.map((role) => (
            <button className={composerRole === role ? "active" : ""} type="button" key={role} onClick={() => { setInputMode("type"); onComposerRole(role); }}>{participantLabel(session.participants.find((item) => item.role === role)!)}</button>
          ))}
        </div>
      ) : null}
      <fieldset className="input-mode-picker">
        <legend>How would you like to contribute?</legend>
        <button className={inputMode === "type" ? "active" : ""} type="button" aria-pressed={inputMode === "type"} onClick={() => setInputMode("type")}><strong>{t(composerLanguage, "type")}</strong><span>Send text messages.</span></button>
        <button className={inputMode === "speak" ? "active" : ""} type="button" aria-pressed={inputMode === "speak"} disabled={!canCompose || saving} onClick={() => setInputMode("speak")}><strong>{t(composerLanguage, "speak")}</strong><span>Use your microphone and review each transcript before adding it.</span></button>
      </fieldset>
      {inputMode === "type" ? (
        <div className="chat-composer">
          <label htmlFor="conversation-message">Message as {roleLabel(composerRole)}</label>
          <textarea
            id="conversation-message"
            rows={3}
            maxLength={2000}
            value={message}
            disabled={!canCompose || saving}
            onChange={(event) => onMessage(event.target.value)}
            placeholder="Type your message…"
          />
          <button className="button secondary" type="button" disabled={!canCompose || saving || message.trim().length < 2} onClick={onSend}>Send message</button>
          <small>{canCompose ? "Type at least two characters to send." : `Only ${roleLabel(session.viewer_role ?? composerRole)} can send from this device.`}</small>
        </div>
      ) : (
        <LiveAudioComposer
          key={`${session.id}-${composerRole}`}
          session={session}
          role={composerRole}
          accessToken={accessToken}
          disabled={!canCompose || saving || session.participant_readiness[composerRole]}
          onSession={onSession}
          onContinueWithText={() => setInputMode("type")}
        />
      )}
      <div className="readiness-grid">
        {roles.map((role) => {
          const ready = session.participant_readiness[role];
          const canAct = !separate || session.viewer_role === role;
          return (
            <article key={role}>
              <span>{roleLabel(role)}</span>
              <strong>{ready ? "Ready to review" : "Still talking"}</strong>
              {canAct ? <button className={ready ? "text-action" : "button secondary"} type="button" disabled={saving} onClick={() => onReady(role, !ready)}>{ready ? "Keep talking" : "I’m ready to review"}</button> : null}
            </article>
          );
        })}
      </div>
      {creatorCanCompare ? (
        <button aria-describedby="compare-requirement" className="button primary compare-action" type="button" disabled={saving || !bothReady || !bothSpoke} onClick={onCompare}>
          {saving ? "Comparing…" : "Compare our understanding"} <span>→</span>
        </button>
      ) : (
        <p className="muted-copy">Waiting for {roleLabel(session.creator_role)} to compare when both people are ready.</p>
      )}
      <p className="muted-copy" id="compare-requirement">
        {!bothSpoke
          ? "Both people need to send at least one message before comparison."
          : readyRole && !bothReady
            ? `${roleLabel(readyRole)} is ready to review. You can continue talking or mark the other person ready.`
          : !bothReady
            ? "Both people need to select “I’m ready to review” before comparison."
            : creatorCanCompare
              ? "Both people are ready. You can compare now or continue talking."
              : "Both people are ready. Waiting for the comparison to begin."}
      </p>
    </section>
  );
}

function UnderstandingStep({
  session,
  version,
  question,
  selectedOption,
  otherText,
  saving,
  onOption,
  onOtherText,
  onSubmitChoice,
  onLeave,
  onDiscuss,
  onContinue,
}: {
  session: LiveSessionView;
  version: AgreementVersion;
  question: UnderstandingQuestion | null;
  selectedOption: string;
  otherText: string;
  saving: boolean;
  onOption: (value: string) => void;
  onOtherText: (value: string) => void;
  onSubmitChoice: () => void;
  onLeave: () => void;
  onDiscuss: (itemKey: string) => void;
  onContinue: () => void;
}) {
  const decisions = version.terms.filter(
    (term) => term.state === "conflicting" || term.state === "stated_by_one",
  );
  const actor = session.active_participant_id;
  const actorParticipant = session.participants.find((item) => item.role === actor);
  const actorLanguage = actorParticipant?.language ?? "en";
  const separateWaiting =
    session.participation_mode === "separate_devices" &&
    actor &&
    actor !== session.viewer_role;
  const outcome = question?.outcome ?? session.questions
    .filter((item) => item.agreement_item_id === question?.agreement_item_id)
    .findLast((item) => item.outcome)?.outcome;
  const disagreement = question?.status === "needs_clarification" || question?.status === "unsure";
  const decisionTerm = question
    ? version.terms.find(
        (term) => term.analysis_item_key === question.agreement_item_id,
      )
    : null;
  const decisionPrompt = decisionTerm?.state === "stated_by_one"
    ? `${actor ? roleLabel(actor) : "The other person"}, should this be included in the agreement?`
    : "What should the clarity receipt record?";
  const evidenceCurrencies = detectedEvidenceCurrencies(session.messages);
  const mismatchedCurrencies = evidenceCurrencies.filter(
    (currency) => currency !== session.currency,
  );

  return (
    <section className="guided-task understanding-step">
      <header className="guided-heading">
        <p className="eyebrow">Check understanding</p>
        <h1>Check your shared understanding</h1>
        <p>MeaningSync compared the conversation. Review what matches, resolve any differences and leave anything undiscussed open.</p>
      </header>
      {mismatchedCurrencies.length ? (
        <div className="currency-mismatch" role="note">
          <strong>Currency differs in the original conversation</strong>
          <p>
            This session uses {session.currency}, while evidence also mentions {mismatchedCurrencies.join(", ")}.
            Original amounts are preserved and no conversion is applied.
          </p>
        </div>
      ) : null}
      <AgreementMap terms={version.terms} roleMode="live" language={actorLanguage} onDiscussMissing={onDiscuss} />

      {question ? (
        <div className="decision-panel">
          {separateWaiting ? (
            <p role="status">Waiting for {roleLabel(actor)} to answer privately.</p>
          ) : disagreement ? (
            <>
              <p className="eyebrow">Still open</p>
              <h2>You still understand this differently.</h2>
              {outcome?.positions.map((position) => (
                <p key={position.participant_id}><strong>{roleLabel(position.participant_id)}:</strong> {position.label}</p>
              ))}
              <div className="guided-actions">
                <button className="button primary" type="button" onClick={() => onDiscuss(question.agreement_item_id)}>Discuss this again</button>
                <button className="button secondary" type="button" disabled={saving} onClick={onLeave}>Leave unresolved</button>
              </div>
            </>
          ) : actor ? (
            <>
              {session.participation_mode === "same_device" ? (
                <div className="handoff-notice" role="status">
                  <strong>Pass this screen to {roleLabel(actor)}</strong>
                  <span>Only {roleLabel(actor)} should make the next private choice.</span>
                </div>
              ) : null}
              <p className="eyebrow">Private choice · {actorParticipant ? participantLabel(actorParticipant) : roleLabel(actor)}</p>
              <h2 lang={actorLanguage}>{question.prompt_localizations?.[actorLanguage] ?? decisionPrompt}</h2>
              <p>Your choice stays hidden until everyone addressed by this question has answered.</p>
              <fieldset className="choice-list">
                <legend>Choose what should be recorded</legend>
                {question.options.map((option) => (
                  <label key={option.id}>
                    <input type="radio" name={`choice-${question.id}`} value={option.id} checked={selectedOption === option.id} onChange={() => onOption(option.id)} />
                    <span>
                      {option.kind === "unsure"
                        ? decisionTerm?.state === "stated_by_one"
                          ? "Leave this unresolved"
                          : "We have not agreed on this yet"
                        : option.localizations?.[actorLanguage] ?? option.label}
                    </span>
                  </label>
                ))}
              </fieldset>
              {question.options.find((item) => item.id === selectedOption)?.kind === "other" ? (
                <label className="composer-field" htmlFor="other-meaning">Describe the meaning<input id="other-meaning" value={otherText} onChange={(event) => onOtherText(event.target.value)} /></label>
              ) : null}
              <div className="guided-actions">
                <button className="button primary" type="button" disabled={saving || !selectedOption || (question.options.find((item) => item.id === selectedOption)?.kind === "other" && otherText.trim().length < 2)} onClick={onSubmitChoice}>Submit my choice</button>
                <button className="text-action" type="button" disabled={saving} onClick={onLeave}>{t(actorLanguage, "leaveUnresolved")}</button>
              </div>
            </>
          ) : null}
        </div>
      ) : (
        <div className="guided-actions understanding-actions">
          {decisions.map((term) => <button className="text-action" type="button" key={term.analysis_item_key} onClick={() => onDiscuss(term.analysis_item_key)}>Discuss {term.label.toLowerCase()}</button>)}
          {session.viewer_role === session.creator_role || session.participation_mode !== "separate_devices" ? (
            <button className="button primary" type="button" disabled={saving} onClick={onContinue}>Continue to confirmation <span>→</span></button>
          ) : <p>Waiting for {roleLabel(session.creator_role)} to continue.</p>}
        </div>
      )}
    </section>
  );
}

function AnalysisLoading() {
  return (
    <section className="guided-task conversation-step" aria-labelledby="analysis-title">
      <header className="guided-heading">
        <p className="eyebrow">Check understanding</p>
        <h1 id="analysis-title">Comparing your understanding</h1>
        <p>MeaningSync is reviewing the complete conversation. This may take a moment.</p>
      </header>
      <div className="guided-loading" role="status" aria-live="polite">
        <span className="loading-spinner" aria-hidden="true" />
        <strong>Preparing your shared understanding…</strong>
      </div>
    </section>
  );
}

function detectedEvidenceCurrencies(messages: LiveSessionView["messages"]) {
  const found = new Set<string>();
  for (const message of messages) {
    if (/₹|\bINR\b|\bRs\.?\s?\d/i.test(message.original_text)) found.add("INR");
    if (/\$|\bUSD\b/i.test(message.original_text)) found.add("USD");
    if (/€|\bEUR\b/i.test(message.original_text)) found.add("EUR");
  }
  return [...found];
}

function ConfirmStep({ session, version, saving, changeItem, onChangeItem, onConfirm, onReceipt }: { session: LiveSessionView; version: AgreementVersion; saving: boolean; changeItem: string; onChangeItem: (value: string) => void; onConfirm: (decision: "confirm" | "request_change") => void; onReceipt: () => void }) {
  const actor = session.active_participant_id;
  const actorParticipant = session.participants.find((item) => item.role === actor);
  const actorLanguage = actorParticipant?.language ?? "en";
  const confirmedRoles = new Set(session.confirmations.filter((item) => !item.invalidated_at && item.agreement_version_id === version.id).map((item) => item.participant_id));
  const bothConfirmed = confirmedRoles.size === 2;
  const canAct = actor && (session.participation_mode !== "separate_devices" || session.viewer_role === actor);
  return (
    <section className="guided-task confirm-step">
      <header className="guided-heading"><p className="eyebrow">Confirm</p><h1>Confirm this shared record</h1><p>Each person confirms this same latest summary. Open points stay open.</p></header>
      <ConfirmationSummary terms={version.terms} language={actorLanguage} />
      <div className="confirmation-status-row">{roles.map((role) => { const participant = session.participants.find((item) => item.role === role); return <div key={role}><span>{participant ? participantLabel(participant) : roleLabel(role)}</span><strong>{confirmedRoles.has(role) ? "Confirmed" : actor === role ? "Reviewing now" : "Waiting"}</strong></div>; })}</div>
      {bothConfirmed && (session.participation_mode !== "separate_devices" || session.viewer_role === session.creator_role) ? (
        <button className="button primary" type="button" disabled={saving || (session.participation_mode === "separate_devices" && session.viewer_role !== session.creator_role)} onClick={onReceipt}>Create clarity receipt <span>→</span></button>
      ) : bothConfirmed ? (
        <p role="status">Both people confirmed. Waiting for {roleLabel(session.creator_role)} to create the clarity receipt.</p>
      ) : canAct && actor ? (
        <div className="confirmation-actions">
          {session.participation_mode === "same_device" ? <p className="handoff-notice"><strong>Pass this screen to {roleLabel(actor)}</strong></p> : null}
          <h2>{actorParticipant ? participantLabel(actorParticipant) : roleLabel(actor)}, does this record match what you mean?</h2>
          <p lang={actorLanguage}>{t(actorLanguage, "confirmationStatement")}</p>
          <button className="button primary" type="button" disabled={saving} onClick={() => onConfirm("confirm")}>{t(actorLanguage, "confirmMine")}</button>
          <label htmlFor="change-item">Something needs to change<select id="change-item" value={changeItem} onChange={(event) => onChangeItem(event.target.value)}><option value="">Choose an item</option>{version.terms.map((term) => <option key={term.analysis_item_key} value={term.analysis_item_key}>{term.label}</option>)}</select></label>
          <button className="button secondary" type="button" disabled={saving || !changeItem} onClick={() => onConfirm("request_change")}>Return to conversation</button>
        </div>
      ) : <p role="status">Waiting for {roleLabel(actor ?? otherRole(session.creator_role))}.</p>}
    </section>
  );
}

function LoadingSession() {
  return <main className="app-shell"><LiveBrandBar /><div className="guided-loading" role="status"><span /> Loading this conversation…</div></main>;
}

function SharedDeviceNameHandoff({ role, saving, onSubmit }: { role: PartyRole; saving: boolean; onSubmit: (displayName: string) => void }) {
  const [displayName, setDisplayName] = useState("");
  return (
    <main className="app-shell">
      <LiveBrandBar />
      <section className="guided-flow-page">
        <LiveProgress currentStage="participation" explanation="Each person provides only their own optional display name." />
        <article className="join-status-card">
          <p className="eyebrow">Private handoff</p>
          <h1>Pass this screen to the {roleLabel(role)}</h1>
          <p>This name is for display only. MeaningSync does not verify identity.</p>
          <label className="setup-name" htmlFor="shared-display-name">
            What should MeaningSync call you?
            <input id="shared-display-name" maxLength={80} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder={roleLabel(role)} />
            <small>Optional — leave blank to use {roleLabel(role)}.</small>
          </label>
          <button className="button primary" type="button" disabled={saving} onClick={() => onSubmit(displayName)}>{saving ? "Saving…" : "Continue privately"} <span>→</span></button>
        </article>
      </section>
    </main>
  );
}
