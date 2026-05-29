# apps/hr-dashboard

Cohort-1 HR Dashboard surface for ReloPass — separate from `frontend/` (the
existing relopass.com app) per the C1-11 brief. Vite + React 18 + TypeScript
+ Tailwind 3.4 + shadcn/ui contract.

## What's in this directory

This is the **C1-11a scaffold** only:

- Vite + React 18 + TS strict.
- Tailwind 3.4 configured to consume the C1-11D design tokens at
  `design/system/tokens.css`.
- shadcn/ui config (`components.json`) — primitives can be added with
  `npx shadcn@latest add <name>`. The theme block in
  `design/system/shadcn-theme.json` is mirrored into
  `tailwind.config.js`.
- React Router v6 with five routes (`/`, `/cases`, `/cases/:id`,
  `/resolution`, `/policy`) plus a public `/login`.
- Auth guard reusing the existing `relopass_token` localStorage key from
  `frontend/src/api/client.ts` — **do not invent a second auth layer**.

The empty pages are placeholders. The real UIs land in C1-11b (cases list),
C1-11c (case detail), C1-11d (PDF viewer), C1-11e (bbox overlay), C1-12
(resolution), C1-15 (policy editor).

## Quick start

```bash
cd apps/hr-dashboard
npm install
npm run dev        # → http://localhost:3100  (frontend/ stays on 3000)
```

Other scripts:

```bash
npm run build       # tsc + vite build → dist/
npm run typecheck   # tsc --noEmit
npm run lint        # eslint src --ext .ts,.tsx
```

## Environment

| Var | Purpose | Default |
| --- | --- | --- |
| `VITE_API_URL` | FastAPI backend base URL | `http://localhost:8000` in dev, empty in build |
| `VITE_RELOPASS_LOGIN_URL` | Override for the main login screen | derived from `VITE_API_URL` |

Local dev proxies `/api/*` to `http://localhost:8000` so the backend doesn't
need CORS. Same convention as `frontend/`.

## Coexistence with the main frontend

The Notion brief is explicit: **do not modify `frontend/`**. This app shares
the backend, the JWT, and the design tokens — nothing else. When porting a
component or pattern over, copy it in deliberately rather than reaching across
the boundary at runtime.

## Where things live

```
apps/hr-dashboard/
├── src/
│   ├── App.tsx              Route tree
│   ├── main.tsx             React + BrowserRouter mount
│   ├── index.css            Tailwind + design tokens import
│   ├── components/
│   │   ├── AppShell.tsx     Persistent header + outlet
│   │   └── EmptyState.tsx   Placeholder used by every scaffold page
│   ├── lib/
│   │   ├── api.ts           Axios client (Authorization: Bearer …)
│   │   ├── auth.ts          relopass_token localStorage helpers
│   │   └── utils.ts         cn() — shadcn standard helper
│   ├── pages/               One file per route
│   └── routes/
│       └── RequireAuth.tsx  Login-redirect wrapper
├── tailwind.config.js       Mirrors design/system/shadcn-theme.json hints
├── tsconfig.json            strict + noUnusedLocals + noUnusedParameters
├── vite.config.ts           Port 3100, /api proxy → :8000
└── components.json          shadcn/ui CLI config
```

## CI

A dedicated job in `.github/workflows/ci.yml` (`hr-dashboard-build`) runs
`npm ci` + `npm run build` + `npm run typecheck` + `npm run lint` on every
PR and on pushes to `main`, mirroring the `frontend-build` job's shape.
