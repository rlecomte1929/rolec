# July 1 Merge Plan — 20 Open PRs

> Generated: 2026-06-30. All 20 PRs were held by the Render/GitHub Actions budget
> freeze. None are stale — every branch has commits not on main. No close candidates.

---

## 1. Merge Order in Conflict-Free Waves

Merges within a wave can be applied simultaneously (or in any order within the wave).
Waves must be completed in sequence. "Parallel" = no shared changed files.

### Wave 1 — Fully Isolated (11 PRs, any order, all parallel)

| PR | Branch | Why isolated |
|----|--------|--------------|
| #1163 | feat/aiq-945-corrections-digest | apps/hr-dashboard + admin_corrections.py only; no overlap |
| #1200 | eval-deepen | backend/eval/ metrics files + test_admin_rag_eval; no overlap |
| #1207 | frontend-hygiene | eslint.config.js + 3 single-owner components; no overlap |
| #1209 | feat/immigration-blue-card-regime | immigration_regime.py + fixtures/tests; no overlap |
| #1210 | frontend-ui-p0 | package.json, index.css, main.tsx, tailwind.config.js; no overlap |
| #1215 | fix/test-p3-xfail-db-layer | single test file; no overlap |
| #1217 | feat/h3-corpus-coverage | audit/ + scripts/ + docs/eval/ only; no overlap |
| #1218 | feat/h1-pii-mask-llm-egress | analytics_query.py, support.py, prospect_enrichment; no overlap |
| #1219 | feat/h4-test-evidence | test files + campaigns.json (root) + results/; no overlap |
| #1220 | feat/aiq-515-extraction-harness | backend/eval/extraction_corpus_adapter.py + scripts; no overlap |
| #1221 | docs/admin-profile-audit | audit/admin/ docs only; no overlap |

**Notes for Wave 1:**
- #1209, #1215, #1220 carry an explicit `⛔ DO NOT MERGE before 1 July` notice in
  their PR body. All are safe to merge on July 1 when credit is restored.
- #1221 must land before Wave 5 (#1227 references its audit plan).

### Wave 2 — Antigravity Barrel (sequential within wave)

| Order | PR | Branch | Rationale |
|-------|----|--------|-----------|
| 2-A | #1213 | frontend-ui-comp2 | Adds Textarea/Switch/Skeleton/Tabs/Pagination to `antigravity/index.ts` |
| 2-B | #1214 | frontend-ui-shell | Adds PageHeader to same `antigravity/index.ts` + modifies AdminLayout.tsx |

Both PRs append new exports to `frontend/src/components/antigravity/index.ts`. GitHub
will merge them cleanly if applied sequentially but will produce a conflict if both are
open simultaneously in a merge queue. Apply 2-A first, then 2-B.

Wave 2 is independent of Waves 3-5 and can be interleaved at any point after Wave 1.

### Wave 3 — Backend Routing + Assistant MVP Foundation (2 PRs, parallel)

#1216 and #1222 touch completely different files and can merge simultaneously.

| PR | Branch | Files | Blocks |
|----|--------|-------|--------|
| #1216 | feat/h2-provider-portal | backend/main.py, backend/app/main.py | #1223 (Wave 4) |
| #1222 | frontend-assistant-mvp | ImmigrationAnswerPanel.tsx, ImmigrationAssistantPage.tsx | #1223 (Wave 4) |

Both must land before Wave 4 because #1223 (Slice 2) touches all four of those files.

### Wave 4 — Slice 2: Employee Snapshot (1 PR, after Wave 3 both done)

| PR | Branch | Shared files with previous waves |
|----|--------|----------------------------------|
| #1223 | assistant-snapshot | backend/main.py + backend/app/main.py (from #1216), ImmigrationAssistantPage.tsx (from #1222) |

#1223 is the bridge: it adds `employee_immigration_snapshot` router to both backend
entry points (needs the clean state from #1216) and wires `MoveAtAGlance` into
ImmigrationAssistantPage (needs #1222's prop plumbing).

### Wave 5 — Slice 3: Context Injection (1 PR, after Wave 4)

| PR | Branch | Shared files |
|----|--------|-------------|
| #1224 | assistant-context-injection | ImmigrationAnswerPanel.tsx (from #1222), ImmigrationAssistantPage.tsx (from #1223) |

### Wave 6 — Slice 4: Suggested Questions (1 PR, after Wave 5)

| PR | Branch | Shared files |
|----|--------|-------------|
| #1225 | assistant-suggested-questions | ImmigrationAnswerPanel.tsx (from #1224) |

### Wave 7 — Slice 5: Policy Bridge (1 PR, after Wave 6)

| PR | Branch | Shared files |
|----|--------|-------------|
| #1226 | assistant-policy-bridge | ImmigrationAnswerPanel.tsx (from #1225), ImmigrationAssistantPage.tsx (from #1224) |

### Wave 8 — Admin Hardening (1 PR, after Waves 1+3+4 all done)

| PR | Branch | Why last |
|----|--------|---------|
| #1227 | feat/admin-hardening | Touches backend/main.py (needs Wave 3 #1216 + Wave 4 #1223 clear), App.tsx, PlatformShellSidebar, routes.ts (unique to this PR), PLUS 2 new migrations. Body explicitly references #1221 ("from the admin-profile audit, PR #1221"). Must be final. |

**Minimum prerequisites for #1227:**
- #1221 merged (docs it references)
- #1216 merged (clears backend/main.py + backend/app/main.py queue)
- #1223 merged (same — avoids 3-way main.py conflict)

---

## 2. Close / Supersede Candidates

**None.** Every branch has at least 1 commit not reachable from `origin/main`
(`git cherry` was non-empty for all 20). No PR is superseded or abandoned.

---

## 3. Hot-File Conflict Table

Files touched by 2+ open PRs — must be resolved by the wave ordering above.

| File | PRs | Required order |
|------|-----|---------------|
| `backend/main.py` | #1216, #1223, #1227 | #1216 → #1223 → #1227 |
| `backend/app/main.py` | #1216, #1223, #1227 | #1216 → #1223 → #1227 |
| `frontend/src/features/immigration/ImmigrationAnswerPanel.tsx` | #1222, #1224, #1225, #1226 | #1222 → #1224 → #1225 → #1226 |
| `frontend/src/pages/employee/ImmigrationAssistantPage.tsx` | #1222, #1223, #1224, #1226 | #1222 → #1223 → #1224 → #1226 |
| `frontend/src/components/antigravity/index.ts` | #1213, #1214 | #1213 → #1214 |

All other files are single-owner — no risk outside the above table.

---

## 4. Migration Timestamps

Only **#1227** (feat/admin-hardening) introduces new migrations. No other open PR
touches `supabase/migrations/`.

| File | Timestamp | Status |
|------|-----------|--------|
| 20260817000000_platform_settings.sql | 2026-08-17 | Safe — above main's highest (20260816) |
| 20260818000000_feedback_status.sql | 2026-08-18 | Safe — sequential above previous |

**Highest migration on main:** `20260816000000_supplier_ranking_weights.sql`

Both new timestamps are strictly above the main watermark with no collision between
them. No timestamp collision risk.

**Pre-existing note:** two files at `20260810000000_*` exist on main
(`requirement_fact_candidates.sql` and `requirement_verification_status.sql`). This
is a pre-existing collision already on main — not introduced by any of these PRs.

---

## 5. Execution Checklist (July 1)

```
[ ] WAVE 1  — merge all 11 in parallel (or any order):
    #1163, #1200, #1207, #1209, #1210, #1215, #1217, #1218, #1219, #1220, #1221

[ ] WAVE 2  — sequential: #1213 first, then #1214

[ ] WAVE 3  — parallel: #1216 and #1222 simultaneously

[ ] WAVE 4  — #1223 (after Wave 3 both done)

[ ] WAVE 5  — #1224 (after Wave 4)

[ ] WAVE 6  — #1225 (after Wave 5)

[ ] WAVE 7  — #1226 (after Wave 6)

[ ] WAVE 8  — #1227 (after Wave 1 #1221 + Wave 3 #1216 + Wave 4 #1223 all done)
```

Total: 20 PRs across 8 waves. The critical path is the assistant slice chain
(Waves 3-7) plus the admin hardening gate (Wave 8). Pure infrastructure /
eval / docs PRs (Wave 1) unblock immediately and have no critical dependencies.

---

## 6. Safe Areas for New Work (Low PR Overlap)

Areas with no or minimal open-PR surface area — safe to start new feature branches
without expecting conflicts on July 1:

| Area | Overlap risk | Note |
|------|-------------|------|
| `backend/app/services/` (most modules) | Low | Only specific files touched (rag_engine, platform_settings, prospect_enrichment, source_reliability, immigration modules) |
| `frontend/src/features/` (except `immigration/`) | Very low | No open PRs in hr/, relocation/, case/ |
| `frontend/src/pages/hr/` | None | Zero open PRs touching HR pages |
| `backend/app/routers/` (except admin_* + immigration_retrieve.py) | Low | New routers can go to unique files |
| `supabase/migrations/` (timestamp >= 20260819) | None | Only #1227 adds migrations; next safe slot is 20260819000000 |
| `backend/tests/` (new files) | None | All test file conflicts are within existing named files |
| `docs/security/` | None | Only #1218 touches PRIV-004; done after Wave 1 |
| `apps/hr-dashboard/` | None | Only #1163 touches it; done in Wave 1 |
