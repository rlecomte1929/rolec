# Why `rce.cases` stopped being written, and whether case creation should write one

**AIQ-1780 · investigation, 2026-08-10 · no code or schema changed by this task**

## TL;DR

1. **The writer is `corridor_persistence.persist_corridor_case()`** (`backend/app/services/corridor_persistence.py:277`). Its only non-test callers are two **manual CLI scripts**. Nothing — no router, service, cron, or GitHub workflow — calls it automatically. The 27 rows are the residue of hand-run `--apply` invocations on 2026-06-29/30.
2. **The path is alive, not dead** — it imports and resolves pathways correctly on `main` today. It simply has no trigger.
3. **But populating `rce.cases` alone would not unblock document extraction**, which is what AIQ-1766/1767/1768 actually need. Uploaded documents attach to `public.mobility_cases` (1,766 rows, written today), which shares **no primary key** with the other case tables — and the upload path that users actually reach never calls the rce bridge at all.

The recommendation is therefore *not* "wire case creation to `rce.cases`". See [Recommendation](#recommendation).

> **Revision, 2026-08-10 (same day).** An earlier version of this document called `mobility_cases`
> "a fourth case table … disjoint from all three others" and left it there. Two corrections, both
> material:
>
> * **`mobility_cases` is not a fourth *case*.** It is a **per-assignment graph anchor** — one row per
>   `case_assignments` row, minted with a fresh `uuid4()`, carrying no business data beyond
>   company/employee/countries. It exists so `case_people`, `case_documents` and
>   `case_requirement_evaluations` have something to FK to.
> * **"No PK overlap" is not "unjoinable".** `assignment_mobility_links` is a **1:1 bridge**
>   (`UNIQUE` on both `assignment_id` and `mobility_case_id`) from `case_assignments` to
>   `mobility_cases`. Every id-space here is reachable from every other.
>
> The operative conclusion survives unchanged, and is now sharper: there is still **no path from
> `mobility_cases` to `public.cases`**, so a bridge call on the reachable upload path must supply the
> canonical case id explicitly. See [The case model](#the-case-model-two-grains-three-projections).

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

## The case model: two grains, three projections

The task frames a three-table split (`public.cases` 272 / `relocation_cases` 935 / `rce.cases` 27) and
asks which is canonical. That question has now been asked three times — `docs/audits/case-bridge-plan.md`
(2026-06-14), `docs/architecture/CASE_ID_UNIFICATION_AUDIT.md` (07-27), and this document — and answered
zero times. **The measurements say it is the wrong question.** These tables are not rival candidates for
"the case"; they are two different grains, plus projections:

| grain | table | rows | last write | role |
|---|---|---|---|---|
| **case** | `public.relocation_cases` | 960 | today | The HR record. `POST /api/hr/cases` creates it. |
| **case** | `public.cases` | 281 | today | Engine projection, **same id**. Read by the trigger engine, forms, dossier, roadmap. |
| **case** | `rce.cases` | 27 | 2026-06-30 | Corridor projection, **same id** (AIQ-941). Unscheduled. |
| **assignment** | `public.case_assignments` | 600 | today | employee ↔ case. Its three id forms were unified by AIQ-1704 `resolve_case_ids`. |
| **assignment** | `public.mobility_cases` | 1,766 | today | Per-assignment **graph anchor** for `case_people` / `case_documents` / `case_requirement_evaluations`. |

### The 960 → 281 "gap" is junk data, not a broken bridge

`_ensure_canonical_case_from_wizard` (`backend/db/cases.py:3054`) projects `relocation_cases` → `public.cases`
using the same id, and deliberately skips any row that cannot satisfy the target's NOT NULL/FK constraints
("never insert a partial/invalid row"). Of the 680 rows it skips:

| reason | rows |
|---|---|
| **no `employee_id`** | **679** |
| no origin/destination country | 640 |
| `company_id` absent from `public.companies` | 79 |
| **fully satisfiable today** | **1** |

These are HR-created shells that were never assigned to anyone — exactly what
`20261008000000_public_cases_backfill_followup.sql` predicted ("incomplete pre-launch test data …
resolve naturally once the data is completed"). **`public.cases` is not an incomplete projection; it is
the set of cases that are actually real.** There is nothing to consolidate and no FK epic to run here.

### `mobility_cases` is joinable — through `assignment_mobility_links`

It shares no primary key with the case tables because each row is minted with a fresh `uuid4()` per
assignment (`assignment_mobility_link_service.py:125`). But it is **not** a separate universe:

```
mobility_cases.id  ←1:1→  assignment_mobility_links  ←1:1→  case_assignments.id
                                                              ↓ canonical_case_id
                                            relocation_cases.id ⊇ public.cases.id = rce.cases.case_id
```

Both link columns are `UNIQUE`, so the traversal is exact in either direction (`backend/db/cases.py:1183`,
`:1206`). Every id-space is reachable from every other. Mind the type mismatch: `mobility_cases.id` is
`uuid`, `case_assignments.id` and `relocation_cases.id` are `text` — an uncast join already 500'd
`exception_requests.py` once.

### Why the obvious fix is still not enough

All 6 rows in `public.case_documents` (5 distinct cases, last upload 2026-07-15) carry `case_id` values
that are **`mobility_cases` ids**. Walking the chain above resolves **3 of the 6 documents** to a real
`relocation_cases`/`public.cases` row — 2 of those 3 land on a case that already has an `rce.cases` row.
The other 3 have no `assignment_mobility_links` row at all and dead-end.

`rce.cases` is keyed on the **case** id. Documents attach at the **assignment** grain. So
**populating `rce.cases` with all 227 missing rows would not, on its own, let one upload cross the
bridge** — `_case_exists()` receives a `mobility_cases` id, and there is no FK path from
`mobility_cases` to `public.cases`. The bridge call has to be handed the canonical case id explicitly.

### There are also two upload paths, and only the unused one is wired to rce

| path | writes | calls the bridge? | rows in prod |
|---|---|---|---|
| `POST /api/immigration/cases/{id}/documents` → `document_upload_service.py:98` | `immigration_documents` | **yes** (`bridge_case_document_to_rce`) | **0, ever** |
| `POST /api/cases/{id}/documents` → `passport_case_document_sync_service.py:265` | `case_documents` | **no** | 6 |

Both have live frontend callers (`frontend/src/api/immigrationDocuments.ts` and `frontend/src/api/documents.ts`). The bridge-wired endpoint has never received a single upload; the endpoint that has real documents never calls the bridge.

**So `rce.documents = 0` has two independent causes, and the missing `rce.cases` row is only the second one.** Even with `rce.cases` fully populated, extraction stays at zero until uploads flow through the bridged path with an id the bridge can resolve.

---

## Recommendation

**Do not wire case creation to `rce.cases`.** A create-hook addresses the *lesser* of the two blockers,
and on its own it would still leave extraction at zero.

**Do not run another "which table is canonical" investigation either.** That question has been asked
three times and is answered above: two grains, three projections, and the 960 → 281 gap is shell data.
No consolidation epic is required.

Proposed order — step 1 is free and reversible, step 2 needs your approval:

**1. Bridge the upload path users actually reach (small code change).**
Call `bridge_case_document_to_rce` from `backend/app/routers/case_documents.py` after
`insert_case_evidence`, passing `_effective_case_id(assignment, case_id)` — the canonical case id, **not**
the `mobility_case_id` used two lines later for the `case_documents` index. Mirror
`immigration_documents.py:111-123`: the bridge is already fail-soft, and `process_rce_document` runs in
the background so the upload response is unaffected. A regression test must assert *which id* is passed;
that single argument is the whole fix.

**2. Re-run the existing backfill (no code, ~1 command).**
`python -m backend.scripts.populate_rce_from_cases --apply`. Idempotent, +227 rows. It also restores the
AIQ-693 "rule changed → employee banner" flow that `active_case_finder` (`rce.rule_citations ⨝ rce.cases`)
depends on — which is what AIQ-941 built it for. **A prod data write, so it is your call** — this task is
investigation-only and I have not run it.

**3. Only then consider a trigger.** With (1) and (2) done, a create-hook is optional convenience rather
than a blocker. If one is added, prefer a **nightly cron**: corridor coverage is partial (30 eligible
cases have no pathway YAML today), so a cron picks cases up as new YAMLs land, whereas a create-hook must
fail-soft on every uncovered corridor and never retries.

Steps 1–3 are specified in full in the follow-on implementation plan; this document is the evidence
behind them.

---

## What AIQ-1766 / 1767 / 1768 actually run against

Per this task's Expected Output, since the recommendation is **not** an immediate "yes, wire it":

Today those agents run against **nothing**. `rce.agent_runs = 0` and `rce.extracted_fields = 0` — across
all eleven registered extraction agents, no agent has ever executed in production, and re-running the
backfill alone would not change that.

That is not an argument against having built them: they are unit-tested against fixtures and the wiring
is guarded by `test_extraction_agent_wiring`. But **until steps 1 and 2 above both land, their acceptance
criteria can only be fixture-level.** AIQ-1767 (PAYSLIP) and AIQ-1768 (classifier) should be scoped and
reviewed on that basis — as fixture-validated components, not as features with observable production
behaviour.

Once steps 1 and 2 land, the honest success metric for this whole thread is a single number moving off
zero: `SELECT count(*) FROM rce.agent_runs`. Expect the first real run to surface OCR/prompt issues that
fixture tests structurally cannot catch — that is the point of running it, not a reason to defer it.

---

## Appendix — measurements (prod `nsvefcvpvwwwhuqyuqmp`, 2026-08-10)

```
rce.cases              27      last 2026-06-30    (8 corridors, first 2026-06-04)
rce.documents           0      never
rce.agent_runs          0      never
rce.extracted_fields    0      never

public.cases          281      last 2026-08-10    (280 of 281 ids also in relocation_cases)
public.relocation_cases 960    last 2026-08-10    (680 unprojected: 679 have no employee_id,
                                                   640 no countries, 1 satisfiable today)
public.case_assignments 600    last 2026-08-10    (280 resolve to a public.cases row;
                                                   24 of those have an rce.cases row)
public.mobility_cases 1766     last 2026-08-10    no PK overlap, but 1:1-joinable via
                                                  assignment_mobility_links (573 links;
                                                  1193 mobility rows have no link)

public.immigration_documents  0    (bridge-wired path, never used)
public.case_documents         6    last 2026-07-15, 5 distinct case_ids, all mobility_cases ids
                                   (3 of 6 walk the link chain to a real case — 2 of those to a
                                    case that already has an rce.cases row; 3 dead-end, no link row)
```

Extraction-eligible population: **280 assignments**, of which **24** have an `rce.cases` row today.

Validation criteria: (1) writer named with file+function ✅ · (2) reachability stated with executed evidence ✅ · (3) recommendation addresses the table split — and replaces "which is canonical?" with a measured grain model ✅ · (4) no schema change, no bridge code, no case-creation change written ✅
