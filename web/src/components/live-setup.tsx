"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import {
  api,
  MeaningSyncApiError,
  type CurrencyCode,
  type LanguageCode,
  type LiveParticipationMode,
  type PartyRole,
} from "@/lib/api";
import { otherRole, roleLabel } from "@/lib/flow-presentation";
import { storeLiveAccess } from "@/lib/live-access";
import { useScrollToTop } from "@/lib/use-scroll-to-top";

const roles: PartyRole[] = ["hirer", "worker"];

export function LiveSetup() {
  const router = useRouter();
  const [step, setStep] = useState<"preferences" | "participation">(
    "preferences",
  );
  const [languages, setLanguages] = useState<Record<PartyRole, LanguageCode>>({
    hirer: "en",
    worker: "en",
  });
  const [currency, setCurrency] = useState<CurrencyCode>("INR");
  const [creatorRole, setCreatorRole] = useState<PartyRole>("hirer");
  const [displayName, setDisplayName] = useState("");
  const [participationMode, setParticipationMode] =
    useState<LiveParticipationMode>("same_device");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported = [languages.hirer, languages.worker].every((item) =>
    ["en", "hi"].includes(item),
  );

  useScrollToTop(`live-setup:${step}`);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!supported) return;
    if (step === "preferences") {
      setStep("participation");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const session = await api.createLiveSession({
        participants: [
          {
            id: "hirer",
            role: "hirer",
            language: languages.hirer,
            display_name: creatorRole === "hirer" ? displayName.trim() || null : null,
          },
          {
            id: "worker",
            role: "worker",
            language: languages.worker,
            display_name: creatorRole === "worker" ? displayName.trim() || null : null,
          },
        ],
        messages: [],
        participation_mode: participationMode,
        currency,
        creator_role: creatorRole,
      });
      storeLiveAccess(session.id, session.access_credentials);
      if (participationMode === "separate_devices") {
        if (!session.invitation) {
          throw new MeaningSyncApiError(
            "A joining invitation could not be created.",
          );
        }
        const fragment = new URLSearchParams({
          invite: session.invitation.invitation,
          expires: session.invitation.expires_at,
          role: session.invitation.role,
        });
        router.push(
          `/live/${encodeURIComponent(session.id)}/waiting#${fragment.toString()}`,
        );
      } else {
        router.push(`/live/${encodeURIComponent(session.id)}`);
      }
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The Live session could not be created.",
      );
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <LiveBrandBar trailing={<span className="guided-mode-note">Live · text only</span>} />
      <section className="setup-page conversation-setup">
        <LiveProgress
          currentStage={step}
          explanation={
            step === "preferences"
              ? "Choose how each person reads the conversation."
              : "Choose who is creating the session and how both people will join."
          }
        />
        <header className="flow-heading">
          <span>{step === "preferences" ? "Preferences" : "Participation"}</span>
          <h1>
            {step === "preferences"
              ? "Set up the conversation"
              : "Who are you?"}
          </h1>
          <p>
            {step === "preferences"
              ? "Original wording and currencies stay unchanged in the evidence."
              : "The other person will take the opposite role in this session."}
          </p>
        </header>

        <form onSubmit={submit}>
          {step === "preferences" ? (
            <>
              <div className="setup-grid">
                {roles.map((role) => (
                  <article className="setup-card" key={role}>
                    <div className="setup-participant">
                      <span>{role === "hirer" ? "Participant 1" : "Participant 2"}</span>
                      <h2>{roleLabel(role)}</h2>
                    </div>
                    <label htmlFor={`live-${role}-language`}>Language</label>
                    <select
                      id={`live-${role}-language`}
                      value={languages[role]}
                      onChange={(event) =>
                        setLanguages((current) => ({
                          ...current,
                          [role]: event.target.value as LanguageCode,
                        }))
                      }
                    >
                      <option value="en">English</option>
                      <option value="hi">Hindi</option>
                    </select>
                  </article>
                ))}
              </div>
              <label className="setup-currency" htmlFor="live-currency">
                Session currency
                <select
                  id="live-currency"
                  value={currency}
                  onChange={(event) =>
                    setCurrency(event.target.value as CurrencyCode)
                  }
                >
                  <option value="INR">INR — Indian rupee</option>
                  <option value="USD">USD — US dollar</option>
                  <option value="EUR">EUR — Euro</option>
                </select>
                <small>No currency conversion is performed.</small>
              </label>
            </>
          ) : (
            <>
              <fieldset className="live-role-picker">
                <legend>Choose your role</legend>
                {roles.map((role) => (
                  <label key={role}>
                    <input
                      type="radio"
                      name="creator-role"
                      value={role}
                      checked={creatorRole === role}
                      onChange={() => setCreatorRole(role)}
                    />
                    <span><strong>I am the {roleLabel(role)}</strong></span>
                  </label>
                ))}
              </fieldset>
              <label className="setup-name" htmlFor="creator-display-name">
                What should MeaningSync call you?
                <input
                  id="creator-display-name"
                  maxLength={80}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder={roleLabel(creatorRole)}
                />
                <small>
                  Optional — leave blank to use {roleLabel(creatorRole)}. This is
                  a display name, not identity verification.
                </small>
              </label>
              <fieldset className="live-mode-picker">
                <legend>How will you take part?</legend>
                <label>
                  <input
                    type="radio"
                    name="participation-mode"
                    value="same_device"
                    checked={participationMode === "same_device"}
                    onChange={() => setParticipationMode("same_device")}
                  />
                  <span>
                    <strong>Share this device</strong>
                    <small>Pass this screen between both people.</small>
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="participation-mode"
                    value="separate_devices"
                    checked={participationMode === "separate_devices"}
                    onChange={() => setParticipationMode("separate_devices")}
                  />
                  <span>
                    <strong>Use separate devices</strong>
                    <small>Invite the {roleLabel(otherRole(creatorRole)).toLowerCase()} with a private link.</small>
                  </span>
                </label>
              </fieldset>
            </>
          )}

          {error ? <p className="analysis-error" role="alert">{error}</p> : null}
          <div className="setup-actions">
            {step === "preferences" ? (
              <Link className="button secondary" href="/">Back to home</Link>
            ) : (
              <button
                className="button secondary"
                type="button"
                onClick={() => setStep("preferences")}
              >
                Back
              </button>
            )}
            <button className="button primary" type="submit" disabled={!supported || loading}>
              {loading ? "Creating session…" : step === "preferences" ? "Continue" : "Start conversation"} <span>→</span>
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
