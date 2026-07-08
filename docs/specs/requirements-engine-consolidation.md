# Requirements Engine Consolidation — Design Decision (AIQ-1473a)

**Status:** Proposed — awaiting reviewer sign-off before any code (parent AIQ-1473:
"Design decision required BEFORE code — do not merge blindly").
**Author:** relopass-dev-queue, 2026-07-08.
**Parent:** AIQ-1473 — Consolidate the two requirements engines.
**Downstream (blocked on this):** AIQ-1473b (shared key resolver), 1473c
(reconciliation), 1473d (consumer wiring), 1473e (parity test).

---

## 1. Problem statement (and a correction to the framing)

The parent frames this as *"requirements shown to HR vs fetched into the
employee/profile don't match."* Reading the code, the split is **not** cleanly
"HR uses engine X, employee uses engine Y." It is two engines that answer two
**different questions**, one of which (immigration) both personas already share:

- **Path A — the immigration document checklist** is already shared across
  personas. HR reads it (`immigration_intake_consent.py:143`) and the **employee**
  reads the *same* engine via `immigration_snapshot_service.build_immigration_snapshot`
  — whose docstring states it "Reuses the exact same engine the HR panel uses so
  the employee sees the same risks."
- **Path B — the relocation dossier** is employee-only and covers *all* pillars
  (immigration, housing, banking, …), not just immigration.

The true divergence: **Path A's corridor×visa immigration checklist** and
**Path B's destination-keyed immigration pillar** are two independent computations
of "what immigration documents does this case need," keyed differently, that can
disagree for the same case — and B can silently return **zero** items when the
destination key fails to resolve (AIQ-1349). That is the bug class to eliminate.

---

## 2. Current state — the two paths

| | **Path A — Immigration checklist** | **Path B — Relocation dossier** |
|---|---|---|
| Entry point | `immigration_requirement_service.get_requirements(corridor_from, corridor_to, visa_type, employee_type, employee_profile)` | `requirements_builder.compute_case_requirements(case_id)` |
| Backing table | `public.immigration_requirements` | `requirement_items` (+ `sources`) |
| DB layer | **Legacy raw** — `from ...database import db`, `db.engine.begin()` + `text()` SQL | **Modular ORM** — `app/db.SessionLocal` + `crud.list_requirements()` |
| Key | `corridor_from × corridor_to × visa_type × employee_type` (origin **and** destination; corridor codes `.upper()`-ed, visa `.lower()`-ed in SQL) | `dest_country × purpose` (**destination only**; dest resolved ISO→full-name via `_resolve_catalog_country`) |
| Scope | Immigration/visa documents only | **All pillars** — the `pillar` field spans immigration, housing, banking, etc. |
| Returns | `List[RequirementResult]` — per-document: apostille, translation, freshness, processing days, book-early, form url + `evaluate_risks()` risk flags | `CaseRequirementsDTO` — items by pillar with `requiredFields`, `statusForCase` (MISSING/PROVIDED), citations/sources, STA-waived logic, disclaimer |
| Conditional logic | `evaluate_condition()` per-row against employee profile | `rules_engine.apply_rules()` against the case draft |
| Fail-closed? | **Yes** — unseeded corridor → callers return `covered=false` | **No** — unresolved dest key → **empty list** that reads as "nothing required" (the AIQ-1349 silent-miss) |
| Consumers | HR `GET /hr/cases/{id}/immigration-requirements` (`immigration_intake_consent.py:143`); employee `immigration_snapshot_service.py:58` | Employee dossier: `cases_read.py:936` + `:1115`, `cases_write.py:292`; **`cases.py:225` is the dead router** (see `reference_cases_router_dead_code`) |

**Two hard constraints these keys create:**
1. **Different DB layers.** A is on the legacy raw layer, B on the modular ORM. The
   root `CLAUDE.md` forbids mixing them in one module. Any shared code must not
   straddle both — it can only share *pure* logic (e.g. key normalization), not
   sessions/engines.
2. **Different key granularity.** A is corridor-aware (origin matters: FR→DE ≠
   NL→DE) and visa-type-aware. B is destination-only. They are **not**
   substitutable — you cannot answer A's question from B's table or vice-versa.

---

## 3. Overlap analysis

- **Immigration is the only overlap.** Path A is entirely immigration. Path B has
  an *immigration pillar* among several. Housing/banking/etc. in B have **no**
  counterpart in A.
- **Where they can disagree:** for the same case, A's corridor×visa checklist and
  B's immigration-pillar items are computed independently, from different tables,
  with different keys and different conditional engines. Nothing keeps them
  consistent today.
- **The silent-zero fault is B-only:** A fails closed (`covered=false`); B returns
  an empty list on an unresolved destination key. So a case can show a rich HR
  immigration checklist (A) and an empty/short employee dossier immigration
  section (B) — exactly the reported mismatch.

**Conclusion:** A and B are **distinct by design** (corridor/visa visa-doc
checklist vs destination multi-pillar dossier). A full merge would conflate two
genuinely different data models and two DB layers. The fix is a **documented
boundary** plus removing the two concrete inconsistency sources.

---

## 4. Options considered

### Option 1 — Unify behind a single service
Collapse A and B into one requirements service/facade with one backing store.

- **Pros:** one code path; structurally impossible to diverge.
- **Cons:** A is corridor+visa keyed on the legacy layer; B is destination keyed on
  the ORM layer with multi-pillar status tracking. Unifying means a **schema
  migration merging two differently-keyed tables**, rewriting both conditional
  engines (`evaluate_condition` vs `rules_engine.apply_rules`), and touching every
  consumer — across **both DB layers**, which `CLAUDE.md` says not to mix. High
  blast radius, high regression risk on both personas, for a pre-launch platform.
  Most of B (housing/banking/…) has nothing to unify with A.

### Option 2 — Explicit documented boundary + reconcile the immigration overlap (recommended)
Keep A and B as separate services with a **written contract**, and remove the two
things that actually cause user-visible mismatch:

1. **Ownership rule (documented):** A owns the *immigration document checklist*
   (corridor×visa, origin-aware, risk flags). B owns the *relocation dossier*
   across pillars and per-case status.
2. **Immigration-pillar deferral:** B's immigration pillar must not present a
   second, contradictory immigration document list. Either (a) B's immigration
   pillar defers to A for the document sub-list when a corridor+visa is known, or
   (b) B keeps only high-level immigration *status* items and links out to the A
   checklist — never a parallel doc list. (1473c picks (a) or (b); (a) is
   preferred where corridor+visa are resolvable.)
3. **Shared key resolver + fail-closed for B:** extract one pure key-normalization
   helper both paths import; make B fail closed (surface "not covered" like A)
   instead of returning an empty list on an unresolved key.

- **Pros:** minimal, targeted, no cross-layer entanglement, no big migration,
  respects the two-DB-layer rule; kills both concrete fault sources (silent-zero +
  duplicate immigration list); each persona's existing contract is preserved.
- **Cons:** two services remain (accepted — they answer different questions); the
  boundary must be *documented and tested* (1473e) so it doesn't silently rot.

---

## 5. Recommendation

**Adopt Option 2.** A and B are distinct by design; the reported "mismatch" comes
from two removable faults, not from having two services:

1. B's silent-zero on an unresolved destination key (AIQ-1349).
2. B's immigration pillar duplicating A's checklist with a different key.

Fixing those two — behind a documented boundary — eliminates the bug class at a
fraction of the risk of a merge, and stays inside the DB-layer rule.

---

## 6. Key-convention decision

The divergence: **A keys on ISO corridor codes** (`corridor_from/to.upper()`, e.g.
`FR`,`DE`,`NO`), while **B keys on full UPPERCASE country names** (`GERMANY`,
`NORWAY`) via the private `_ISO_TO_CATALOG_NAME` map in `requirements_builder.py:19`.

**Decision — canonical internal key = ISO-3166 alpha-2, UPPERCASE.**

- ISO is already what cases store and what A uses; it is unambiguous
  (full-name variants "UK"/"United Kingdom"/"UNITED KINGDOM" are a mapping hazard).
- **B changes at the boundary, not in its table:** rather than remap A to
  full-names or migrate B's `requirement_items.country_code` data immediately, add
  **one shared pure resolver** (1473b) — `resolve_dest_key(raw) -> ISO` — and have
  B translate ISO→catalog-name *at the query edge* using the existing map, but
  sourced from the shared helper so there is a single definition. This removes the
  duplicate/private map without a data migration.
- **Fail-closed:** the resolver returns a sentinel (e.g. `None`/`"UNKNOWN"`) for an
  unrecognised destination; B must then surface "not covered" rather than query
  with a bad key and return zero rows. (A already fails closed.)
- **Optional follow-up (not required by 1473):** a later migration can normalise
  `requirement_items.country_code` to ISO and delete the translation entirely.
  Out of scope here; note it so it isn't lost.

---

## 7. Refactor + migration sketch (for 1473b/c/d/e)

- **1473b — shared resolver.** New pure module (no DB), e.g.
  `backend/app/services/requirements_country_key.py`, exporting `resolve_dest_key`
  (raw dest → canonical ISO or `None`) and `iso_to_catalog_name` (ISO → the
  full-name B's table currently uses). Move `_ISO_TO_CATALOG_NAME` +
  `_resolve_catalog_country` out of `requirements_builder.py` into it; both A's
  corridor keying and B's dest keying import from here. Unit-tested for ISO / full
  name / mixed case / unknown. **No schema change.**
- **1473c — reconciliation.** (i) Point `requirements_builder` at the shared
  resolver and make it **fail closed** on `None` (return a `covered=false`-style
  DTO / empty-with-reason, matching A's semantics) instead of a bare empty list.
  (ii) Implement the immigration-pillar deferral from §5.2 so B's immigration
  section no longer computes a parallel doc list. Keep the two DB layers separate.
  **No schema change** (unless the reviewer elects the optional §6 ISO migration,
  which then carries RLS/ledger discipline — but that is not required).
- **1473d — consumer wiring.** Ensure the employee dossier consumers
  (`cases_read.py:936` + `:1115`, `cases_write.py:292` — **not** the dead
  `cases.py`) and the HR/employee immigration consumers all go through the
  reconciled entrypoints. No contract change beyond the documented deferral.
- **1473e — parity + zero-miss guard.** A test that (a) a case's immigration items
  are consistent between the A checklist and B's immigration pillar (or the
  documented, intentional difference), and (b) the resolver never yields a
  zero-row query for a known corridor/destination (FR→NO, and a known dest).
  Must fail on today's `main` and pass after b/c/d. Run the **full** backend suite
  (adding a SELECT column elsewhere breaks per-file SQLite `_SCHEMA` fixtures).

---

## 8. Reviewer decision required

**One decision unblocks the rest:**

> Confirm **Option 2 (documented boundary + immigration-pillar deferral + shared
> ISO key resolver, no data migration)**, with **canonical internal key = ISO
> alpha-2 UPPERCASE** and **B translating ISO→catalog-name at the query edge via
> the shared helper**.

Sub-choice deferred to 1473c (does not block b): immigration-pillar deferral
strategy **(a)** B defers to A for the immigration doc sub-list when corridor+visa
are known, vs **(b)** B keeps only immigration *status* + links to the A checklist.
Recommendation: **(a)** where corridor+visa resolve, fall back to **(b)**.

If the reviewer instead wants the full **Option 1 merge** (single store + single
service), that is a larger, migration-bearing effort and 1473b–e should be
re-scoped before proceeding.
