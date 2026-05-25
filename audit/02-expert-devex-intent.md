# Plan-Mode Expert Review — Developer Experience Lens (Intent)

**Reviewer lens:** "Is the developer-facing layer (provider portal, integrations, internal APIs) approachable, well-documented, and consistent enough that a new integrator or new engineer can succeed quickly?"
**Docs reviewed:** `CLAUDE.md`, `IMPLEMENTATION_EXECUTION_GUIDE.md`, `README.md`, `README_DEPLOY_RENDER.md`, integration routers (`integrations_personio_*`, `integrations_bamboohr.py`), provider portal surfaces.

**Score: 5.5 / 10** — DX intent is partial: there's solid contributor-facing documentation (CLAUDE.md), but external-facing DX (provider portal, integration partners, API consumers) is thin.

What would make it a 10: a single "Integrate with ReloPass" doc with auth flow + webhook schema + status-page link + sandbox creds, and an internal "Onboard a new engineer in 1 hour" path that actually works.

---

## Strengths

1. **CLAUDE.md is excellent** as contributor onboarding for the AI coding loop. Dual-layer pattern documented, env vars listed, build hygiene explicit.
2. **Personio + BambooHR integration patterns exist** as routers (suggests a real plan for HRIS integration).
3. **AI Work Queue items document Form Template Registry, Dossier Builder UI, Provider Task Portal UI** — these are developer-experience-adjacent surfaces with structured specs.

## Findings

### DX-1 [P0] — No external-facing API documentation
There is no public-facing API reference. The Personio + BambooHR routers exist but their webhook contracts (`integrations_personio_webhook.py`) are documented only in code comments. For a B2B SaaS that depends on integration story (per CEO-lens: "Phase 2 export readiness to Topia"), this is a critical gap.
**Recommend:** publish an OpenAPI spec from the FastAPI app (FastAPI generates this for free at `/openapi.json` + `/docs`), then a curated "Integrate with ReloPass" page.

### DX-2 [P0] — Provider portal DX is unknown
`provider_portal.py` exists. `AIQ-4-D` ("Build provider task portal UI — scoped to provider JWT") is in the AI Work Queue. But no doc explains: how does a new provider get onboarded? How does the JWT issuance work? How does the provider self-service their account? This matters because vendor adoption is the bottleneck on the coordination value-prop — and bad vendor DX kills it.
**Recommend:** write a one-page "Welcome, vendor partner" doc covering onboarding, JWT lifecycle, and the 3 actions a vendor can take.

### DX-3 [P1] — `CLAUDE.md` local-dev command is stale
`cd backend && uvicorn main:app --reload --port 8000` fails with `ImportError: attempted relative import with no known parent package` because the package path requires running from repo root. This is a DX paper-cut — every new engineer hits it.
**Recommend:** fix CLAUDE.md to read `uvicorn backend.main:app --reload --port 8000` from repo root.

### DX-4 [P1] — `IMPLEMENTATION_EXECUTION_GUIDE.md` is unstructured (9.7 KB single file)
The implementation guide is long-form prose without a TOC, anchors, or "if you're new here, start at X." For a doc designed to guide multi-day implementation tasks, this is hard to navigate.
**Recommend:** add TOC, sectional anchors, and a "Quick paths: bug fix / new feature / migration" tree at the top.

### DX-5 [P1] — Frontend dev-proxy + supabase-client conventions are documented but not enforced
CLAUDE.md says: HTTP calls go through `frontend/src/api/`; Supabase client only for auth/realtime/docs. Full-stack audit found `AdminAbTestsPage.tsx` querying Supabase directly + `AdminProspects.tsx` using raw fetch. Documentation without enforcement is half-DX.
**Recommend:** lint rule (ESLint custom rule or grep-based CI check) that fails the build on `supabase.from(` outside `api/` and `auth/`, and on `fetch(` / `axios(` outside `api/`.

### DX-6 [P1] — Test commands not consistent
CLAUDE.md lists `cd backend && pytest` and `cd frontend && npx vitest`. There's no `make test`, no `npm run test` at repo root, no GitHub Actions matrix reference. A new contributor doesn't know if they should run both, neither, or which one for their change.
**Recommend:** root-level `Makefile` or `npm` script that runs both, plus a CONTRIBUTING.md (today: missing).

### DX-7 [P2] — Env-var documentation is split across CLAUDE.md, README, and .env.example
Three sources of truth. .env.example exists but is not the canonical reference. CLAUDE.md lists ~6 vars, but the actual app likely needs ~20.
**Recommend:** make `.env.example` exhaustive (every env var the app reads), with a comment per var, and point CLAUDE.md to it.

### DX-8 [P2] — No `gh` PR template, no issue template
For a repo with multiple AI agents committing, structured PR descriptions accelerate review.
**Recommend:** `.github/pull_request_template.md` with: summary / test plan / linked Notion task / screenshots if UI.

### DX-9 [P2] — Service-tree DX is confusing per ENG-3
`backend/services/` vs `backend/app/services/` — new engineer doesn't know where to put a new service. Existing imports leak across.
**Recommend:** decide and document.

---

## What this lens is NOT saying

- Not telling you to build a developer portal. That's premature for the segment.
- Not telling you to ship a CLI. Most B2B SaaS doesn't need one.
- Not telling you to open-source. Out of scope.

## Recommended next DX actions

1. Publish OpenAPI spec + `/docs` route enabled in prod (FastAPI does this for free, gate behind admin auth).
2. One-page vendor onboarding doc.
3. Fix CLAUDE.md uvicorn command — 2-minute fix.
4. Add ESLint rule for Supabase/fetch usage.
5. Add `make test` or root npm script.
6. Decide+delete one services tree.
