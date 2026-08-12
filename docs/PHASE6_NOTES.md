# Phase 6 - Frontend Notes

## Running it locally

```bash
# Terminal 1 - backend
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Terminal 2 - frontend
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000`. Register an account, create a project, and
either run the questionnaire wizard or upload/describe requirements via
`/projects/{id}/intake`.

## Verifying it

```bash
cd frontend
npx tsc --noEmit   # type-check
npm run lint        # eslint
npm test            # 24 Vitest unit/component tests
npm run build        # production build
```

All four are clean as of this phase.

## What wasn't verified here

The sandbox this was built in has npm registry access but no way to drive
an actual browser, so the full interactive flow (fill the wizard, watch
live validation update, submit, see the dashboard render, click export and
get a real file) was verified piecemeal instead: the backend side of every
one of these calls has its own passing test (144 backend tests), and the
frontend's production build serves every route with a `200` and the
expected shell content. What's genuinely unverified is the *browser*
experience - React hydration, the Mermaid diagram actually rendering an SVG
in a live DOM, the theme toggle, and the file-download flow.

**Manual checklist** (run once against a live `npm run dev` + backend):

- [ ] Register, log out, log back in - JWT persists across a page reload
- [ ] Create a project, run the wizard through all 8 steps, confirm live
      validation updates within ~1s of changing a field
- [ ] Submit with a deliberately unsupported value (e.g. vcpu 3 on e2) and
      confirm the warning/blocker shows with the right severity color
- [ ] On the estimate dashboard: pie chart renders, bar chart renders,
      architecture Mermaid diagram renders as an actual SVG (not blank)
- [ ] Toggle dark mode - persists across reload, charts remain readable
- [ ] Click "Export Excel" and "Export PDF" - both download a real file
      (not a JSON error) and the numbers match the dashboard
- [ ] Upload a filled Excel questionnaire via `/projects/{id}/intake` -
      redirects to the new estimate
- [ ] Extract from free text (the spec's own example: "500 users, HA
      required, 99.99% uptime, 100GB database") - redirects to a priced
      estimate with visible assumptions

**Recommended next step:** automate this checklist with Playwright against
a running `next start` + `uvicorn` pair, rather than relying on manual
re-verification before each release. Not done in this phase to keep scope
bounded - tracked as a natural Phase 7 addition.

## Design decisions worth knowing

- **No shadcn/ui CLI.** The UI primitives in `src/components/ui/` are
  hand-written (Tailwind + `class-variance-authority`), styled to match
  shadcn/ui's visual language, rather than pulled in via the shadcn CLI
  (which vendors Radix-based component source into the repo). Functionally
  equivalent for this app's needs; swapping in real shadcn/ui components
  later is a drop-in replacement per component since the prop shapes
  (`variant`, `size`, etc.) follow the same convention.
- **`localStorage` for the JWT.** This is a normal browser web app, not an
  embedded preview/artifact - persisting the session token in
  `localStorage` (via `src/lib/token.ts`) is the standard, appropriate
  pattern here.
- **Live validation calls `/api/v1/validate`, not `/api/v1/estimate`.** The
  wizard debounces a validation-only call (no pricing) on every field
  change so feedback is fast; pricing only happens once, on final submit.
