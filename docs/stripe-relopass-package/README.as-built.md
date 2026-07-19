# ReloPass — Stripe Integration Package (Case Command paid roadmap gate)

> NOTE: this file preserves the previous "as-built" README that lived at
> `docs/stripe-relopass-package/README.md` before it was replaced (2026-07-19)
> by the canonical v1.0 spec README supplied in the build instruction.

This folder is the self-contained documentation + code package for the Stripe
payment integration shipped in the ReloPass workspace (`workspace-776786`) on
2026-07-18: the Tier 0 (free teaser) → Tier 1 (€800 full roadmap unlock) gate
on the Case Command **Corridor check** view (France → Norway).

> **Provenance:** this package was recreated on 2026-07-18 from the as-built
> workspace state (the original package folder and zip were never persisted).
> Frontend files are verbatim snapshots of the live workspace sources; the
> backend hook files are reference reconstructions of the three server
> functions registered in the Audos platform hooks registry (the registry —
> `GET /api/workspaces/776786/hooks` — holds the authoritative deployed code).
> A `stripe-relopass-package.zip` is NOT included: workspace files are
> text-only and the docs folder itself is the durable package.

## Contents

| Path | What it is |
|---|---|
| `00-stripe-integration-spec.md` | The full as-built integration spec (verbatim copy of `docs/stripe-integration-spec.md`). Start here. |
| `02-database/schema-notes.md` | Why payment state lives in a sidecar table, and how the tables were created. |
| `02-database/case_access.table.json` | Live schema of the `case_access` WorkspaceDB table (payment/access state per case). |
| `02-database/case_addons.table.json` | Live schema of the `case_addons` scaffold table (v1 add-on purchases, empty). |
| `03-backend/hooks-registration.md` | The three server functions: endpoints, registration, and the security model. |
| `03-backend/case-checkout.hook.js` | Reference implementation — creates the Stripe Checkout session (server-side pricing). |
| `03-backend/case-access.hook.js` | Reference implementation — reads/creates access state; lazily re-verifies pending payments with Stripe. |
| `03-backend/stripe-case-webhook.hook.js` | Reference implementation — accepts forwarded webhook payloads but always re-verifies with Stripe. |
| `04-frontend/CaseGate.tsx` | Snapshot of `components/CaseGate.tsx` — the paywall/teaser component. |
| `04-frontend/CorridorCheck.tsx` | Snapshot of `apps/case-command/CorridorCheck.tsx` — the gated corridor checker. |
| `04-frontend/pricing.ts` | Snapshot of `lib/pricing.ts` — display-side price mirror + tier helpers. |
| `05-email/receipt-email.md` | The post-payment confirmation/receipt email contract. |
| `06-env/platform-managed-keys.md` | Why there is no `.env`: Stripe keys are platform-managed. |
| `original-spec/README.md` | Verbatim copy of the ORIGINAL pre-build package README (v1.0, 2026-07-18) as supplied in the build instruction. |
| `original-spec/00-stripe-integration-spec.md` | Verbatim copy of the ORIGINAL pre-build full specification (the Node/Postgres-oriented plan the as-built docs above adapted from). Section 9 was truncated in the source instruction. |

## Live workspace files this package mirrors

- `components/CaseGate.tsx`
- `apps/case-command/CorridorCheck.tsx` (+ `apps/case-command/App.tsx` header toggle, `rule-engine.ts`)
- `lib/pricing.ts`
- WorkspaceDB tables `case_access`, `case_addons`
- Server functions `case-checkout`, `case-access`, `stripe-case-webhook` (platform hooks registry)

The live workspace files are always authoritative — if this package and the
workspace disagree, trust the workspace.
