"use client";

import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LiveBrandBar, LiveProgress } from "@/components/live-flow-shell";
import {
  api,
  MeaningSyncApiError,
  type LiveInvitation,
  type LiveSessionView,
} from "@/lib/api";
import { otherRole, roleLabel } from "@/lib/flow-presentation";
import { getAnyLiveAccess } from "@/lib/live-access";

const pollMilliseconds = Math.max(
  1000,
  Number(process.env.NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS ?? 1500),
);

export function LiveWaitingRoom({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [invitation, setInvitation] = useState<LiveInvitation | null>(null);
  const [session, setSession] = useState<LiveSessionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const stopped = useRef(false);
  const creatorAccess = useMemo(() => getAnyLiveAccess(sessionId), [sessionId]);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    window.history.replaceState(null, "", window.location.pathname);
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      const fragment = new URLSearchParams(hash);
      const raw = fragment.get("invite");
      const expiresAt = fragment.get("expires");
      const role = fragment.get("role");
      if (raw && expiresAt && (role === "hirer" || role === "worker")) {
        setInvitation({ role, invitation: raw, expires_at: expiresAt });
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!creatorAccess) {
      setError("Creator access is missing. Start a new Live session on this device.");
      stopped.current = true;
      return;
    }
    try {
      const next = await api.getLiveSession(sessionId, creatorAccess.token);
      setSession(next);
      setError(null);
      const invitedRole = otherRole(next.creator_role);
      const joined = next.participant_presence?.some(
        (presence) =>
          presence.role === invitedRole && presence.status === "connected",
      );
      if (joined) {
        stopped.current = true;
        router.replace(`/live/${encodeURIComponent(sessionId)}`);
      }
    } catch (caught) {
      if (caught instanceof MeaningSyncApiError && !caught.retryable) {
        setError(caught.message);
        stopped.current = true;
      } else {
        setError("Connection interrupted. MeaningSync will keep trying.");
      }
    }
  }, [creatorAccess, router, sessionId]);

  useEffect(() => {
    stopped.current = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      await refresh();
      if (!stopped.current) timer = setTimeout(poll, pollMilliseconds);
    };
    void poll();
    return () => {
      stopped.current = true;
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);

  const joinUrl = useMemo(() => {
    if (!invitation || typeof window === "undefined") return null;
    const publicUrl = (
      process.env.NEXT_PUBLIC_MEANINGSYNC_APP_URL ?? window.location.origin
    ).replace(/\/$/, "");
    const fragment = new URLSearchParams({
      invite: invitation.invitation,
      role: invitation.role,
    });
    return `${publicUrl}/live/join#${fragment.toString()}`;
  }, [invitation]);

  const regenerate = async () => {
    if (!creatorAccess) return;
    try {
      const result = await api.regenerateLiveInvitation(
        sessionId,
        creatorAccess.token,
      );
      setInvitation(result.invitation);
      setCopied(false);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "A new invitation could not be created.",
      );
    }
  };

  const invitedRole = invitation?.role ?? (
    session ? otherRole(session.creator_role) : "worker"
  );

  return (
    <main className="app-shell">
      <LiveBrandBar trailing={<span className="guided-mode-note">Live · text only</span>} />
      <section className="guided-flow-page waiting-room">
        <LiveProgress
          currentStage="participation"
          explanation="The conversation opens automatically when the other person joins."
        />
        <article className="join-status-card waiting-session-card" aria-live="polite">
          <p className="eyebrow">Separate devices</p>
          <h1>Invite the {roleLabel(invitedRole)}</h1>
          <ol className="joining-instructions">
            <li>Ask the {roleLabel(invitedRole).toLowerCase()} to scan the QR code or open the private link.</li>
            <li>They review the data notice and join as {roleLabel(invitedRole)}.</li>
            <li>Keep this page open; both devices continue automatically.</li>
          </ol>
          {joinUrl ? (
            <>
              <div className="qr-frame" aria-label={`${roleLabel(invitedRole)} joining QR code`}>
                <QRCodeSVG value={joinUrl} size={224} level="M" />
              </div>
              <div className="setup-actions compact">
                <button
                  className="button secondary"
                  type="button"
                  onClick={async () => {
                    await navigator.clipboard.writeText(joinUrl);
                    setCopied(true);
                  }}
                >
                  {copied ? "Invitation link copied" : "Copy invitation link"}
                </button>
                <button className="text-action" type="button" onClick={regenerate}>
                  Generate a new link
                </button>
              </div>
            </>
          ) : (
            <button className="button secondary" type="button" onClick={regenerate}>
              Generate joining link
            </button>
          )}
          {invitation ? (
            <p className="invitation-expiry">
              Invitation expires {new Date(invitation.expires_at).toLocaleString()}.
            </p>
          ) : null}
          <div className="connection-status-grid" aria-label="Participant connection status">
            {(["hirer", "worker"] as const).map((role) => {
              const connected = session?.participant_presence?.some(
                (presence) => presence.role === role && presence.status === "connected",
              ) ?? role !== invitedRole;
              return (
                <div key={role}>
                  <span>{roleLabel(role)}</span>
                  <strong>{connected ? "Connected" : "Waiting to join"}</strong>
                </div>
              );
            })}
          </div>
          <div className="waiting-inline-status">
            <span className="waiting-pulse" aria-hidden="true" />
            <strong>Waiting for {roleLabel(invitedRole)}…</strong>
          </div>
          {error ? <p className="analysis-error" role="alert">{error}</p> : null}
        </article>
      </section>
    </main>
  );
}
