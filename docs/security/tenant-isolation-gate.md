# Tenant-isolation gate (SEC-02 / AIQ-1165)

**Goal:** guarantee "company A can never see or mutate company B's data" stays
true on every change — preventing recurrence of the cross-tenant leak the probe
caught (HR A acting on company B's case).

There are two layers: an **always-on CI gate** (fast, no live DB) and a
**pre-release live probe** (slow, runs against a real deployment).

---

## 1. CI gate — runs on every backend PR (the regression guard)

`.github/workflows/ci.yml` → `backend-tests` runs these on any PR touching
`backend/**` or `scripts/**`:

- `backend/tests/test_tenant_isolation_behavioral.py` — exercises the two central
  authorization primitives that **every** company-scoped read/mutation funnels
  through:
  - `_hr_can_access_assignment(...)` — cross-tenant read returns **False**.
  - `_assert_hr_can_mutate_case(...)` — cross-tenant mutate raises **HTTP 404**
    (404, not 403, so we never leak that the other company's case exists).
  Both directions are asserted (A↛B and B↛A), plus the admin override and the
  owner-HR override.
- `backend/tests/test_hr_assign_tenant_scope.py` — company-scope on the **assign**
  endpoint.
- `backend/tests/test_hr_mutation_tenant_scope.py` — company-scope on the
  **mutating** case endpoints (patch/claim/etc.).

**Why testing the guard is sufficient for the high-risk endpoints:** case
assign/claim/patch, policy, and exceptions all enforce scope by calling
`_assert_hr_can_mutate_case` / `_hr_can_access_assignment`. Testing those guards
directly proves the scope check itself; the per-endpoint scope tests above prove
the highest-risk routes actually invoke it.

**Pass/fail:** a green `backend-tests` job means isolation holds. A failure here
is a **launch blocker** — do not merge.

> Coverage gap to close in a follow-up: assert (e.g. via a route-introspection
> test) that *every* mutating `/api/hr/cases/**` and policy/exceptions handler
> calls the guard, so a newly-added endpoint that forgets the check fails CI.

---

## 2. Pre-release live probe — `scripts/verify_tenant_isolation.py`

End-to-end check against a real deployment. It provisions two throwaway tenants
(A and B) via the real APIs — each with an HR, a case, and a published policy —
then asserts from each HR's perspective that they see **only** their own
company's data.

```bash
RELOPASS_API_BASE=https://api.relopass.com python3 scripts/verify_tenant_isolation.py
```

**Verdicts:**
- `PASS` — isolated (ship-safe).
- `LEAK` — cross-tenant access — **security FAIL, launch blocker**.
- `FAIL` — setup error (investigate; not a verdict on isolation).
- `BLOCKED` — a prerequisite failed.

**Why it is NOT a CI job:** it registers 2 real tenants per run, and `register`
is rate-limited to 5/hour (SEC-004), so it cannot run on every PR. It also writes
to the target environment (guarded by `_prod_write_guard`). Run it **before each
release** (or after any change to the case/assignment/policy authorization paths),
not per-PR. Throwaway tenants are namespaced (`Probe RLS-A/B <ts>`, `@probe.test`)
and cleaned by `scripts/fresh_onboarding_teardown.sql`.

---

## When to run what

| Change | CI gate (auto) | Live probe (manual) |
|---|---|---|
| Any backend PR | ✅ runs | — |
| Touching case/assignment/policy/exceptions authz | ✅ runs | ▶ run before merge to release |
| Cutting a release | ✅ (already green) | ▶ run; require `PASS` |
