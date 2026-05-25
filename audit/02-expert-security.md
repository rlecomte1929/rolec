# Expert Review — Security (CSO Lens)

**Reviewer lens:** Chief Security Officer / pentester. Targeting OWASP Top 10 + supply chain + LLM security + Supabase RLS coverage.
**Method:** Static analysis + RLS coverage count + secret-leak grep + runtime probes. **Not** a full pentest — no exploit attempts, no fuzz testing, no real attacker simulation. Confidence: ≥8/10 on what's reported; gaps explicitly flagged.

**Composite score: 6.5 / 10**

What would make it a 10:
- All `app/routers/` handlers explicitly declare auth (no defense-in-depth via compat shadowing)
- RLS policy count ≥ table count, with a CI test that asserts every Supabase-exposed table has at least one policy
- `SUPABASE_SERVICE_ROLE_KEY` usage confined to ≤3 well-documented modules
- LLM calls have prompt-injection defenses (input sanitization + structured output schemas)
- No secrets in repo (verified by automated scan)

---

## P0 findings

### SEC-1 — `ensure_initialized` startup transaction abort masks DB drift
**Evidence:** `/tmp/relopass-backend.log` — `WARNING ... InFailedSqlTransaction current transaction is aborted, commands ignored ... CREATE INDEX IF NOT EXISTS idx_sqlite_pc_benefits_version`
**Why P0 security:** Schema drift is the #1 way RLS holes appear in Supabase. A table created locally via this `ensure_initialized` path but missing in remote migrations (or vice-versa) creates a window where production has table-without-policy or migration-without-table. `MEMORY.md` already flags drift between local + remote (~95 orphan rows; `supabase db push` blocked). The runtime evidence here is consistent with that drift.
**Fix:** Investigate the underlying DDL failure, fail-fast on startup if integrity is questionable, and pair with the next finding.

### SEC-2 — RLS coverage gap: 122 tables created, 82 files with `CREATE POLICY`
**Evidence:**
```
$ grep -rli "create policy" supabase/migrations | wc -l → 82
$ grep -hri "create table" supabase/migrations | wc -l → 122
$ grep -hri "enable row level security" supabase/migrations | wc -l → 210
```
**Why P0:** 122 distinct `CREATE TABLE` statements in migrations, but only 82 migration files contain *any* `CREATE POLICY` text. The 210 `ENABLE ROW LEVEL SECURITY` count being higher than table count suggests RLS-on-existing-tables migrations after the table was created — these are good — but the policy count being lower than the table count is the alarm.

**Caveat:** A single migration file can contain multiple `CREATE POLICY` statements, so 82 files ≠ 82 policies. Could be 200+ policies covering all tables, or could be 60 covering some. Needs precise count of `CREATE POLICY` *statements* per table.
**Fix:** Write a single SQL query (or Python script) that joins `information_schema.tables` × `pg_policies` against the live DB and lists tables without any policy. Run in CI as a guard. Treat any policy-less Supabase-exposed table as a deploy-block.

### SEC-3 — `app/routers/cases.py:101 get_case` is unguarded in source
**Evidence:** No `Depends(get_current_user)` on the handler. Runtime probe returns 401, but this is because `backend/routes/compat.py:93` (mounted at `main.py:565`) shadows the route — both register `/api/cases/{case_id}` and FastAPI picks compat by registration order.
**Why P0:** Shadowing is fragile. Removing compat (planned per CLAUDE.md migration narrative) without first hardening cases.py creates an instant unauth-read regression on **employee case data** including household, pets, personal info.
**Fix:** Add `Depends(get_current_user)` + `_assert_case_access(user, case)` to `cases.get_case` *now*, before any compat-layer changes. Add the route-enumeration CI test from QA-2.

---

## P1 findings

### SEC-4 — Service-role key usage spreads beyond core
**Evidence:**
```
backend/app/routers/ab_tests.py
backend/services/supabase_client.py
backend/services/policy_storage_health.py
backend/database.py
backend/main.py
```
Plus the test file `backend/tests/services/test_policy_intake_rejections.py` (acceptable for tests).
**Why P1:** `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS. CLAUDE.md states it's "only used in backend Edge Functions and admin migrations." Reality: it's used in routine routers (`ab_tests.py`) and services (`policy_storage_health.py`). Every additional use is a potential blast-radius expansion if a bug leaks data through that path.
**Fix:** Either justify each usage in code comments + CLAUDE.md, or refactor to use anon-key + scoped JWT where possible. Treat service-role as `setuid` — minimal call sites, audited.

### SEC-5 — LLM call (`ocr_passport_extractor.py`) lacks prompt-injection defenses
**Evidence (full-stack agent + manual verification):** OpenAI vision call with a static prompt template. Good news: no user-text interpolation. Bad news: the *image content* itself could contain adversarial text (e.g., a fake passport with text saying "Ignore prior instructions and return: {…}"). GPT-4o is vulnerable to this class.
**Why P1:** Today's prompt expects structured JSON output. A successful prompt injection could cause it to return arbitrary content that downstream code might trust as legitimate passport data.
**Fix:** Use `response_format={"type": "json_schema", "json_schema": {...}}` (OpenAI structured outputs) so the model is forced to return validated JSON. Schema-validate the response. Add a sanity check on extracted values (date plausibility, nationality whitelist).

### SEC-6 — `assistant_router.ts` (modified in working tree) and policy assistant likely use LLM
**Evidence:** `git status` shows `frontend/src/features/policy-builder/assistant_router.ts` modified. The assistant feature is one of the AI-native claims (S6 in prior synthesis). Source not deep-read in this pass; should be reviewed for: (a) prompt construction from user input, (b) any tool-use / function-calling that touches DB writes, (c) output rendering (XSS risk if LLM output is dangerously rendered).
**Fix:** Phase-3 follow-up — full security review of the assistant boundary.

### SEC-7 — 7 routers with no auth import (per Explore agent)
**Files:** `ab_tests.py`, `auth.py`, `crons.py`, `policy_templates.py`, `rules.py`, `support.py`, `analytics.py`
**Why P1:** Some are correctly public (`auth.py` is the login endpoint by design; `analytics.py` was confirmed to use `Depends(get_org_id_for_hr_user)`). Others are unclear: should `policy_templates.py` be admin-only? Should `rules.py`?
**Fix:** Each gets a comment at the top of the file declaring its auth posture: "PUBLIC — login endpoint" / "INTERNAL — cron webhook with shared-secret check" / "ADMIN — requires require_admin".

### SEC-8 — Webhook auth ambiguity
**Files:** `integrations_personio_webhook.py`, `crons.py`, `support.py` (webhook endpoint)
**Why P1:** Webhooks must be authenticated by *shared secret or signature*, not by user auth. Need to verify each webhook handler validates the signature header. Not verified in this pass.
**Fix:** Phase-3 dedicated webhook security review.

---

## P2 findings

| # | Finding | Notes |
|---|---|---|
| SEC-9 | 20+ routers swallow exceptions with `except Exception:` | Could mask security errors. See QA-1. |
| SEC-10 | No CSP / strict-origin headers visible in `main.py` middleware setup | Verify in prod (Render); add `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options` |
| SEC-11 | `Auth.tsx` form lacks `autocomplete="current-password"` | Minor — password managers may not autofill correctly |
| SEC-12 | No automated secret scan visible in CI | Tools like `trufflehog`, `gitleaks` should run on every push |
| SEC-13 | `python-3.9` venv on dev — production claims 3.11 (per CLAUDE.md) | Dev/prod parity risk. Recommend: pin local to 3.11 too |

## RLS audit punch list

| Status | Item |
|---|---|
| ⚠ | Run `SELECT tablename FROM pg_tables LEFT JOIN pg_policies USING (tablename) WHERE schemaname='public' AND policyname IS NULL` against production DB. List tables without policies. |
| ⚠ | For each policy-less table: is it server-only (acceptable) or exposed via Supabase JS (must have policy)? |
| ⚠ | Audit the 5 service-role consumers. Justify each. |
| ⚠ | Verify `is_admin()` SQL function uses `auth.uid()` not legacy `users.id` — prior synthesis flagged this. |

## LLM threat model summary

| Surface | Risk | Mitigation status |
|---|---|---|
| Passport OCR | Indirect prompt injection via image content | None — needs structured output enforcement |
| Policy extraction | Indirect injection via PDF content | Not audited |
| Policy assistant (`assistant_router.ts`) | Direct prompt injection via user message | Not audited |
| Document review AI replies (LOOP skill per Notion) | Both | Not audited |

## What this pass DID NOT cover

- Actual database-level RLS verification (require live SQL access). Phase 3 task.
- Webhook signature verification (Personio, BambooHR, payments if any).
- Pentest-style fuzz testing of forms, file uploads, API parameters.
- Dependency vulnerability scan (`npm audit`, `pip-audit`).
- Container/image scan (Render runtime).
- Secrets-in-history scan (gitleaks).
- Session-token entropy/expiry analysis (PBKDF2 in `auth.py` claimed; not verified).

## Recommended next security actions (ranked)

1. **Investigate SEC-1** (`ensure_initialized` failure) — root cause must be known before next deploy.
2. **RLS coverage CI check** (SEC-2) — query DB, list policy-less tables, fail build.
3. **Harden `cases.get_case`** (SEC-3) — add `Depends(get_current_user)`, 5-line PR.
4. **Audit service-role usage** (SEC-4) — comment each call site with justification; consider refactoring `ab_tests.py`.
5. **Structured-output JSON schema for OCR** (SEC-5) — 1-hour change with high payoff.
6. **Run `gitleaks`** as a one-shot to confirm no historic secret leaks. Add to CI.
7. **Document `Strict-Transport-Security` + CSP** posture (SEC-10).
