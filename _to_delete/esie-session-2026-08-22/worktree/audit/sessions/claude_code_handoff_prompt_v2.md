# Claude Code handoff packet v2 — supersedes v1 (2026-06-03 end-of-day)

**Paste this entire block into Claude Code at the start of the next session. Discard the v1 handoff — this is the full update after today's compliance + GTM sprint.**

---

You're picking up ReloPass work from a very long Cowork session that finished 2026-06-03. The session shipped 18 markdown deliverables and closed ~206 Notion tasks. The Notion AI Work Queue is now in good shape — heavily archived against the 3-week MVP scope, with every Cowork-feasible spec doc already written. Your job is implementation.

**Don't re-triage the queue. Don't ask if you should archive things. Don't re-derive specs — they exist.** Just execute.

## Use this skill stack in this order

1. `relopass-dev-queue` — your primary tool. Codebase recon → plan → approval gate → implement → validate → commit. Use for every code task.
2. `notion-task-executor` — only if `relopass-dev-queue` is unavailable. Skip Step 0 triage (already done extensively).
3. `notion-review-validator` at end of each task to close out.

## MVP scope (Option 2 compression — already applied)

8 capabilities. Stay inside:
1. Multi-tenant company → HR → employee (✅ shipped)
2. Case creation + allocation by HR (✅ shipped)
3. HR Policy Builder — **standard template only**, NO PDF upload + AI extraction (cut)
4. Employee intake — IMM-08 interview shell is the biggest delivery
5. Country-specific immigration path — **pilot ONE corridor only** (FR→NO)
6. Document OCR — **PASSPORT_TD3 + EMPLOYMENT_CONTRACT only**, plus C2-01 family docs (MARRIAGE_CERT / BIRTH_CERT / FOSTER_CARE_ORDER). DIPLOMA, PAYSLIP, EU_RESIDENCE_PERMIT, TAX_CERT, CRIMINAL_RECORD all archived.
7. Milestone tracker + reminders — **D-7/D-3/D-0 email cron only** (AIQ-34-D pattern), NO in-app notification bell
8. Provider directory + RFQ — **HR-curated list only**, NO RFQ flow

If a task you pick up is for an archived capability, mark it Archived and move on.

---

## Reference docs to move from outputs/ → repo

Run this batch FIRST. All these files exist in the Cowork outputs folder and need to land in the repo before any task that consumes them.

```bash
# Compliance bundle (EU AI Act + GDPR)
mv outputs/annex_iv_technical_doc_v1.md            audit/eu_ai_act/annex_iv_technical_doc_v1.md
mv outputs/risk_register_v1.md                     audit/eu_ai_act/risk_register_v1.md
mv outputs/conformity_assessment_record_v1.md      audit/eu_ai_act/conformity_assessment_record_v1.md
mv outputs/priv-003_data_retention_policy_v1.md    audit/gdpr/data_retention_policy_v1.md
mv outputs/p1-07e_case_outcomes_gdpr.md            docs/case_outcomes_gdpr.md
mv outputs/priv-001_erasure_runbook_v1.md          audit/gdpr/erasure_runbook_v1.md
mv outputs/priv-005_privacy_notice_v1.md           audit/gdpr/privacy_notice_v1.md
mv outputs/ai-005_post_market_monitoring_plan_v1.md audit/eu_ai_act/post_market_monitoring_plan_v1.md

# FRIDAY-004 hero rewrite pack
mv outputs/friday-004a_positioning_sentence.md     audit/gtm/positioning_v1.md
mv outputs/friday-004b_hero_variants.md            audit/gtm/hero_variants_v1.md
mv outputs/friday-004c_proof_block.md              audit/gtm/proof_block_v1.md
mv outputs/friday-004d_seo_meta_spec.md            audit/gtm/seo_meta_spec_v1.md

# C1-12U + C1-18 (from earlier)
mv outputs/c1-12u_resolution_ui_micro_states.md    docs/design/c1-12u_resolution_ui_states.md
mv outputs/demo_marc_script.md                     audit/gtm/demo_marc_script.md
mv outputs/demo_priya_script.md                    audit/gtm/demo_priya_script.md
mv outputs/demo_scripts_brand_audit.md             audit/gtm/demo_scripts_brand_audit.md

# Pathway strings (from earlier)
mv outputs/pathway_strings_v1.json                 apps/pathway/locales/en/pathway.json

# Data API audit (from earlier)
mv outputs/data-api-audit.md                       backend/docs/data-api-audit.md

# Keep as session reference (NOT for repo)
# outputs/github_pr_audit_2026-06-03.md
# outputs/claude_code_handoff_prompt.md            (v1, superseded by this file)
# outputs/claude_code_handoff_prompt_v2.md         (this file)
```

Create the `audit/eu_ai_act/`, `audit/gdpr/`, and `audit/gtm/` directories if they don't exist. Commit this move as a single PR before touching anything else.

---

## Priority queue — work in this exact order

### Tier 0 — Unblock the existing PRs (FIRST — these were already queued from yesterday)

**0.1. Fix the migration drift killing PR #233's Supabase preview replay**

In `supabase/migrations/`, find the migration that creates `exception_requests.organization_id` as TEXT and the `exception_requests_select_tenant` RLS policy that fails with `text = uuid`. Verified during yesterday's audit:
- `profiles.id` and `profiles.company_id` are both `uuid`.
- `exception_requests` exists on prod with no `organization_id` column yet.

Fix (pick option A unless something else relies on TEXT):

```sql
ALTER TABLE public.exception_requests
  ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid;
```

Then rebase PR #233 (`feat/p1-02-specialist-review`) on main. Same for PR #235 (`fix/restore-unregistered-routers`) — conflict in `backend/main.py`. Push both, merge once green.

**0.2. Push 2 branches that were left local-only after Cowork couldn't reach them**

- `feature/sec-006-upload-validation` (4 commits, AIQ-478 SEC-006): push branch, open PR, set repo var `RLS_COVERAGE_DATABASE_URL_SET=true` so the new bucket-check CI job runs, merge once green. Notion task is in Validation.
- `feat/c1-12-be-resolve-escalate` (commit 61928daa, AIQ-570 C1-12-be): push branch, open PR, run live integration tests against fixture DB, verify 200/409/404 paths on resolve + escalate endpoints, merge. Notion task is in Validation.

After each merges, flip the Notion task to Done with `Final Validation Result = Passed`.

### Tier 1 — The 4 bug tickets filed yesterday

All Ready for AI in Notion with full validation criteria + suggested fix paths:

- **AIQ-760 · /hr/\* routes are NOT role-gated** (P1). Add `RequireRole={['HR','ADMIN']}` wrapper around `/hr/*` route block, mirror `/admin/*` pattern. Likely in `frontend/src/App.tsx` or `frontend/src/navigation/routes.ts`. **Fix this first** — it eliminates the AIQ-128 phantom "Failed to load provider grid" error as a side effect.
- **Review Queue counter mismatch** (P1). `/admin/overview` shows "24 items · 8 awaiting" while `/admin/review-queue` shows 0. Unify the count source. Likely in AdminOverviewPage.
- **AIQ-757 · Marketing redirect** (P2). `/` and `/why-relopass` redirect signed-in users; `/platform`, `/how-it-works`, `/get-started` don't. Remove the redirect on `/` + `/why-relopass`.
- **/admin/companies V2 missing column resize + drag-reorder** (P2). DOM inspection confirmed `draggable: false`, `cursor: auto`, no resize handles. Add HTML5 drag-and-drop + `cursor: col-resize` on column boundaries.

### Tier 2 — FRIDAY-004e: ship the hero rewrite

Consumes 4 specs in `audit/gtm/`:
- `positioning_v1.md` — locked positioning sentence
- `hero_variants_v1.md` — recommended pair: headline 🅰 + sub-hero ① + A/B challenger 🅰+④
- `proof_block_v1.md` — 3 lines (audit logs · bias testing · human-in-loop)
- `seo_meta_spec_v1.md` — copy/paste meta tags, og:tags, JSON-LD

**Implementation order (from `seo_meta_spec_v1.md` §8)**:
1. Update `<title>` and `<meta description>`.
2. Add the og:* + twitter:* blocks.
3. Update hero component with the recommended pair (🅰 headline + ① sub-hero).
4. Add the 3-line proof block under the hero (layout spec in `proof_block_v1.md` §5).
5. **Commission the og:image** before deploying — without it, og:image returns 404 and breaks LinkedIn previews. Spec in `seo_meta_spec_v1.md` §5.
6. Add the JSON-LD Organization markup. **Confirm placeholders first**: founding date, LinkedIn slug, X handle, GitHub link, sales/support emails.
7. Wire A/B framework if available (control = old hero, variant = 🅰+① recommended). If no framework, ship 100% and add to known-gaps.
8. Validate: LinkedIn Post Inspector, X Card Validator, Google Rich Results, Slack /link-unfurl debug. Lighthouse SEO ≥ 95.

Notion: AIQ-XXX (FRIDAY-004e). Mark Done after merge.

### Tier 3 — GDPR endpoints + UI (consume the PRIV-001 + PRIV-005 specs)

**3.1 PRIV-005 privacy notice gate** (Notion in Validation):

- **Migration**: `supabase/migrations/[date]_privacy_consents.sql` per `audit/gdpr/privacy_notice_v1.md` §4. Includes table + indices + RLS policies.
- **API**: `POST /api/privacy/consents` per §6.
- **React component**: `<PrivacyNoticeGate />` per §5. Wire into IMM-07 consent screen path.
- **Validation**: §3 element-by-element Art. 13 mapping. Add the explicit consequence clause from §3 gap before merge.
- Move Notion to Done after merge.

**3.2 PRIV-001 right-to-erasure** (Notion in Validation):

- **Migration**: define `fn_erase_employee_data` function per `audit/gdpr/erasure_runbook_v1.md` §4.4. Add `app.pii_pepper` setting backed by env-managed secret (Render). Add `pii_redacted_at` columns to `case_audit_events` + `rce.rule_citations` if not present.
- **API**: `POST /api/gdpr/erasure` and `GET /api/gdpr/data-export` per §3.5 + §6 spec. SLA-clock tracking in metadata.
- **React component**: "Delete my data" button on Pathway profile + admin-side support tool to handle email-channel requests.
- **PII inventory**: §5 inventory updates `docs/case_outcomes_gdpr.md` engineering checklist (§13).
- Move Notion to Done after merge.

**3.3 PRIV-003 retention enforcement** (gated on Romain row-by-row approval):

- **Pre-req**: Romain approves §3 of `audit/gdpr/data_retention_policy_v1.md` row-by-row (he uses §8 approval log).
- **Once approved**: implement pg_cron jobs per §4 spec. One job per data class + retention test + alert-on-zero-delete.
- **Staging dry-run** before production deploy. Verify the `audit.retention_runs` aggregate looks sensible.
- Move Notion to Done after deploy + 24h smoke test.

### Tier 4 — EU AI Act post-market monitoring (AI-005 implementation)

Consumes `audit/eu_ai_act/post_market_monitoring_plan_v1.md`.

- **Migration**: 3 tables per §4.1: `post_market_metrics_daily`, `post_market_alerts`, `post_market_quarterly_reviews`. Include indices.
- **pg_cron aggregators**: 21 jobs per §4.2 pattern, one per metric in §3.
- **Alert jobs**: per §4.3 pattern, scheduled 5 min after each aggregator.
- **Observability emission**: every aggregator emits a structured log line. Wire CloudWatch / Sentry counter metrics if available.
- **First quarterly report**: dry-run a `2026Q3` populate against fixture data so the report template (§6.3) is exercised.
- Move Notion (AI-005, AIQ-653) to Done after the migration + at least 1 aggregator + 1 alert + the dry-run quarterly report all ship.

### Tier 5 — FRIDAY-003 finish

- **003b** — Read `backend/docs/data-api-audit.md`. Answer the 8 VERIFY questions by greping the frontend for `supabase.from('<table>'`. For each VERIFY table with zero hits, add to REVOKE list. Write `supabase/migrations/[date]_data_api_opt_out.sql` using the SQL block in the audit doc. Apply to staging. Confirm AUDIT-A3 RLS guard still green.
- **003c** — After 003b staging is green for 24h, apply to production. Smoke test. Document outcome in audit doc.

### Tier 6 — IMM frontend stack (the biggest MVP delivery — Cohort 1 critical path)

- **IMM-07** Frontend — GDPR consent screen before intake (now consumes the PRIV-005 `<PrivacyNoticeGate />` from Tier 3.1).
- **IMM-08** Frontend — Smart interview shell + question renderer. THE biggest delivery.
- **IMM-09** Frontend — Passport OCR upload + extract + confirm flow.
- **IMM-10** Frontend — wire Step 4 (last open IMM frontend).

Backend dependencies (IMM-02 through IMM-06) already shipped — Done.

### Tier 7 — C1 series finishing

- **C1-04 LangGraph node** — consume the prompt at `prompts/docs/classifier/v1.txt`. AIQ-489 already closed Done but worth reviewing implementation.
- **C1-05c EMPLOYMENT_CONTRACT** agent runtime — consume `prompts/extraction/employment_contract_{fr,de,no}_v1.txt`.
- **C1-05b PASSPORT_TD3** agent runtime — consume the C1-05P-b prompt.
- **C1-07 entity resolver** — consume `prompts/entity/resolver_v1.txt`.
- **C2-01 family doc cohort** — MARRIAGE_CERT, BIRTH_CERT, FOSTER_CARE_ORDER. Only family docs; CRIMINAL/TAX/HOUSING archived.

### Tier 8 — Compliance bundle gap closure (counsel coordination + Cowork-shippable follow-ups)

After Tier 4 ships, the EU AI Act bundle has 18 catalogued gaps across the 4 deliverables (annex_iv §1-§9, risk register §9, conformity assessment §5, post-market plan §10). These split into:

- **Engineering**: AI-004f incident response template + secondary on-call assignment. Mostly a Romain decision + a calendar item.
- **Counsel handoff**: Article 47 declaration of conformity drafting (counsel + Romain sign), Article 17 QMS docs, ISO 42001 gap analysis.
- **Customer-facing**: `/eu-ai-act` landing page (consumes the 3 EU AI Act docs), public `/changelog`, public `/versioning` policy page.

Don't auto-file Tier 8. Surface the gap list when Tier 4 is done and ask Romain which to prioritize.

---

## Things to NOT do

- **Don't archive anything else.** The triage is done — 200+ moved to terminal state today.
- **Don't execute any C2-* task except C2-01** (family). C2-02a/b/c (criminal, tax, housing leases) are archived per Option 2.
- **Don't build the AI assistant chat** (P4-*/P5-* series). Archived — not in MVP.
- **Don't build the PDF policy upload + LLM extraction** (P2-3 series). Archived — Policy Builder is standard-template only.
- **Don't merge PRs without per-PR confirmation from Romain** (Cowork rule, still applies in Claude Code by default).
- **Don't re-write any of the 18 spec docs from today.** They're v1; counsel review converts them to submission-ready. The next pass is v1.1.
- **Don't skip the og:image commission** before shipping FRIDAY-004e — half-shipped hero is worse than not shipping.
- **Don't ship PRIV-003 pg_cron without Romain's row-by-row approval** of the retention schedule (§8 approval log in that doc).

---

## Per-deliverable Notion update protocol

For every implementation task in Tiers 0-8:

1. Read the corresponding spec doc from `audit/`.
2. Use `relopass-dev-queue` skill's codebase recon + plan + approval gate.
3. After implementation + tests + commit:
   - Update the Notion task: `Status` → `Done`, `Final Validation Result` → `Passed`.
   - Append an Execution Notes block (template in `relopass-dev-queue` Phase 7).
   - Include the PR number in the notes for traceability.
4. If the implementation surfaces a gap that wasn't in the spec, append a "Discovered gaps" sub-section in Execution Notes and (optionally) file a follow-up task.

---

## Quick-start commands

```bash
# In Claude Code at the repo root:
cd /Users/romainlecomte/Documents/GitHub/rolec
git fetch origin && git checkout main && git pull

# Move the 18 deliverables into the repo first (use the batch in §"Reference docs" above)
# Open a PR with just the moves: "docs: import Cowork compliance bundle 2026-06-03"

# Then in the session:
# "Use relopass-dev-queue skill. Start at Tier 0.1 — fix the exception_requests
#  migration drift killing PR #233 preview replay. Reference
#  audit/sessions/claude_code_handoff_prompt_v2.md for the full priority queue."
```

---

## What's already in Done state on Notion (the big list)

Cumulative through 2026-06-03 end-of-day:

**EU AI Act core**:
- AI-001 (Annex III classification)
- AI-002 (human oversight — archived but shipped)
- AI-003 (Annex IV technical doc)
- AI-004 (conformity assessment record)
- AI-006 (risk register)

**EU AI Act partial (Validation status — code awaits implementation)**:
- AI-005 (post-market monitoring plan)

**GDPR / Privacy core**:
- PRIV-003 (retention policy)
- P1-07e (case-outcomes GDPR checklist)

**GDPR / Privacy partial (Validation status)**:
- PRIV-001 (erasure runbook + anonymisation + PII inventory)
- PRIV-005 (privacy notice copy + schema + component spec)
- PRIV-004 (DPAs — still in progress on Romain side)

**FRIDAY-004 GTM**:
- FRIDAY-004 parent (decomposed → Done)
- 004a (positioning + buyer-validation kit)
- 004b (hero variants)
- 004c (proof block)
- 004d (SEO meta spec)
- 004e (Ready for AI — Claude Code implementation work)

**Other content shipped today**:
- C1-12U (Resolution UI micro-states spec)
- C1-18 (Marc + Priya demo scripts)
- Brand audit on demo scripts
- 7 PRs merged yesterday (#229-#232, #234, #236, #237)

`git pull origin main` before starting any work.

---

## Session totals (full day)

- **8 PRs merged** to main
- **~206 Notion tasks** moved to terminal state (Done / Archived / Rejected / Validation)
- **18 deliverables shipped** to outputs/
- **5 new Notion subtasks created** (FRIDAY-004a-e)
- **EU AI Act + GDPR compliance v1 bundle**: complete

---

*Handoff prompt v2 generated 2026-06-03 by Cowork session at end-of-day. Supersedes v1 from same day. v3 should be expected after Claude Code processes Tiers 0-4.*
