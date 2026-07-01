# Admin audit — gap register

Findings from the static audit (`origin/main @ 0f14c760`). Severity: **P0** (security/data risk or operator blocked) · **P1** (significant, fix soon) · **P2** (meaningful improvement) · **P3** (hygiene). Effort: **S** (≤1d) · **M** (1–5d) · **L** (multi-week). Dimensions per the rubric (1 Observability · 2 Control · 3 Feedback · 4 BugRoutines · 5 HITL · 6 Access&Audit · 7 IA · 8 Blast-radius).

## P1 — significant (fix soon)

| ID | Dim | Sev | Eff | Finding | Recommendation |
|---|---|---|---|---|---|
| A-01 | 6 | P1 | S | `/admin/countries` + `/:cc` render with **no `RequireAdminRoute`** (declared in `routes.ts`, not `navigation/`) — any authenticated user reaches the Country Requirements CMS. | Wrap both in `RequireAdminRoute`; add a route-guard test. |
| A-02 | 6 | P1 | M | `CRON_SECRET == Authorization` → synthetic **full-ADMIN** user (`auth_deps.get_current_user`), a static env root credential outside the allowlist. | Scope to specific cron routes / per-job tokens; never grant blanket ADMIN; rotate. |
| A-03 | 6 | P1 | M | **No in-app admin lifecycle**: adding an admin = SQL (`add_admin_allowlist` only at boot/seed); **no remove/disable function exists**. | Add gated `POST/DELETE /api/admin/admins` + UI + audit. |
| A-04 | 6 | P1 | M | Audit logging fragmented (3 mechanisms / 2 tables); silent mutations in `admin_catalog`, `admin_prospects`, `admin_staging`, `admin_review_queue`, `admin_notifications`, `admin_prompts`, and company/people/assignment CRUD. | Route all critical mutations through one `audit_logs` writer (app-level, per the id-less-table pattern). |
| A-05 | 6 | P1 | M | No platform-wide admin audit-log **viewer** (only per-case/per-request scoped reads). | Build an admin audit browser over `audit_logs`. |
| O-01 | 1 | P1 | M | RAG-eval dashboard (`/admin/rag-quality`) serves a **mock** series until reports land; producers aren't scheduled into a committed admin feed. | Wire the report-only eval workflow output → `audit/rag_eval/` → dashboard `source:"live"`. |
| O-02 | 1 | P1 | M | Gate-impact / answer-provenance is **company-scoped** (`require_admin_or_hr` + org filter) — no **fleet-wide** AI governance view. | Add an admin fleet rollup endpoint + view. |
| C-01 | 2 | P1 | M | AI behavior flags (groundedness gate, rerank, learned-weights) are **env-only**; flipping needs a redeploy and is invisible. | Admin AI-controls panel (see D-HITL) with gated toggles + audit. |
| F-01 | 3 | P1 | S | `policy_answer_helpfulness` endpoint has **no frontend producer** — the end-user policy-answer thumbs are inert (the Phase-2 feature can't be submitted). | Wire a 👍/👎 control in the policy-assistant answer component → `POST /api/policy-assistant/helpfulness`. |
| F-02 | 3 | P1 | M | `ai_human_feedback` + `policy_answer_helpfulness` are **write-only to ML/eval**; no admin browse (admin sees only one aggregate gate-impact stat). | Admin AI-feedback view (see D-Feedback). |
| B-01 | 4 | P1 | L | **No in-app bridge** from a reported bug to triage/agent dispatch — `submit_feedback` only inserts a row; all automation is external (Notion + cron). | Build report→triage→dispatch→status loop (see D-BugRoutine). |
| H-01 | 5 | P1 | M | Source-reliability recompute **auto-mutates source trust daily** off rejected AI feedback with **no human approval**. | Add an admin-visible diff + approval step or kill-switch. |
| H-02 | 5 | P1 | M | AI-quality levers ungated env flags — flipping is uncontrolled/invisible (HITL view of C-01). | Gate behind admin control + audit + kill-switch. |
| BR-01 | 8 | P1 | M | Destructive operator actions (`/actions/purge-cases`, `override-eligibility`, `unlock-case`, impersonate) audit unevenly (legacy table) and blast radius (tenant vs fleet) is unlabeled. | Uniform audit + confirm + reversibility + blast-radius labels. |

## P2 — meaningful improvement

| ID | Dim | Sev | Eff | Finding | Recommendation |
|---|---|---|---|---|---|
| A-06 | 6 | P2 | S | `audit_logs` trigger needs an `id` column + CHECK limits action_type to insert/update/delete → semantic events / id-less tables uncovered. | Use app-level writers with `new_value.event` for semantic events. |
| A-07 | 6 | P2 | S | Duplicate admin-check logic (`admin_workflow_analytics` etc. reimplement `_require_admin`). | Consolidate on `auth_deps.require_admin`. |
| O-03 | 1 | P2 | S | Overview "System SLA (30D)" StatCard is hard-null ("No platform aggregate connected"). | Wire a real aggregate or remove the card. |
| O-04 | 1 | P2 | M | Gate-impact sweep + weight-fit are CLI-only (no endpoint). | Surface as read-only admin endpoints. |
| O-05 | 1 | P2 | M | No unified operator "is the platform healthy now" home (signals scattered + buried). | Compose an operator health home from existing signals. |
| C-02 | 2 | P2 | M | Supplier ranking weights not readable/editable in-app; learned-weights written only by offline CLI. | Admin read + gated per-segment override. |
| C-03 | 2 | P2 | M | Eval thresholds (`MetricSpec`) hardcoded; no admin tuning. | Make admin-configurable with guardrails. |
| F-03 | 3 | P2 | M | Analytics beacons + `policy_assistant_answer_audits` are admin dead-ends. | Surface in a usage view or retire. |
| F-04 | 3 | P2 | S | `AdminFeedback` reads `public.feedback` directly via Supabase (not the API pattern) and is buried. | Standardize on a backend GET; promote to sidebar. |
| B-02 | 4 | P2 | M | Feedback/error tickets lack SLA/owner/status surfaced to the reporter. | Add ticket lifecycle + reporter notification. |
| B-03 | 4 | P2 | S | External Notion/skills + cron automation invisible from admin (no run status/health). | Surface routine runs/health in-app. |
| H-03 | 5 | P2 | S | No per-feature AI kill-switch surface. | Add kill-switches to the AI-controls panel. |
| I-01 | 7 | P2 | S | ~20 live pages buried (Feedback, Errors, Prompts, RAG-quality, A/B, Policies, Suppliers…). | Restructure sidebar/IA. |
| I-02 | 7 | P2 | S | Dead/decoy/duplicate surfaces (3 dead sidebars, route-dead pages, dup dashboards, orphan `AdminExceptions`, legacy rollback routes). | Remove after confirming no rollback need. |
| BR-02 | 8 | P2 | S | Impersonation: verify time-boxed + audited + clearly indicated in UI. | Confirm/enforce the three. |
| BR-03 | 8 | P2 | M | Fleet-wide vs company-scoped actions not delineated in UI. | Label blast radius per action. |

## P3 — hygiene

| ID | Dim | Sev | Eff | Finding | Recommendation |
|---|---|---|---|---|---|
| C-04 | 2 | P3 | S | Model/temperature/embeddings env-only (config-as-code OK). | Surface current values read-only. |
| H-04 | 5 | P3 | S | No in-app visibility of pending/applied migrations. | Optional read-only migration status. |
| I-03 | 7 | P3 | S | Inconsistent tab layouts (Ops/ReviewQueue/Freshness). | Consolidate via the WIP `AdminTabLayout`. |
| I-04 | 7 | P3 | S | `-v2` duplicate routes linger after V2 became default. | Collapse aliases. |

**Counts:** P1 = 14 · P2 = 16 · P3 = 4 (34 findings). The three priority systems Romain named map to F-01/F-02/F-04 (D-Feedback), B-01/B-02/B-03 (D-BugRoutine), and C-01/H-01/H-02/H-03 (D-HITL).
