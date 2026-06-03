# FOLLOW-UP PROMPT — G-frontend: Admin panel for AI unit economics

_This is a deferred follow-up to step G. Run it manually when you're ready to
ship the admin panel. It is **not** part of the auto-chain. Paste this whole
file into Claude Code yourself._

## Pre-flight checklist (you, Romain, do this before pasting)

- [ ] Step G's PR is merged. The `mv_ai_unit_economics` view exists in production.
- [ ] The endpoint `GET /api/admin/ai-unit-economics` is returning sensible
      numbers for at least one customer.
- [ ] You've decided where this panel sits in the admin nav (suggested:
      under the existing AI / Observability area).

## Task body

**UI impact:** ONE new admin page at `/admin/ai-economics`. Reuses
antigravity primitives, Recharts, and the existing admin layout. Treat this as
"significant" per the UI-reuse doctrine — write `UI-PROPOSAL.md` first, stop
for Romain's approval, then proceed.

### Stage 1 — UI-PROPOSAL.md (write this first, then STOP)

Before any frontend file edit, write
`audit/parker-pipeline/runs/<RUN_ID>/G-frontend/UI-PROPOSAL.md` containing:

- **Purpose**: "Surface AI spend and carbon per customer per feature so we can
  defend unit economics in commercial conversations and ESG reporting."
- **Info architecture**: route `/admin/ai-economics`, admin-only, sibling to
  the existing AI/observability admin pages (identify the closest existing one).
- **Reused components**: list specific antigravity primitives + the existing
  admin layout shell.
- **New components**: only what cannot be done with existing primitives.
- **Closest existing analogue**: find the current admin page that most resembles
  this in info architecture (probably the supplier admin or the prompt registry
  page from step D). Cite its file path.
- **Visual mock**: ASCII sketch of the page (header + filter row + cost-per-feature
  bar chart + table of recent calls + summary card with totals).
- **Open questions**: anything Romain should weigh in on (date-range default,
  default customer filter, whether the carbon number is shown in grams or kg).

Then write `BLOCKED.md` with "Waiting on UI-PROPOSAL approval" and STOP.

### Stage 2 — After approval, build it

Once Romain greenlights the proposal:

1. Create `frontend/src/features/admin/ai-economics/AIUnitEconomicsPage.tsx`.
2. Lazy-load the route in `frontend/src/App.tsx` per the existing pattern.
3. Wire it to `GET /api/admin/ai-unit-economics` via the existing axios wrapper
   pattern in `frontend/src/api/`.
4. Add a chart (Recharts BarChart) of cost-per-feature for the selected period.
5. Add a card row at the top with totals: $ spent, total tokens, CO₂e (with the
   "≈ estimated" disclaimer per step G).
6. Add the route to the admin nav (find where existing admin links are wired up).
7. Tests:
   - `frontend/src/features/admin/ai-economics/__tests__/AIUnitEconomicsPage.test.tsx`
     — renders without crashing on a mocked API response.
   - Snapshot test for the totals card.

### Closeout

Same as the standard pipeline closeout:
- Run `cd frontend && npx tsc --noEmit` — must pass.
- Run `cd backend && pytest -q` — should be unchanged (no backend edits).
- Branch: `audit/parker-step-G-frontend`.
- PR: `audit(parker-G-frontend): admin AI unit economics panel`.
- Write RESULT.md.
