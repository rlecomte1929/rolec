# Step J PLAN — NLG variety (data-to-text, frame-based, extractive)

_Run: run-20260530-174625 | Branch: audit/parker-step-J-nlg-variety | Base: 81d98bc8_

## Task understanding
ReloPass produces written output via markdown templates only (`guidance_markdown.py`).
Parker's framework (W11) flags this NLG monoculture. This step adds three classical,
**LLM-free, deterministic** NLG strategies under a new `backend/app/services/nlg/`
package: (1) **data-to-text** — turns a structured KPI set into a 3–5 sentence executive
summary ordered by salience; (2) **frame-based** — fills pre-vetted slot templates for
four incident/case event types; (3) **extractive** — a TextRank-style summariser for long
policy documents. Each is exposed where it adds the most buyer value and is gated/added
in-place on existing surfaces (no new pages or routes-trees). The whole point per Parker:
classical NLG is cheaper, auditable, and deterministic where an LLM is overkill.

## Upstream alignment
PREREQUISITES.md: **no upstream dependencies**. Step I (translation) shipped, so the
frame-based renderer exposes an optional translation hook — but I will NOT hard-import
`translation_service` (it lives on the unmerged I branch and is absent from this tree).
The hook is an injectable callable defaulting to identity, so this branch stays
self-contained and the I layer can be wired in once both merge.

## File-by-file change list
**Backend — new package `backend/app/services/nlg/`:**
- `__init__.py` — exports `data_to_text`, `frame_based`, `extractive_summarizer` modules
  plus the three public callables `summarise_kpis`, `render` (+ `Frame`), `summarise`.
- `data_to_text.py` — `summarise_kpis(kpis, *, audience) -> str`. Deterministic templates;
  sentence ordering by salience (anomalies first, then largest |delta|). `KPI`/`KPISet`
  typed structures. No LLM, no randomness.
- `frame_based.py` — `Frame(event_type, slots)` dataclass; a registry of four frames
  (`passport_expiry_at_risk`, `assignment_milestone_missed`, `policy_change_required`,
  `supplier_unresponsive`); `render(frame, *, locale='en', translate=None) -> str`;
  typed `MissingSlotError` / `UnknownFrameError`. Date/number formatting via stdlib.
- `extractive_summarizer.py` — `summarise(text, *, max_sentences=5) -> str`. TextRank:
  sentence split → TF-IDF vectors → cosine similarity matrix → PageRank power-iteration
  (numpy). Pure Python/numpy, no LLM, deterministic. Preserves source order on output.

**Backend — router + wiring:**
- `backend/app/routers/nlg.py` — new router: `GET /api/hr/{company_id}/exec-summary`
  (HR/admin, company-scoped) + `GET /api/policies/{policy_id}/tldr` (session auth).
  Reads env flag `NLG_EXEC_SUMMARY_PROVIDER`.
- `backend/app/main.py` — register `nlg.router`.
- `backend/requirements.txt` — no new dep (see deviation #1: networkx replaced by numpy).

**Frontend (in-place only):**
- `frontend/src/api/nlg.ts` — `fetchExecSummary(companyId)` + `fetchPolicyTldr(policyId)`
  wrappers (apiGet).
- Wire the exec-summary text + policy TL;DR into the closest existing surfaces, reusing
  antigravity primitives (Card/Badge). No new route, no new page.

**Docs/tests:** see below.

## New tables and migration plan
**None.** This step is pure presentation logic over existing data; no schema change, no
migration. (Honors the RLS hard gate vacuously — no new public table.)

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | /api/hr/{company_id}/exec-summary | require_admin_or_hr + company match | backend/app/routers/nlg.py |
| GET | /api/policies/{policy_id}/tldr | get_current_user (session) | backend/app/routers/nlg.py |

## Tests
- `backend/tests/test_nlg_data_to_text.py` — 6-KPI fixture snapshot per audience
  (`exec`, `hr-ops`); anomaly-leads ordering; salience ordering by |delta|; determinism
  (two calls → identical bytes); empty KPI set → safe sentence.
- `backend/tests/test_nlg_frame_based.py` — each of 4 frames renders; missing slot →
  `MissingSlotError`; unknown event → `UnknownFrameError`; translate hook applied;
  determinism.
- `backend/tests/test_nlg_extractive.py` — known small corpus → expected top sentences;
  `max_sentences` respected; source-order preserved; determinism (identical bytes twice);
  short text (≤ max) returned whole.
- `backend/tests/test_nlg_router.py` — exec-summary: 401 unauth, 200 HR own company,
  403 cross-company; tldr: 401 unauth, 200 with summary, 404 unknown policy; env-flag
  `NLG_EXEC_SUMMARY_PROVIDER=llm` path returns the passthrough provider marker.
- LLM-free assertion: tests patch/spy that no `openai`/`anthropic` client is constructed.

## Risks and unknowns
- **No live DB in CI** — router tests use FastAPI `dependency_overrides` + monkeypatched
  data loaders (same pattern as the I-step router tests), not a real Postgres.
- **Frontend surfaces are large/unfamiliar** and the UI can't be run headless here; I will
  keep edits minimal/in-place and state explicitly in RESULT what was and wasn't run.
- **TextRank determinism** — fixed iteration count + sorted tie-breaking by source index
  guarantees identical bytes across runs.

## Deviations from the original audit prompt
1. **networkx replaced by a ~20-line numpy power-iteration.** networkx is not installed in
   the env; the prompt said "check before adding" and TextRank over one similarity graph
   needs only PageRank, which is trivial in numpy (already a dep). Adding a heavy graph lib
   for one matrix op violates Simplicity First. No new dependency added.
2. **babel not used** — also not installed; frame locale/date/number formatting uses stdlib
   `datetime`/`format` (the prompt permits the stdlib fallback explicitly).
3. **Translation hook is injectable, not a hard import.** Step I's `translation_service`
   is on an unmerged branch and absent from this tree; `render(..., translate=callable)`
   defaults to identity so this branch is self-contained and forward-compatible.
4. **Frontend wiring is in-place on the nearest existing surface**, not the literal
   `frontend/src/features/hr/command-center/` path in the sketch (that path does not exist).
