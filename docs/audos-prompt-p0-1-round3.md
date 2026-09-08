# Audos task brief — P0-1 round 3: corrected scope + approved execution

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec`
**Under review:** `3f9ed63a` on `audit/stage-p0-1-eager-policy-resolution` · **Also open:** `121403c8` on `fix/f14-shared-taxonomy`
**Supersedes:** `docs/audos-prompt-p0-1-followup.md` §2 and §6.3. Everything else in that brief stands.

Your proposed executor split is approved: **Cursor** for code, recommendations and prod SQL; **you** for the browser measurements. Both tracks are green-lit, with the corrections below.

---

## 0. Correction — the "seed is 77% broken" claim is RETRACTED

The prior brief told you the seed was failing for 77% of test-drive companies and that your n=1 conclusion was wrong. **That figure was computed on a bad denominator and should not be used.**

It counted all `is_test = true` companies. Most of those are not test-drive provisioned at all:

| Last 3 days | Count |
|---|---|
| Rows in `test_sessions` | **15** |
| `is_test = true` companies | **92** |
| Companies with a published policy | **15** |

Roughly 77 of those 92 companies come from automated tests and E2E runs, which never seed a policy by design. Counting them as seed failures was the error. And 15 sessions against 15 published policies points toward the seed working — i.e. **your original n=1 finding may have been correct.**

It is not yet proven either way, because the linkage cannot currently be verified (see §3.1). So the seed question is **open, not closed** — and §2.1 below is now the measurement that decides it.

**Do not spend effort defending or attacking the 77% number. It is withdrawn.**

---

## 1. Track A — Cursor (recommend only; do not implement)

Both items below are **hard gates**. Produce a written recommendation and stop. No migration file, no persistence code, no schema change.

### 1.1 Step 0 — AIQ-1631 reconciliation

There are now **four** overlapping attempts at this defect. Three are already on `main`:

```
c765c4d2  [AIQ-1631/1635/1636] make config-matrix policy cap reachable on default test-drive path (#1567)
bef49ab7  [AIQ-1635] cover host_housing_cap in the default seed so over-cap is reachable
03d4b18e  [AIQ-1631] alias config-matrix benefits in the live employee resolver path
38e53704  [AIQ-1631] resolve config-matrix policies for employees (has_policy gate)
```

The fourth is your `fix/f14-shared-taxonomy`, which pushes the canonical vocabulary in the **opposite** direction to AIQ-1631's runtime aliasing at `backend/main.py:9791`.

**Deliver:** which direction wins · what gets deleted · whether `121403c8` needs amending before merge · what breaks if both remain. **Then stop.**

### 1.2 Persistence design decision

`3f9ed63a` writes `policy_id = 'policy_config_matrix:<vid>'` into a column verified in production as:

```
policy_id          uuid NOT NULL   FK → company_policies(id)   ON DELETE CASCADE
policy_version_id  uuid NOT NULL   FK → policy_versions(id)    ON DELETE CASCADE
assignment_id      text NOT NULL   UNIQUE
case_id            text NULL
```

A string containing a colon cannot be written to a `uuid` column — it fails at the cast, before the FK is evaluated. **Relaxing the foreign keys alone does not fix this.**

Assess all three and recommend one with reasoning:

- **A** — relax FKs, widen `policy_id` / `policy_version_id` to `text`. Weakens integrity for every row, including real customers'.
- **B** — write shadow `company_policies` + `policy_versions` rows. No migration, FKs intact, but inserts synthetic rows that every other consumer of those tables treats as real.
- **C (Romain's preference)** — make `policy_id` / `policy_version_id` nullable, add `policy_config_version_id uuid` with FK → `policy_config_versions`, plus a CHECK enforcing exactly one populated source. Honest polymorphism; the table genuinely has two policy sources now.

**Constraints:** any migration is 🔴 Red — commit the file only, never apply it, never write to `supabase_migrations.schema_migrations`. Idempotent DDL. Existing rows and real-customer resolution must not regress. **Then stop.**

### 1.3 Scope justification

`frontend/src/api/client.ts` and `frontend/src/pages/ProvidersPage.tsx` are in `3f9ed63a` with no apparent link to policy resolution. Justify or split them out.

### 1.4 Prod SQL (if DB access is available)

```sql
WITH pub AS (
  SELECT pc.company_id::text AS cid
  FROM policy_configs pc
  JOIN policy_config_versions pcv ON pcv.policy_config_id::text = pc.id::text
  WHERE pcv.status='published' GROUP BY 1
)
SELECT co.is_test,
       count(*)                                    AS cases,
       count(*) FILTER (WHERE pub.cid IS NOT NULL) AS company_has_published_policy,
       count(rap.id)                               AS cases_with_resolution
FROM relocation_cases rc
JOIN companies co ON co.id::text = rc.company_id::text
LEFT JOIN pub ON pub.cid = co.id::text
LEFT JOIN resolved_assignment_policies rap ON rap.case_id::text = rc.id::text
WHERE rc.created_at::timestamptz > now() - interval '2 days'
GROUP BY co.is_test;
```

Real-customer baseline must not regress: currently **3 of 21** cases resolved.

---

## 2. Track B — Audos browser (proceed now, no approval needed)

### 2.1 Seed success rate — this is the decisive measurement

**Goal:** establish the true rate. Not to confirm a failure — the 77% claim is withdrawn and your n=1 may have been right. This settles it.

**Protocol.**
1. Provision **5** fresh test-drive sessions, each in a clean browser context, at:
   `https://relopass.com/test-drive?campaign=qa-p0-1&corridor=FR_NO`
2. Record the first name label used for each, so the sessions are identifiable.
3. For each, determine whether the company ended up with a **published** policy-config version.
4. Report **n/5**, not a narrative.

**Interpretation — state which applies:**
- **5/5** → the seed is healthy. Close the seed line of investigation. The persistence design (§1.2) becomes the entire critical path.
- **0–4/5** → the seed is intermittent. Capture the **actual exception** from the swallow at `backend/app/routers/test_drive.py:229–232` and report the real error text. Do not guess at the cause.

**Cleanup:** report every `qa-p0-1` artifact created so it can be purged. Never use `insead-2026`.

### 2.2 RUN 003 Segment B step B16 — record as a PRE-MERGE BASELINE only

**Important correction.** `3f9ed63a` is on a branch. `main` is at `1f2e4593`. **None of the eager hook, structured error events, or the `policy_unavailable` state is deployed to production.**

So B16 against prod measures the *old* behaviour and will almost certainly show "No policy rule for this category". **That is the expected baseline — it is NOT a failure of the new work, and must not be reported as one.**

Record: which of the three states the Housing card shows — a real cap comparison / "No policy rule for this category" / "Policy comparison unavailable". Label it `PRE-MERGE BASELINE (main @ 1f2e4593)`. B16 becomes a real verification only after the persistence design is approved, implemented and merged.

---

## 3. Side findings worth a line each

### 3.1 `test_sessions` cannot be joined to companies
`test_sessions.hr_user_id` produces **zero** matches against `profiles.id`, so there is no working path from a test-drive session to the company it provisioned. This is why the seed rate could not be verified from data and why §2.1 has to be measured by hand.

Worth a small investigation: is `hr_user_id` referencing Supabase auth UUIDs while `profiles.id` uses a different key? If so, session-level analytics (including tester segment attribution) are unreliable for the same reason.

### 3.2 Repo hygiene
There are ~20 identical commits titled `docs: add Stripe integration spec package for ReloPass Case Command` within two minutes on 07-19. Worth squashing.

---

## 4. Task #84515 — Stripe signature verification: answer before review

A search of `backend/app/`, `backend/main.py` and `frontend/src/` finds **no Stripe code**. The only match in the entire application is a CSS comment describing a design as "Stripe-inspired". Every Stripe commit in the last three days touches `docs/` only, and `docs/stripe-relopass-package/03-backend/webhook-extension.ts` is TypeScript in a Python FastAPI backend, imported by nothing.

Confirm exactly one:
- the **file path(s)** written, and whether they sit inside `backend/`; **or**
- that #84515 produced a **spec artifact only** — in which case say so plainly and it will be tracked as spec, not as shipped.

If a route was added, it must be registered in **both** `backend/main.py` and `backend/app/main.py` (Render boots `uvicorn backend.main:app`; registering only in the modular app returns 405 in production). Verify with:

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if any(k in r.path for k in ('stripe','payment','webhook'))))"
```

An empty list means the webhook is not live. **Signature verification that is not wired to a live endpoint provides no protection**, so this will not be approved as security work until the path is confirmed.

---

## 5. Report format

```
TRACK A — Cursor (recommend only)
  Step 0 / AIQ-1631: direction ____ | delete ____ | amend 121403c8? ____
  Persistence: recommended ____ because ____ | migration needed? ____
  Scope (client.ts, ProvidersPage.tsx): ____
  SQL output: [paste raw]  | real-customer baseline (was 3/21): ____
  [STOPPED — awaiting approval on both gates]

TRACK B — browser
  Seed rate: ___/5   Campaign: qa-p0-1   Corridor: FR_NO
  If <5/5 — actual exception text: ____
  RUN 003 B16 [PRE-MERGE BASELINE, main @ 1f2e4593]: ____
  Artifacts to purge: ____

TASK #84515
  File path(s): ____ | Route live? ____ | Spec-only? ____

BLOCKED / NOT DONE: ____
```

**Sequencing:** Track B starts immediately. Track A stops at both gates and waits. Nothing implements the persistence fix until Romain approves an option.
