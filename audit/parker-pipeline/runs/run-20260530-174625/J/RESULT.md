# Step J RESULT — NLG variety (data-to-text, frame-based, extractive)

_Run: run-20260530-174625 | Branch: audit/parker-step-J-nlg-variety_

## Summary
Broke ReloPass's NLG monoculture (Parker W11 — markdown templates only) by adding three
classical, **LLM-free, deterministic** NLG strategies under a new
`backend/app/services/nlg/` package: **data-to-text** (executive KPI summaries ordered by
salience), **frame-based** (slot-validated incident/case reports for four event types), and
**extractive** (TextRank TL;DR of long policy documents). Two are wired into real product
surfaces behind a new router: a data-to-text exec summary on the HR Mobility Control Center
(env-flag gated for one-var rollback) and an extractive TL;DR panel on the HR Policy Review
Workspace. Every function is deterministic — identical input yields identical bytes — and
none calls an LLM, which is Parker's whole point: classical NLG is cheaper, auditable, and
sufficient for these artefacts. No schema change, no migration.

## Files changed
```
 backend/app/main.py                                |   2 +
 backend/app/routers/nlg.py                         | 170 +++++++++++++++++++++ (new)
 backend/app/services/nlg/__init__.py               |  34 +++++ (new)
 backend/app/services/nlg/data_to_text.py           | 128 ++++++++++++++++ (new)
 backend/app/services/nlg/extractive_summarizer.py  | 121 +++++++++++++++ (new)
 backend/app/services/nlg/frame_based.py            | 141 +++++++++++++++++ (new)
 backend/tests/test_nlg_data_to_text.py             |  96 ++++++++++++ (new)
 backend/tests/test_nlg_extractive.py               |  72 +++++++++ (new)
 backend/tests/test_nlg_frame_based.py              | 114 ++++++++++++ (new)
 backend/tests/test_nlg_router.py                   | 118 ++++++++++++ (new)
 frontend/src/api/nlg.ts                            |  26 ++++ (new)
 frontend/src/features/platform-v2/mobility-control/MobilityControlCenterV2Page.tsx | 22 +++
 frontend/src/features/policy/HrPolicyReviewWorkspace.tsx                            | 23 +++
 13 files changed, 1067 insertions(+)
```
_(Against base `81d98bc8` — the pre-merge pipeline base, same as A–I. The diff is against
HEAD~base, not `main`.)_

## Tests added
- `backend/tests/test_nlg_data_to_text.py` (7 tests) — exec + hr-ops snapshot on a 6-KPI
  fixture; anomaly-leads-first regardless of delta size; salience ordering by |delta|;
  determinism (identical bytes); empty KPI set → safe sentence; output is 3–5 sentences.
- `backend/tests/test_nlg_frame_based.py` (8 tests) — all four frames registered; each
  renders with minimal slots; missing slot → `MissingSlotError`; unknown event →
  `UnknownFrameError`; locale number grouping (`1,500` en / `1.500` de); translate hook
  applied; determinism (identical bytes).
- `backend/tests/test_nlg_extractive.py` (6 tests) — at-most max_sentences; selects the
  central housing/tax theme and drops off-topic filler; source order preserved; short text
  returned whole; empty text → empty; determinism; **LLM-free** (source has no openai/
  anthropic import).
- `backend/tests/test_nlg_router.py` (9 tests) — exec-summary: 401 unauth, 200 HR own
  company, 403 cross-company, 200 admin any company, `NLG_EXEC_SUMMARY_PROVIDER=llm` →
  provider=`llm` + `summary=None`; tldr: 401 unauth, 200 with summary on a 40-sentence doc
  (sentence_count ≤ 5), 404 unknown policy. FastAPI `dependency_overrides` + monkeypatched
  data loaders (no live DB).

## Test result
- pytest (NLG suite, all 4 files): **30 passed** (0.46s).
- Regression check (collect-only over all `backend/tests`): **2043 tests collected, 10
  pre-existing collection errors** — all legacy un-migrated `services.*` import-path files
  (`test_admin`, `test_collaboration*`, `test_dossier`, `test_employee_policy_*`,
  `test_guidance_pack`, `test_official_ingest`, `test_auth_reconcile_timeout`,
  AUDIT-A9.3). **Zero NLG-related errors**; my new files collect cleanly.
  `from backend.app.main import create_app; create_app()` wires both NLG routes with no error
  (`/api/hr/{company_id}/exec-summary`, `/api/policies/{policy_id}/tldr`).
- tsc: **pass** (`cd frontend && npx tsc --noEmit`, exit 0).
- vitest: no frontend NLG unit test added (the two edits are in-place wiring on existing
  pages; see UI changes + Known gaps).

## Migration applied?
- **No migration.** This step is pure presentation logic over existing data. No new public
  table → the RLS hard gate is satisfied vacuously. The TL;DR endpoint reads the existing
  `public.policy_documents.raw_text` column (already RLS-protected by
  `20260329000000_policy_documents.sql`).

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | /api/hr/{company_id}/exec-summary | require_admin_or_hr + company match (admin any) | backend/app/routers/nlg.py |
| GET | /api/policies/{policy_id}/tldr | get_current_user (session token) | backend/app/routers/nlg.py |

`exec-summary` → `{company_id, provider, period, summary}` (summary `null` when
provider=`llm`). `tldr` → `{policy_id, summary, sentence_count, source_chars}`; 404 when the
policy document is missing or has no extracted text.

## New tables / schema changes
- **None.**

## Configuration / env vars added
- `NLG_EXEC_SUMMARY_PROVIDER` — `data_to_text` (default) | `llm`. When `llm`, the
  exec-summary endpoint returns `provider="llm"`, `summary=null` so the frontend keeps its
  existing LLM-rendered summary — making the swap (and rollback) a one-env-var change. Read
  in `backend/app/routers/nlg.py`.

## UI changes summary
- New routes added: **none** (no new top-level route, no new page).
- New components added: **none** — only in-place edits to two existing pages plus a new
  API wrapper module (`frontend/src/api/nlg.ts`, non-visual).
- Existing antigravity components reused: `Card` (TL;DR panel on the policy workspace). The
  exec-summary block reuses the page's existing Tailwind card styling inline.
- Surfaces wired in-place:
  - `MobilityControlCenterV2Page.tsx` — data-to-text exec summary block below the KPI strip,
    sourced from `useHrCompanyContext().companyId` → `fetchExecSummary`. Hidden when the
    provider is `llm` or the call fails (graceful).
  - `HrPolicyReviewWorkspace.tsx` — "TL;DR" `Card` after the policy header, sourced from
    `normalized.version.source_policy_document_id` → `fetchPolicyTldr`. Hidden when there is
    no source document or the call fails.
- UI-PROPOSAL.md status: **not required** — the task's UI-impact line is "In-place updates
  only … Does NOT require UI-PROPOSAL.md."

## Deviations from the original audit prompt
1. **networkx replaced by a ~20-line numpy PageRank power-iteration.** networkx is not an
   installed dependency; the prompt said "check before adding" and TextRank over one
   TF-IDF similarity graph needs only a single PageRank pass. Adding a heavy graph library
   for one matrix op violates Simplicity First, so I used numpy (already a dep). **No new
   dependency added** to `backend/requirements.txt`.
2. **babel not used** — also not installed; frame locale/date/number formatting uses the
   stdlib (`datetime.isoformat`, manual thousands grouping). The prompt explicitly permits
   the stdlib fallback.
3. **Frame-based translation hook is injectable, not a hard import of Step I.** `render(...,
   translate=callable)` defaults to identity. Step I's `translation_service` lives on an
   unmerged branch and is absent from this tree, so a hard import would break the build;
   `translation_key_for(event_type)` + the hook keep this forward-compatible.
4. **Frame-based feed wiring is the renderer utility, not a live alerts emitter.** The four
   frames render correctly and are unit-tested, but the Mobility Control Center "Risk feed"
   is derived client-side from the case list and there is no backend event source emitting
   the four typed events. Emitting frames into a real feed is a follow-up (see Known gaps) —
   the deterministic renderer is the shippable primitive.
5. **Frontend paths differ from the sketch.** `frontend/src/features/hr/command-center/`
   does not exist; the actual HR command center is
   `frontend/src/features/platform-v2/mobility-control/MobilityControlCenterV2Page.tsx`, and
   the policy viewer wired is `HrPolicyReviewWorkspace.tsx`.

## What downstream steps will need from this step
- **NLG primitives** are importable from `backend.app.services.nlg`:
  `summarise_kpis(KPISet, audience=...)`, `render(Frame, locale=..., translate=...)` with
  `registered_event_types()` = `('passport_expiry_at_risk', 'assignment_milestone_missed',
  'policy_change_required', 'supplier_unresponsive')`, and `summarise(text,
  max_sentences=...)`. All deterministic and LLM-free.
- **Translation (Step I)**, once merged, can be wired into frame reports by passing
  `translate=lambda s: translation_service.translate(s, src, tgt).text` to `render()` when
  the recipient's `preferred_language` ≠ source — no change needed here.
- **Adding more of Parker's 14 NLG approaches** slots into the same `nlg/` package
  (template/rule/grammar/etc. were explicitly out of scope).

## Known gaps / follow-ups
- **Frame-based feed not wired to a live event source** — the renderer + registry ship and
  are tested, but emitting frames into the Risk feed needs a backend producer for the four
  event types (passport expiry, milestone missed, policy change, supplier silence). Map to a
  Notion AI Work Queue follow-up. (Deviation #4.)
- **UI not run headless** — both frontend edits type-check (tsc exit 0) but were not
  exercised in a browser in this environment. The wiring degrades gracefully (panels hide on
  error / when data is absent), but a visual pass on the exec-summary block and the TL;DR
  Card is recommended at review.
- **KPI loader is minimal** — `load_company_kpis` currently emits a single
  active-assignments KPI from `case_assignments`; richer KPIs (compliance %, overage,
  anomalies) can be added without touching the summariser, which already handles multi-KPI
  salience ordering.
- **Full local suite is known-red** (pre-existing legacy `services.*` collection errors,
  AUDIT-A9.3) — out of scope; this branch adds **zero** new failures or errors.
