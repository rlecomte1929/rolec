# Docs index

`docs/` has grown to ~80 markdown files, many of them design notes, phase reports, or one-off audits captured in flight. Not all of them are current. This file lists the ones that are worth reading **today**, grouped by what you're trying to do.

Everything else in `docs/` should be treated as historical context — useful for archaeology, but do not take it as authoritative over the code.

## Start here (new contributors)

- **[../README.md](../README.md)** — stack, product surface, quick start, deploy
- **[DATABASE_ARCHITECTURE_MAP.md](DATABASE_ARCHITECTURE_MAP.md)** — high-level DB domain map
- **[SUPABASE_MIGRATIONS.md](SUPABASE_MIGRATIONS.md)** — how migrations are organized and applied

## Auth & identity

- **[AUTH_AND_DATA_FLOW_MAP.md](AUTH_AND_DATA_FLOW_MAP.md)** — overall auth flow including Supabase sync
- **[identity/](identity/)** — identity-normalization and reconciliation notes (still actively referenced by backend services)
- **[SUPABASE_AUTH_MIGRATION_PLAN.md](SUPABASE_AUTH_MIGRATION_PLAN.md)** — plan to consolidate onto Supabase Auth (partially executed, see code)

## Policy pipeline (the largest subsystem)

The canonical pipeline is ingest → normalize → canonical → publish → assistant. These are the current contracts:

- **[policy/canonical-policy-pipeline.md](policy/canonical-policy-pipeline.md)**
- **[policy/canonical-entitlement-model.md](policy/canonical-entitlement-model.md)**
- **[policy/policy-assistant-contract.md](policy/policy-assistant-contract.md)**
- **[policy/normalization-persistence.md](policy/normalization-persistence.md)**
- **[policy/production-hr-policy-rollout-checklist.md](policy/production-hr-policy-rollout-checklist.md)**

## Assignments / cases

- **[assignments/assignment-domain-audit.md](assignments/assignment-domain-audit.md)** — authoritative domain map
- **[assignments/company-scope-guardrails.md](assignments/company-scope-guardrails.md)** — multi-tenant invariants to preserve
- **[assignments/multi-assignment-routing.md](assignments/multi-assignment-routing.md)**
- **[employee/canonical-employee-case-context.md](employee/canonical-employee-case-context.md)**

## Operations & reliability

- **[PRODUCTION_RELIABILITY.md](PRODUCTION_RELIABILITY.md)** — what can break, how to diagnose
- **[OBSERVABILITY_ANALYTICS.md](OBSERVABILITY_ANALYTICS.md)** — logging / event conventions
- **[DEMO_RUNBOOK.md](DEMO_RUNBOOK.md)** — pre-demo checklist
- **[testing/policy-processing-e2e.md](testing/policy-processing-e2e.md)** — how the E2E policy tests are structured

## QA packs (useful for regression runs)

- **[qa/hr-policy-workflow-qa-pack.md](qa/hr-policy-workflow-qa-pack.md)**
- **[qa/policy-assistant-qa-pack.md](qa/policy-assistant-qa-pack.md)**

## Known open items (tracked, not fixed)

- README / docs accuracy pass — done in commit that introduced this index
- Migrate passwords from PBKDF2 to argon2
- Collapse the dual auth (legacy tokens + Supabase JWT) to a single source of truth — plan in `SUPABASE_AUTH_MIGRATION_PLAN.md`
- Stand up CI (GitHub Actions running `pytest`, `tsc`, `vite build`, lint)
- Add request-level caching + pagination on unbounded `.all()` queries
- Replace `BackgroundTasks` with a durable queue for policy extraction
- GDPR consent surface + soft-delete/erasure endpoint
- Sentry + structured JSON logging

## What NOT to trust

If a doc name contains any of `AUDIT_REPORT`, `PHASE1_STEPN`, `DEPLOYMENT_NOTE`, `BLOCK5`, `FIXES_APPLIED`, or `MIGRATION_PHASE_`, it's almost certainly a point-in-time artifact from an earlier refactor. Useful for context, not authoritative.

When a doc disagrees with the code, the code wins.
