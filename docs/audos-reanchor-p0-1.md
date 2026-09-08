# Re-anchor: this IS ReloPass, and it is your own commit

You've lost session context. Everything in the brief refers to `rlecomte1929/rolec` — the same repo as the Stripe work. Verify it yourself before replying; every item below is checkable in under a minute.

---

## 1. The commit in question is yours, from today

```bash
git show 3f9ed63a49554f3d3db433e953928cbc42aa5e4b --stat
```

```
Author:  rlecomte1929 <romain_lecomte@hotmail.com>
Date:    2026-07-19 20:03:21 +0200
Branch:  audit/stage-p0-1-eager-policy-resolution
Subject: P0-1: eager policy resolution for test-drive cases + zero silent policy failures
```

Its own message references `resolved_assignment_policies`, the AIQ-1621 seed, `test_drive.py`, and the config-matrix persistence problem. You wrote it roughly two hours ago. It changed 9 files and added 342 lines to `backend/tests/test_policy_resolution.py`.

Your earlier commit `121403c80b2ae3976259cd360264fc528b28e8e1` on `fix/f14-shared-taxonomy` is the one you already reported to Romain, including the PR 403 blocker.

## 2. Every term you flagged as unfamiliar is in this repo

```bash
grep -rn "AIQ-1631" backend/main.py
#   backend/main.py:9791: # [AIQ-1631] The matrix bridge returns benefits keyed by their config-matrix...

grep -rn "_seed_default_published_policy" backend/app/routers/test_drive.py
#   :210 (definition)   :313 (call site)

git log --oneline --all | grep -E "AIQ-163[1-6]"
#   c765c4d2 fix(policy): [AIQ-1631/1635/1636] make config-matrix policy cap reachable...
#   bef49ab7 fix(policy): [AIQ-1635] cover host_housing_cap in the default seed...
#   03d4b18e fix(policy): [AIQ-1631] alias config-matrix benefits in the live employee resolver path
```

`resolved_assignment_policies` is a table in the ReloPass Supabase project (`nsvefcvpvwwwhuqyuqmp`). The `uuid NOT NULL` / FK finding came from querying that database directly:

```
policy_id          uuid NOT NULL   FK → company_policies(id)
policy_version_id  uuid NOT NULL   FK → policy_versions(id)
```

"Policies" = **relocation benefits policies** (housing caps, shipment allowances) that HR publishes and the employee's Services page compares against. Not Audos workspace policies.

---

## 3. What still needs doing — unchanged

Full brief: `docs/audos-prompt-p0-1-followup.md`. Summary:

**Two hard gates — report a recommendation and WAIT for approval, do not implement:**

1. **AIQ-1631 reconciliation.** Your `shared/service_benefit_taxonomy.json` pushes the canonical vocabulary one way; AIQ-1631 (`main.py:9791`, already on `main`) aliases matrix benefits the other way. Which wins, what gets deleted, does `fix/f14-shared-taxonomy` need amending before merge?

2. **Persistence design.** Your matrix branch writes `policy_id = 'policy_config_matrix:<vid>'` into a **`uuid NOT NULL`** column. That fails on the type cast, before the FK is even checked — so FK relaxation alone does not fix it. Assess three options and recommend one:
   - **A** — relax FKs + widen columns to `text`. Weakens integrity for real customers too.
   - **B** — shadow `company_policies` / `policy_versions` rows. No migration, but writes synthetic rows other consumers treat as real.
   - **C (recommended)** — make `policy_id` / `policy_version_id` nullable, add `policy_config_version_id uuid` FK → `policy_config_versions`, plus a CHECK that exactly one source is set. Honest polymorphism, no weakened constraints.

   Any migration is 🔴 Red: commit the file only, never apply it, never touch `supabase_migrations.schema_migrations`.

**Proceed without approval (no schema change, 77% of the population):**

3. **Seed intermittency.** You concluded the seed works from **one** session. Production says otherwise — 07-19: 47 test companies, 11 with a published policy (23%); 07-18: 45 / 4 (9%). Provision **5** fresh sessions on `?campaign=qa-p0-1&corridor=FR_NO`, report `n/5`, and capture the actual exception when it fails.

**Also:** `frontend/src/api/client.ts` and `frontend/src/pages/ProvidersPage.tsx` are in commit `3f9ed63a` with no apparent link to policy resolution. Justify or split them out.

---

## 4. Separate question — Task #84515 (Stripe signature verification)

Before this is reviewed: **what file path did it write to?**

A search of `backend/app/`, `backend/main.py` and `frontend/src/` finds **no Stripe code at all** — the only match in the whole application is a CSS comment describing a design as "Stripe-inspired". Every Stripe commit in the last three days touches `docs/` only, and `docs/stripe-relopass-package/03-backend/webhook-extension.ts` is **TypeScript sitting in a Python FastAPI backend, imported by nothing**.

Signature verification that is not wired to a live endpoint provides zero protection. Please confirm one of:

- the exact path(s) written, and whether they are inside `backend/app/` or `backend/`;
- the route the webhook is served on, and that it is registered in **both** `backend/main.py` and `backend/app/main.py` (Render boots `uvicorn backend.main:app` — registering only in the modular app returns 405 in production);
- or that #84515 produced a **spec artifact only**, in which case say so plainly and it will be tracked as spec, not as shipped.

Verification command:
```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'stripe' in r.path or 'payment' in r.path or 'webhook' in r.path))"
```
If that prints an empty list, the webhook is not live.

---

## 5. Reporting

Your last two chat reports contained only the repo name and prior commit hash — no branch, no SHA, no measurements. The work was good; the report made it look like nothing happened. Every report needs: branch, commit SHA, what changed, what you measured (raw output), and what is blocked.
