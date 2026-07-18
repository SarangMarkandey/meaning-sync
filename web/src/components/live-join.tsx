"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import { api, MeaningSyncApiError, type PartyRole } from "@/lib/api";
import { roleLabel } from "@/lib/flow-presentation";
import { storeLiveAccess } from "@/lib/live-access";
import { useScrollToTop } from "@/lib/use-scroll-to-top";

type JoinState = "checking" | "consent" | "joining" | "failed";

export function LiveJoin() {
  const router = useRouter();
  const invitationRef = useRef<string | null>(null);
  const [state, setState] = useState<JoinState>("checking");
  const [role, setRole] = useState<PartyRole>("worker");
  const [message, setMessage] = useState("Checking your private invitation…");

  useScrollToTop(`live-join:${state}`);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    window.history.replaceState(null, "", window.location.pathname);
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      const fragment = new URLSearchParams(hash);
      const invitation = fragment.get("invite");
      const invitedRole = fragment.get("role");
      if (!invitation) {
        setState("failed");
        setMessage("This joining link is incomplete. Ask the session creator for a new link.");
        return;
      }
      invitationRef.current = invitation;
      if (invitedRole === "hirer" || invitedRole === "worker") {
        setRole(invitedRole);
      }
      setState("consent");
      setMessage("Review the notice, then join this conversation in one step.");
    });
    return () => {
      active = false;
    };
  }, []);

  const join = async () => {
    const invitation = invitationRef.current;
    if (!invitation) return;
    invitationRef.current = null;
    setState("joining");
    setMessage("Connecting you to this MeaningSync session…");
    try {
      const result = await api.exchangeLiveInvitation(invitation);
      storeLiveAccess(result.session_id, [
        {
          role: result.role,
          access_token: result.access_token,
          expires_at: result.expires_at,
        },
      ]);
      router.replace(`/live/${encodeURIComponent(result.session_id)}`);
    } catch (caught) {
      setState("failed");
      setMessage(
        caught instanceof MeaningSyncApiError
          ? caught.message
          : "MeaningSync could not connect this device. Ask for a new link.",
      );
    }
  };

  return (
    <main className="app-shell">
      <LiveBrandBar />
      <section className="join-page">
        <LiveProgress
          currentStage="participation"
          explanation="Join the session before the conversation begins."
        />
        <article className="join-status-card" aria-live="polite">
          <p className="eyebrow">MeaningSync Live</p>
          <h1>
            {state === "failed"
              ? "This link cannot be used"
              : `Join as ${roleLabel(role)}`}
          </h1>
          <p>{message}</p>
          <div className="privacy-note" role="note">
            <strong>Before you join</strong>
            <span>
              Your messages and choices are sent only to this session. MeaningSync
              does not verify identity, provide legal advice, or create a legal contract.
            </span>
          </div>
          {state === "consent" ? (
            <button className="button primary" type="button" onClick={() => void join()}>
              Join as {roleLabel(role)} <span>→</span>
            </button>
          ) : state === "joining" || state === "checking" ? (
            <p role="status">Please wait…</p>
          ) : (
            <Link className="button secondary" href="/">Return home</Link>
          )}
        </article>
      </section>
    </main>
  );
}
