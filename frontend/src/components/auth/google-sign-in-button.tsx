"use client";

import { Tooltip } from "@/components/ui/tooltip";

function GoogleLogo() {
  return (
    <svg viewBox="0 0 48 48" className="h-4 w-4" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 16.3 4 9.6 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.5 0 10.4-1.9 14.3-5.1l-6.6-5.4C29.6 35.4 27 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.6 5.1C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.3-4.1 5.7l6.6 5.4C41.9 35.6 44 30.3 44 24c0-1.2-.1-2.4-.4-3.5z" />
    </svg>
  );
}

/** Google Sign-In isn't wired to a backend yet - the auth API only
 * supports email/password (see backend/app/api/routers/auth.py). Rendered
 * as a real, clearly-disabled affordance rather than a button that
 * silently does nothing or fakes a working login. */
export function GoogleSignInButton() {
  return (
    <Tooltip content="Google SSO isn't connected in this environment yet" side="bottom">
      <button
        type="button"
        aria-disabled="true"
        onClick={(e) => e.preventDefault()}
        className="flex w-full cursor-not-allowed items-center justify-center gap-2.5 rounded-md border border-border-strong bg-surface px-4 py-2 text-sm font-medium text-muted-foreground opacity-70"
      >
        <GoogleLogo />
        Continue with Google
        <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Soon
        </span>
      </button>
    </Tooltip>
  );
}
