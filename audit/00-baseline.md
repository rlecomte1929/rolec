# Audit Baseline — Phase 0

**Run date:** 2026-05-25
**Mode:** Report-only, comprehensive depth, all personas
**Scope confirmed by user:** Employee + HR + Admin + Provider/Supplier (4th, lighter); recent customer calls weighted; AI Work Queue included for known-vs-new cross-ref.

## Environment

| Component | Status | Notes |
|---|---|---|
| Backend (`uvicorn backend.main:app :8000`) | HTTP 200 `/health` | Started from repo root. `cd backend && uvicorn main:app` form in CLAUDE.md is stale — relative imports require package path. |
| Frontend (`npm run dev :3000`) | HTTP 200 | Vite 5.4.21, ready in 223ms |
| TypeScript baseline | 0 errors (`tsc --noEmit` exit 0) | Clean snapshot — any new errors during audit attribution is unambiguous |
| Git working tree | 1 modified file (`assistant_router.ts`), no uncommitted commits | Pre-existing; not audit-related |

## Prior audit artifacts found

| File | Date | Relevance |
|---|---|---|
| `audit-docs/ReloPass_Audit_Final_Synthesis_INTERNAL.md` | 2026-04-26 | 15-task structured audit. Explicit limitation: "No customer-interview validation." Verdict 3-4x vs legacy. |
| `audit-docs/ReloPass_Audit_Investor_Cut.md` | 2026-04-26 | Investor-facing derivative |
| `audit-docs/ReloPass_Audit_Pitch_Ready_Cut.md` | 2026-04-26 | Buyer-facing derivative |
| `audit-docs/ReloPass_Revised_Execution_Plan.md` | 2026-04-26 | Execution plan post-audit |
| `relopass-figma-spec.md` | 2026-04 | Design intent baseline (Phase-1 wireframe spec) |
| `relopass-brand-audit-2026-04-23.md` | 2026-04-23 | Site copy/category audit. Composite **27/50**; "operating layer" / differentiation / compliance promise absent site-wide. |
| `ReloPass_Audit_Final_Synthesis_INTERNAL.md` (root) | 2026-04 | Duplicate of audit-docs version |

**Implication:** prior audit covers product strategy, verdict, architectural spikes, competitive landscape. **What it does NOT cover** (gaps this run must fill):
- Customer-interview validation (explicit T15 §11 limitation)
- Live UI evidence per persona (was inferred from screenshots, not driven)
- Code-level findings (full-stack expert lens — was product-level only)
- Security / accessibility / performance / UX-copy live evidence

## Codebase magnitudes

| Dimension | Count |
|---|---|
| Frontend LOC (`.ts`/`.tsx`) | 138,059 |
| Frontend feature dirs | 18 (`features/{admin,cases,employee,exceptions,hr,immigration,messages,platform-v2,policy,policy-builder,policy-config,readiness,recommendations,relocation-plan,relocation-plan-employee,resources,services,timeline}`) |
| Frontend pages | ~80+ in `src/pages/` |
| Frontend tests | 41 |
| Backend Python LOC | ~1.4M (includes `.venv` — exclude) |
| Backend `app/routers/` | 50 routers |
| Backend `app/services/` | 25 service modules |
| Backend tests | 212 |
| Supabase migrations | 280 |

## Notion data sources confirmed

| DB | Collection ID | Rows visible | Notes |
|---|---|---|---|
| Customer Interviews | `804549ef-5796-4fea-8915-78dc735cb107` | 11+ shown (6 real + 5 explicit `[SAMPLE]`) | Schema has Mom Test grade + pain signal + WTP signal + buyer/non-buyer |
| Pain Points | `11ef02cf-6ad5-45a1-b709-877e3f56e37f` | 25+ shown | Severity + Strategic Importance + Affected Persona multi-select. Filter views exist for HR Director, Employee, High-Severity, Most-Frequent. |
| AI Work Queue | `75d7ed78-91f4-46b6-b805-12e43abbecce` | 25+ shown | Has UX Constraints + Validation Criteria fields — perfect for known-vs-new cross-ref |

> **Superseded 2026-08-18.** _(that database is now titled “AI Work Queue (RETIRED)”; the live queue is `3bc887c6-4d48-8089-8188-fcf2dc3edc1b` / data source `4e2887c6-4d48-82c1-931e-87b09fb5c4ed`.)_ The id above is left as the record of what was true when this baseline was taken.


## Real (non-sample) customer interviews — sorted by recency

| Date | Person | Buyer type | Mom Test | Pain | WTP | Top quote |
|---|---|---|---|---|---|---|
| 2026-05-08 | Philippe Maury (ex Ford Credit CEO) | Consultant/Advisor | A | 5/5 | 3/5 | "Never had access to anything like ReloPass" |
| 2025-12-03 | Helena Harless (Welcome Service Geneva DSP) | Vendor | A | 5/5 | 2/5 | "It's not just a job, it's a LIFE" |
| 2025-11-27 | Florence Mandelik (refugee integration) | Other | — | — | — | not yet read |
| 2025-10-07 | Victoria @ NBIM | **In-house buyer**, pilot candidate | A | 5/5 | 4/5 | "Too many contacts and handovers, lack of single ownership" |
| 2025-06-25 | Clotilde Eyraud-joly (MBA researcher) | — | — | — | — | not yet read |
| 2025-06-10 | Christelle Chouet (PwC, French market) | — | — | — | — | not yet read |

**Sample interviews intentionally excluded** from customer signal (explicit "DO NOT treat as customer signal" tag): Marcus L./Pleo, Anne K./Cognite, Sofie H./Tibber, Johan Vikström/EY, Lars E./Kahoot. These are synthetic personas for prompt testing.

**Critical limitation flagged:** Only **one** real in-house HR buyer interview in the past 12 months (Victoria @ NBIM). The Phase-1 persona synthesis is necessarily reliant on the **Pain Points DB** (which has richer aggregated evidence) more than on raw interviews. Sample interviews are explicitly *not* used.

## Baseline locked. Proceeding to Phase 1.
