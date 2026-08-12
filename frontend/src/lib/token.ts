// Centralized JWT storage. A single module owning the storage key avoids
// the auth context and the axios interceptor drifting on the key name.
// This is a normal browser web app (not an ephemeral preview/artifact), so
// localStorage is the right place to persist a session token across reloads.
const TOKEN_KEY = "finops_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
