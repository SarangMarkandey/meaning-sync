import type { LiveAccessCredential, PartyRole } from "@/lib/api";

const key = (sessionId: string, role: PartyRole) =>
  `meaningsync.live.${sessionId}.${role}`;

export function storeLiveAccess(
  sessionId: string,
  credentials: LiveAccessCredential[],
) {
  if (typeof window === "undefined") return;
  for (const credential of credentials) {
    window.sessionStorage.setItem(
      key(sessionId, credential.role),
      credential.access_token,
    );
  }
}

export function getLiveAccess(sessionId: string, role: PartyRole): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(key(sessionId, role));
}

export function getAnyLiveAccess(
  sessionId: string,
): { role: PartyRole; token: string } | null {
  for (const role of ["hirer", "worker"] as const) {
    const token = getLiveAccess(sessionId, role);
    if (token) return { role, token };
  }
  return null;
}

export function clearLiveAccess(sessionId: string, role: PartyRole) {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(key(sessionId, role));
}
