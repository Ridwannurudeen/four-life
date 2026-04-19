// Tiny auth helper for the FOUR-LIFE dashboard.
//
// API_SECRET is set on the live VPS, which means any endpoint that gates
// operational internals (`/api/status` → wallet + learnings,
// `/api/tokens/{addr}` → launch post-mortem, `/api/memory` outright, plus
// every /api/agent/* write) now requires a Bearer token. The dashboard is
// the only first-party UI that needs to see the authenticated view — the
// radar / launch / evidence pages are explicitly public.
//
// We keep this client-only: the secret lives in localStorage in the
// operator's browser, nowhere in the repo. Unauthenticated visitors see
// the public shape; the operator unlocks by pasting the secret once.

const LS_KEY = "four-life.api.secret";

export function getApiSecret(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LS_KEY);
  } catch {
    return null;
  }
}

export function setApiSecret(value: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (value) {
      window.localStorage.setItem(LS_KEY, value);
    } else {
      window.localStorage.removeItem(LS_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const secret = getApiSecret();
  const headers: Record<string, string> = { ...extra };
  if (secret) headers["Authorization"] = `Bearer ${secret}`;
  return headers;
}

// Drop-in replacement for fetch() that injects the Bearer if we have one.
export function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = authHeaders((init.headers as Record<string, string>) || {});
  return fetch(input, { ...init, headers });
}
