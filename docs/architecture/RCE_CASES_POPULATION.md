# Why `rce.cases` stopped being written, and whether case creation should write one

**AIQ-1780 · investigation, 2026-08-10 · no code or schema changed by this task**

## TL;DR

1. **The writer is `corridor_persistence.persist_corridor_case()`** (`backend/app/services/corridor_persistence.py:277`). Its only non-test callers are two **manual CLI scripts**. Nothing — no router, service, cron, or GitHub workflow — calls it automatically. The 27 rows are the residue of hand-run `--apply` invocations on 2026-06-29/30.
2. **The path is alive, not dead** — it imports and resolves pathways correctly on `main` today. It simply has no trigger.
3. **But populating `rce.cases` would not unblock document extraction**, which is what AIQ-1766/1767/1768 actually need. The blocker is not the one the task assumed. There is a **fourth** case table, `public.mobility_cases` (1,766 rows, written today), whose id-space is **disjoint from all three others**, and that is where uploaded documents attach.

The recommendation is therefore *not* "wire case creation to `rce.cases`". See [Recommendation](#recommendation).

---

## Q1 — What wrote the 27 rows?

**Named:** `persist_corridor_case()` — `backend/app/services/corridor_persistence.py:277`, the only `INSERT INTO rce.cases` in application code.

Its callers, exhaustively (`grep persist_corridor_case backend/`):

| Caller | Kind | Automated? |
|---|---|---|
| `backend/scripts/populate_rce_from_cases.py:114` (`populate_rce_for_public_case`) | manual CLI, `--dry-run` default | **No** |
| `backend/scripts/seed_corridor_case.py:36` | manual demo seed | **No** |
| `backend/tests/test_populate_rce_from_cases.py` | test | n/a |

`grep` over `.github/`, `render.yaml`, and `backend/app/` finds **no** reference to either script. There is no cron, no create-hook, no request path.

The script arrived in **PR #1186 / commit `60523281`, merged 2026-06-29** (AIQ-941, *"populate rce engine from real public cases (unify the id-space)"*). Its own commit message names the gap it left open:

> Reusable `populate_rce_for_public_case()` (**for a future cron/create-hook**).

That future hook was never built. The write pattern in prod matches exactly:

| corridor | rows | first | last |
|---|---|---|---|
| `FR_DE_EU_2026` | 13 | 2026-06-29 | 2026-06-30 |
| `IN_DE_BLUECARD_2026` | 7 | 2026-06-04 | 2026-06-29 |
| `FR_NL_2026` | 2 | 2026-06-30 | 2026-06-30 |
| `FR_NO`, `FR_CH`, `DE_NO`, `ES_NL`, `FR_ES` | 1 each | 2026-06-30 | 2026-06-30 |

Two bursts on 29–30 June (the `--apply` runs, the day the PR merged), plus a 2026-06-04 tail that predates it — the earlier `seed_corridor_case.py` demo seed. **Answer: a one-off manual backfill, exactly as the task hypothesised.**

## Q2 — Is that path still reachable on `main`?

**Yes.** Verified by execution, not inspection:

```
backend/scripts/populate_rce_from_cases.py     present on origin/main
module imports on main: OK
  IN      ->DE       corridor=IN_DE   pathway=BLUECARD_2026     loadable=True
  FRANCE  ->GERMANY  corridor=FR_DE   pathway=EU_FREEDOM_2026   loadable=True
  FR      ->NO       corridor=FR_NO   pathway=EEA_FREEDOM_2026  loadable=True
  US      ->JP       corridor=US_JP   pathway=None              loadable=False
```

It is idempotent (`persist_corridor_case` upserts `ON CONFLICT`) and already normalises country names → ISO-2, so the `'France'`-style rows tracked by AIQ-1778 resolve here. Re-running `--apply` today would write:

| | cases |
|---|---|
| `public.cases` total (all eligible status) | 281 |
| eligible **and** corridor-covered | 251 |
| already in `rce.cases` | 24 |
| **would be added** | **227** |
| eligible but no pathway YAML → skipped | 30 |

So one command would take `rce.cases` from 27 → 251. **It is not dead, superseded, or broken. It is unscheduled.**

---

## The finding the task did not anticipate: it is a *four*-table split

The task frames a three-table split (`public.cases` 272 / `relocation_cases` 935 / `rce.cases` 27). Measured today there is a fourth, and it changes the conclusion.

| table | rows | last write | id-space |
|---|---|---|---|
| `public.mobility_cases` | **1,766** | **today** | **disjoint from all three below** |
| `public.relocation_cases` | 960 | today | shares ids with `public.cases` |
| `public.cases` | 281 | today | 280 of 281 ids also in `relocation_cases` |
| `rce.cases` | 27 | 2026-06-30 | `case_id` == `public.cases.id` (AIQ-941) |

Overlap of `mobility_cases` with `public.cases`, `relocation_cases`, and `rce.cases`: **0, 0, and 0.**

So the "schism" is really two things, and only one is a problem:

* **`relocation_cases` / `public.cases` / `rce.cases` already share one id-space.** AIQ-941 made `rce.cases.case_id == public.cases.id`, and 280/281 `public.cases` ids are also `relocation_cases` ids. Nothing to reconcile here.
* **`mobility_cases` is a separate universe** — the largest case table, actively written, sharing ids with nothing.

### Why that sinks the obvious fix

All 6 rows in `public.case_documents` (5 distinct cases, last upload 2026-07-15) carry `case_id` values that exist in **`mobility_cases` only** — not in `public.cases`, not in `relocation_cases`, not in `rce.cases`.

`rce.cases` is populated *from `public.cases`*. Documents attach *to `mobility_cases`*. **Populating `rce.cases` with all 227 missing `public.cases` rows would not let a single existing or future `mobility_cases` upload cross the bridge**, because `_case_exists()` is looking in a table those ids will never appear in.

### There are also two upload paths, and only the unused one is wired to rce

| path | writes | calls the bridge? | rows in prod |
|---|---|---|---|
| `POST /api/immigration/cases/{id}/documents` → `document_upload_service.py:98` | `immigration_documents` | **yes** (`bridge_case_document_to_rce`) | **0, ever** |
| `POST /api/cases/{id}/documents` → `passport_case_document_sync_service.py:265` | `case_documents` | **no** | 6 |

Both have live frontend callers (`frontend/src/api/immigrationDocuments.ts` and `frontend/src/api/documents.ts`). The bridge-wired endpoint has never received a single upload; the endpoint that has real documents never calls the bridge.

**So `rce.documents = 0` has two independent causes, and the missing `rce.cases` row is only the second one.** Even with `rce.cases` fully populated, extraction stays at zero until uploads flow through the bridged path with an id the bridge can resolve.

---

## Recommendation

**Do not wire case creation to `rce.cases` yet.** It would be a real change addressing the *lesser* of two blockers, and it would harden the `public.cases`-centric assumption at the moment that assumption looks wrong.

Proposed order — the first step is free and reversible, the rest need your call:

**1. Re-run the existing backfill (no code, ~1 command).**
`python -m backend.scripts.populate_rce_from_cases --apply`. Idempotent, +227 rows, restores the AIQ-693 "rule changed → employee banner" flow that `active_case_finder` (`rce.rule_citations ⨝ rce.cases`) depends on — which is what AIQ-941 built this for in the first place. That flow, not extraction, is the honest justification. **This is a prod data write, so it is your call, not mine** — the task is investigation-only and I have not run it.

**2. Answer the prior question: which table is *the* case?**
`mobility_cases` (1,766) vs `relocation_cases` (960) vs `public.cases` (281), all three written today, is the actual architectural debt. Extraction, prefill and the rules engine each picked a different one. Until that is settled, any hook we add binds us harder to whichever table we happen to choose.

**3. Then, and only then, choose a trigger.** If the answer to (2) keeps `public.cases`, prefer a **nightly cron** over a create-hook: corridor coverage is partial (30 eligible cases have no pathway YAML today), so a cron naturally picks cases up as new pathway YAMLs land, whereas a create-hook must fail-soft on every uncovered corridor and never retries.

I'd suggest filing (2) as its own task before any implementation task for (1) or (3).

---

## What AIQ-1766 / 1767 / 1768 actually run against

Per this task's Expected Output, since the recommendation is **not** an immediate "yes, wire it":

Today those agents run against **nothing**, and re-running the backfill would not change that. `rce.agent_runs = 0` and `rce.extracted_fields = 0` — across all eleven registered extraction agents, no agent has ever executed in production.

That is not an argument against having built them: they are unit-tested against fixtures and the wiring is guarded by `test_extraction_agent_wiring`. But their acceptance criteria can only ever be *fixture-level* until the upload-path/id-space question above is resolved. **AIQ-1767 (PAYSLIP) and AIQ-1768 (classifier) should be scoped and reviewed on that basis** — as fixture-validated components, not as features with observable production behaviour.

---

## Appendix — measurements (prod `nsvefcvpvwwwhuqyuqmp`, 2026-08-10)

```
rce.cases              27      last 2026-06-30    (8 corridors, first 2026-06-04)
rce.documents           0      never
rce.agent_runs          0      never
rce.extracted_fields    0      never

public.cases          281      last 2026-08-10
public.relocation_cases 960    last 2026-08-10
public.mobility_cases 1766     last 2026-08-10    overlap with the other 3: 0 / 0 / 0

public.immigration_documents  0    (bridge-wired path)
public.case_documents         6    last 2026-07-15, 5 distinct case_ids, all mobility_cases
```

Validation criteria: (1) writer named with file+function ✅ · (2) reachability stated with executed evidence ✅ · (3) recommendation addresses the table split — and corrects it from three tables to four ✅ · (4) no schema change, no bridge code, no case-creation change written ✅
