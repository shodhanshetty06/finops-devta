# GCP FinOps Frontend

Next.js 16 (App Router, TypeScript, Tailwind v4) frontend for the GCP
FinOps Estimation Platform. Talks to the FastAPI backend in `../backend`
through a single typed client (`src/lib/api-client.ts`).

See `../docs/PHASE6_NOTES.md` for how to run it, verify it, and a manual
browser checklist.

## Quick start

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

## Scripts

- `npm run dev` - development server
- `npm run build` / `npm start` - production build + serve
- `npx tsc --noEmit` - type-check
- `npm run lint` - eslint
- `npm test` - Vitest unit/component tests

## Structure

```
src/
  app/                Next.js routes (login, register, projects, wizard, dashboard, intake)
  components/          reusable UI - charts, panels, nav, wizard steps
  components/ui/        hand-built primitives (button, input, card, ...)
  contexts/             AuthProvider
  lib/                   api-client, types, utils, React Query provider
```
