# Service → Roadmap Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an employee selects services (Services tab) or requests a quote, materialise concrete per-service real-world steps into the live roadmap (`case_milestones`), and keep them across AI roadmap regeneration.

**Architecture:** A deterministic step library (`service_key → ordered steps`) feeds an idempotent `reconcile_service_milestones(case_id, selected_services)` that upserts/removes only `source='service'` milestone rows. Triggered from the services-state save and the quote-request endpoint. `case_milestones` gains `source` + `service_key` columns so service rows are managed independently and survive the AI generator's delete-and-rewrite.

**Tech Stack:** FastAPI (Python 3.11), SQLAlchemy core (raw SQL via `db._exec`), Supabase Postgres (prod) + SQLite (tests), pytest.

**Spec:** `docs/superpowers/specs/2026-06-15-service-roadmap-bridge-design.md`

**Conventions reminder (from backend/CLAUDE.md):**
- DB methods live on the `Database` class in `backend/db/cases.py` (raw SQL via `self._exec(conn, sql, params, op_name=..., request_id=...)`).
- Migrations: commit a file under `supabase/migrations/<ts>_<name>.sql`; NEVER apply via MCP. Altering an existing table (not creating one) ⇒ no new RLS block required (RLS already enabled on `case_milestones`).
- Run backend tests from repo root: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 python -m pytest <path> -v`.

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|-----------|
| `supabase/migrations/20260627000000_case_milestones_source_service_key.sql` | Add `source`+`service_key` columns, backfill, index | Create |
| `backend/app/services/service_roadmap_steps.py` | Pure step library: `service_key → steps`, category→key map | Create |
| `backend/app/services/service_roadmap_bridge.py` | `reconcile_service_milestones()` + `advance_quote_step()` | Create |
| `backend/db/cases.py` | Add `source`/`service_key` to upsert + list; `exclude_source` on delete; `delete_service_milestones_not_in`; columns in both init DDLs | Modify |
| `backend/app/services/case_roadmap_profile.py` | Scope regen DELETE to non-service; tag AI rows `source='ai'` | Modify |
| `backend/app/routers/services_state.py` | Call reconcile after save (best-effort) | Modify |
| `backend/app/routers/employee_quotes.py` | Advance quote step after insert (best-effort) | Modify |
| `backend/tests/test_service_roadmap_steps.py` | Unit tests — step library | Create |
| `backend/tests/test_service_roadmap_bridge.py` | Unit tests — reconcile + regen coexistence | Create |

---

## Task 1: Migration — tag `case_milestones`

**Files:**
- Create: `supabase/migrations/20260627000000_case_milestones_source_service_key.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Add provenance tagging to case_milestones so service-derived roadmap steps can
-- be reconciled independently and survive AI roadmap regeneration.
-- Altering an existing table (case_milestones already has RLS enabled, see
-- 20260325000000_case_milestones.sql) — no new RLS block required.

ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS service_key text;

-- Backfill provenance for existing rows (clarity + queryability). AI-generated
-- milestone_type values look like "{phase}_ai_{order}"; everything else is the
-- deterministic seed. New service rows will be written with source='service'.
UPDATE public.case_milestones
   SET source = CASE WHEN milestone_type LIKE '%\_ai\_%' ESCAPE '\' THEN 'ai'
                     ELSE 'deterministic_seed' END
 WHERE source IS NULL;

CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical_source
  ON public.case_milestones (canonical_case_id, source);
```

- [ ] **Step 2: Verify the file lints as SQL (no apply)**

Run: `python3 -c "import pathlib,re; s=pathlib.Path('supabase/migrations/20260627000000_case_milestones_source_service_key.sql').read_text(); assert 'ADD COLUMN IF NOT EXISTS source' in s and 'idx_case_milestones_canonical_source' in s; print('migration OK')"`
Expected: `migration OK`

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260627000000_case_milestones_source_service_key.sql
git commit -m "feat(db): add source + service_key to case_milestones for service roadmap bridge"
```

> Optional pre-merge validation (does NOT touch prod): run the column-add + a SELECT inside a single MCP `execute_sql` block ending with `RAISE EXCEPTION 'ALL_TESTS_PASSED'` so it rolls back (see `reference_migration_validation_rollback`). Not required for the plan to proceed.

---

## Task 2: Step library (pure, no DB)

**Files:**
- Create: `backend/app/services/service_roadmap_steps.py`
- Test: `backend/tests/test_service_roadmap_steps.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_service_roadmap_steps.py
from backend.app.services.service_roadmap_steps import (
    SERVICE_STEPS, steps_for_service, service_key_for_category, ServiceStep,
)


def test_every_service_has_at_least_one_well_formed_step():
    assert SERVICE_STEPS, "step library must not be empty"
    for key, steps in SERVICE_STEPS.items():
        assert steps, f"{key} has no steps"
        for s in steps:
            assert isinstance(s, ServiceStep)
            assert s.key and s.title and s.phase
            assert s.phase in {"pre_departure", "during", "arrival"}


def test_steps_for_known_and_unknown_service():
    assert steps_for_service("immigration")  # known
    assert steps_for_service("does_not_exist") == []  # unknown -> empty, no crash


def test_immigration_has_an_embassy_step_and_schools_has_admissions():
    imm_titles = " ".join(s.title.lower() for s in steps_for_service("immigration"))
    assert "embassy" in imm_titles or "consular" in imm_titles
    sch_titles = " ".join(s.title.lower() for s in steps_for_service("schools"))
    assert "admission" in sch_titles


def test_quote_step_key_is_stable_for_quote_trigger():
    # Services that support quotes expose a step whose key endswith "quote".
    housing = {s.key for s in steps_for_service("housing")}
    assert any(k.endswith("quote") for k in housing)


def test_category_label_maps_to_service_key():
    assert service_key_for_category("Housing search") == "housing"
    assert service_key_for_category("Schools / Childcare") == "schools"
    assert service_key_for_category("Banking") in {"banking", "banks"}
    assert service_key_for_category("totally unknown category") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/test_service_roadmap_steps.py -v`
Expected: FAIL with `ModuleNotFoundError: backend.app.services.service_roadmap_steps`

- [ ] **Step 3: Implement the step library**

```python
# backend/app/services/service_roadmap_steps.py
"""Deterministic per-service roadmap step library.

Maps a service_key (as used by the Service providers tab / case_services) to an
ordered list of concrete real-world steps. Pure data + helpers — no DB, no I/O —
so it unit-tests trivially and is safe to import anywhere.

`phase` aligns with the relocation plan view phases:
  pre_departure | during | arrival
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ServiceStep:
    key: str           # stable within a service; used to build milestone_type
    title: str
    description: str
    phase: str         # pre_departure | during | arrival
    sort_offset: int   # ordering within the service cluster


SERVICE_STEPS: Dict[str, List[ServiceStep]] = {
    "immigration": [
        ServiceStep("embassy_appt", "Book consular/embassy appointment",
                    "Schedule your visa or permit appointment at the relevant consulate or embassy.",
                    "pre_departure", 10),
        ServiceStep("gather_docs", "Gather visa/permit documents",
                    "Collect the documents required for your visa or residence permit application.",
                    "pre_departure", 20),
        ServiceStep("submit_application", "Submit application",
                    "Submit your visa or permit application.", "pre_departure", 30),
        ServiceStep("biometrics", "Attend biometrics appointment",
                    "Attend the biometrics/identity appointment if required.", "during", 40),
        ServiceStep("collect_permit", "Collect residence permit",
                    "Collect your residence permit once approved.", "arrival", 50),
    ],
    "schools": [
        ServiceStep("shortlist", "Shortlist schools",
                    "Identify suitable schools near your destination.", "pre_departure", 10),
        ServiceStep("contact_admissions", "Contact school admissions",
                    "Reach out to admissions offices about availability and requirements.",
                    "pre_departure", 20),
        ServiceStep("submit_applications", "Submit school applications",
                    "Apply to your shortlisted schools.", "pre_departure", 30),
        ServiceStep("confirm_enrolment", "Confirm enrolment",
                    "Confirm your child's place and enrolment.", "arrival", 40),
    ],
    "housing": [
        ServiceStep("criteria", "Define housing search criteria",
                    "Set budget, area, size and must-haves for your home search.", "pre_departure", 10),
        ServiceStep("quote", "Request & compare housing quotes",
                    "Request and compare offers from housing providers.", "pre_departure", 20),
        ServiceStep("viewings", "Attend viewings",
                    "View shortlisted properties.", "during", 30),
        ServiceStep("sign_lease", "Sign lease",
                    "Sign your rental or purchase agreement.", "arrival", 40),
    ],
    "banking": [
        ServiceStep("appt", "Book account-opening appointment",
                    "Schedule an appointment to open a local bank account.", "arrival", 10),
        ServiceStep("open_account", "Open local bank account",
                    "Open your local account and set up transfers.", "arrival", 20),
    ],
    "movers": [
        ServiceStep("quote", "Request & compare moving quotes",
                    "Request and compare quotes from international movers.", "pre_departure", 10),
        ServiceStep("book_mover", "Book mover",
                    "Confirm and book your chosen moving company.", "pre_departure", 20),
        ServiceStep("pack_ship", "Pack & ship household goods",
                    "Pack and ship your belongings.", "during", 30),
    ],
    "tax": [
        ServiceStep("consult", "Book tax-advisor consultation",
                    "Arrange advice on cross-border and host-country tax.", "pre_departure", 10),
        ServiceStep("gather_docs", "Gather income/residency documents",
                    "Collect documents your tax advisor will need.", "pre_departure", 20),
    ],
    "language": [
        ServiceStep("choose_course", "Choose a language course",
                    "Pick a course that fits your level and schedule.", "arrival", 10),
        ServiceStep("enrol", "Enrol in language course",
                    "Enrol and book your first lessons.", "arrival", 20),
    ],
    "spouse": [
        ServiceStep("career_consult", "Partner career consultation",
                    "Arrange a career consultation for your partner.", "arrival", 10),
        ServiceStep("cv_review", "CV / credentials review",
                    "Review and adapt your partner's CV and credentials for the local market.",
                    "arrival", 20),
    ],
    "temp": [
        ServiceStep("book_temp", "Book temporary accommodation",
                    "Arrange a place to stay on arrival before permanent housing.",
                    "pre_departure", 10),
    ],
    "pets": [
        ServiceStep("vet_docs", "Vet health check & documents",
                    "Complete the vet checks and paperwork for pet relocation.", "pre_departure", 10),
        ServiceStep("book_transport", "Book pet transport",
                    "Arrange your pet's transport to the destination.", "pre_departure", 20),
    ],
}

# Aliases so callers using a different vocabulary still resolve (serviceConfig
# uses 'banks'/'temp_accommodation'/'visa').
_SERVICE_ALIASES: Dict[str, str] = {
    "banks": "banking",
    "temp_accommodation": "temp",
    "visa": "immigration",
    "immigration_support": "immigration",
}


def _canonical_service_key(service_key: str) -> str:
    key = (service_key or "").strip().lower()
    return _SERVICE_ALIASES.get(key, key)


def steps_for_service(service_key: str) -> List[ServiceStep]:
    """Steps for a service_key (alias-aware). Unknown key -> []."""
    return SERVICE_STEPS.get(_canonical_service_key(service_key), [])


# Maps a quote_requests.service_categories[] label to a service_key. Labels come
# from the frontend serviceConfig; match on a lowercased keyword so minor label
# drift still resolves.
_CATEGORY_KEYWORDS = [
    ("housing", "housing"),
    ("school", "schools"),
    ("childcare", "schools"),
    ("immigration", "immigration"),
    ("visa", "immigration"),
    ("permit", "immigration"),
    ("mover", "movers"),
    ("moving", "movers"),
    ("bank", "banking"),
    ("tax", "tax"),
    ("language", "language"),
    ("spouse", "spouse"),
    ("partner", "spouse"),
    ("temporary", "temp"),
    ("pet", "pets"),
]


def service_key_for_category(category: str) -> Optional[str]:
    """Resolve a service-category label to a service_key, or None if unknown."""
    label = (category or "").strip().lower()
    if not label:
        return None
    for keyword, key in _CATEGORY_KEYWORDS:
        if keyword in label:
            return key
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_service_roadmap_steps.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/service_roadmap_steps.py backend/tests/test_service_roadmap_steps.py
git commit -m "feat(roadmap): deterministic per-service roadmap step library"
```

---

## Task 3: DB layer — tag, list, scoped delete

**Files:**
- Modify: `backend/db/cases.py` (`upsert_case_milestone`, `list_case_milestones`, `delete_case_milestones`, both init DDLs; add `delete_service_milestones_not_in`)

- [ ] **Step 1: Add columns to both init DDLs**

In `_ensure_postgres_case_milestones_schema` (≈ line 2998), add the two columns to the `CREATE TABLE IF NOT EXISTS public.case_milestones (...)` body, after `notes text`:

```python
                  notes text,
                  source text,
                  service_key text
                )
```

Immediately after that `CREATE TABLE` block (before the index statements), add idempotent ALTERs so existing test/dev DBs gain the columns:

```python
        for _col in ("source", "service_key"):
            conn.execute(text(
                f"ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS {_col} text"
            ))
```

In `_ensure_case_milestones_tracker_sqlite` (≈ line 605), add the columns to the `CREATE TABLE case_milestones__new (...)` body after `notes TEXT`:

```python
                    notes TEXT,
                    source TEXT,
                    service_key TEXT
                )
```

(The SQLite copy `INSERT ... SELECT` does not need the new columns — they default to NULL on the rebuilt table.)

- [ ] **Step 2: Add `source`/`service_key` to `upsert_case_milestone`**

Add two keyword params to the signature (after `notes`):

```python
        notes: Optional[str] = None,
        source: Optional[str] = None,
        service_key: Optional[str] = None,
        milestone_id: Optional[str] = None,
```

In the UPDATE branch, add to the `SET` clause and params:

```python
                       notes = :notes, source = :source, service_key = :svc_key, updated_at = :now
```
```python
                        "notes": notes,
                        "source": source,
                        "svc_key": service_key,
                        "now": now,
```

In the INSERT branch, add the columns and values:

```python
                """INSERT INTO case_milestones
                   (id, case_id, canonical_case_id, milestone_type, title, description, target_date, actual_date, status, sort_order, created_at, updated_at, owner, criticality, notes, source, service_key)
                   VALUES (:id, :cid, :canonical, :mt, :title, :desc, :td, :ad, :status, :so, :now, :now, :owner, :crit, :notes, :source, :svc_key)""",
```
```python
                    "notes": notes,
                    "source": source,
                    "svc_key": service_key,
                },
```

- [ ] **Step 3: Surface `source`/`service_key` from `list_case_milestones`**

In `list_case_milestones`, extend the SELECT column list:

```python
                """SELECT id, case_id, canonical_case_id, milestone_type, title, description,
                   target_date, actual_date, status, sort_order, created_at, updated_at,
                   owner, criticality, notes, source, service_key
                   FROM case_milestones
                   WHERE (canonical_case_id = :cid OR case_id = :cid)
                   ORDER BY sort_order ASC, created_at ASC""",
```

- [ ] **Step 4: Add `exclude_source` to `delete_case_milestones`**

Replace the method body's signature + SQL:

```python
    def delete_case_milestones(
        self, case_id: str, *, exclude_source: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> int:
        """Delete milestones for a case. Used before re-persisting a regenerated
        roadmap. `exclude_source` (e.g. 'service') preserves rows with that
        source so externally-managed milestones survive a regeneration."""
        cid = self.coalesce_case_lookup_id(case_id)
        sql = "DELETE FROM case_milestones WHERE (canonical_case_id = :cid OR case_id = :cid)"
        params = {"cid": cid}
        if exclude_source is not None:
            sql += " AND (source IS NULL OR source <> :excl)"
            params["excl"] = exclude_source
        with self.engine.begin() as conn:
            result = self._exec(conn, sql, params, op_name="delete_case_milestones", request_id=request_id)
        return getattr(result, "rowcount", 0) or 0
```

- [ ] **Step 5: Add `delete_service_milestones_not_in`**

Add this method directly below `delete_case_milestones`:

```python
    def delete_service_milestones_not_in(
        self, case_id: str, keep_service_keys: Sequence[str],
        *, request_id: Optional[str] = None,
    ) -> int:
        """Delete source='service' milestones whose service_key is NOT in
        keep_service_keys (i.e. the service was deselected). Never touches
        AI/deterministic/manual rows."""
        cid = self.coalesce_case_lookup_id(case_id)
        keys = list(keep_service_keys)
        with self.engine.begin() as conn:
            if keys:
                placeholders = ", ".join(f":k{i}" for i in range(len(keys)))
                params = {"cid": cid, **{f"k{i}": k for i, k in enumerate(keys)}}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service' "
                    f"AND service_key NOT IN ({placeholders})"
                )
            else:
                params = {"cid": cid}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service'"
                )
            result = self._exec(conn, sql, params, op_name="delete_service_milestones_not_in", request_id=request_id)
        return getattr(result, "rowcount", 0) or 0
```

Confirm `Sequence` is imported at the top of `backend/db/cases.py` (it imports from `typing`); if not, add it.

- [ ] **Step 6: Commit**

```bash
git add backend/db/cases.py
git commit -m "feat(db): source/service_key on milestones + scoped deletes for service bridge"
```

---

## Task 4: Reconcile + quote-advance service

**Files:**
- Create: `backend/app/services/service_roadmap_bridge.py`
- Test: `backend/tests/test_service_roadmap_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_service_roadmap_bridge.py
import uuid
import pytest
from sqlalchemy import create_engine, text

from backend.app.services.service_roadmap_bridge import (
    reconcile_service_milestones, advance_quote_step,
)


class FakeDB:
    """Minimal Database-shaped object backed by in-memory SQLite, exposing only
    the methods the bridge uses."""

    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as c:
            c.execute(text("""
                CREATE TABLE case_milestones (
                  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, canonical_case_id TEXT,
                  milestone_type TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
                  target_date TEXT, actual_date TEXT, status TEXT NOT NULL DEFAULT 'pending',
                  sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, owner TEXT DEFAULT 'joint',
                  criticality TEXT DEFAULT 'normal', notes TEXT, source TEXT, service_key TEXT
                )
            """))

    def coalesce_case_lookup_id(self, case_id):
        return case_id

    def _exec(self, conn, sql, params=None, **kwargs):
        return conn.execute(text(sql), params or {})

    def list_case_milestones(self, case_id, request_id=None):
        with self.engine.connect() as c:
            rows = c.execute(text(
                "SELECT id, milestone_type, title, status, source, service_key "
                "FROM case_milestones WHERE case_id = :cid OR canonical_case_id = :cid"
            ), {"cid": case_id}).mappings().all()
        return [dict(r) for r in rows]

    def upsert_case_milestone(self, case_id, milestone_type, title, *, description=None,
                              status="pending", sort_order=0, source=None, service_key=None,
                              milestone_id=None, request_id=None, **_):
        with self.engine.begin() as c:
            if milestone_id:
                c.execute(text(
                    "UPDATE case_milestones SET title=:t, description=:d, status=:s, "
                    "sort_order=:so, source=:src, service_key=:sk, updated_at='now' WHERE id=:id"
                ), {"t": title, "d": description, "s": status, "so": sort_order,
                    "src": source, "sk": service_key, "id": milestone_id})
                return {"id": milestone_id}
            mid = str(uuid.uuid4())
            c.execute(text(
                "INSERT INTO case_milestones (id, case_id, canonical_case_id, milestone_type, "
                "title, description, status, sort_order, created_at, updated_at, source, service_key) "
                "VALUES (:id,:cid,:cid,:mt,:t,:d,:s,:so,'now','now',:src,:sk)"
            ), {"id": mid, "cid": case_id, "mt": milestone_type, "t": title, "d": description,
                "s": status, "so": sort_order, "src": source, "sk": service_key})
            return {"id": mid}

    def delete_service_milestones_not_in(self, case_id, keep_service_keys, request_id=None):
        keys = list(keep_service_keys)
        with self.engine.begin() as c:
            if keys:
                ph = ",".join(f":k{i}" for i in range(len(keys)))
                params = {"cid": case_id, **{f"k{i}": k for i, k in enumerate(keys)}}
                sql = (f"DELETE FROM case_milestones WHERE (case_id=:cid OR canonical_case_id=:cid) "
                       f"AND source='service' AND service_key NOT IN ({ph})")
            else:
                params = {"cid": case_id}
                sql = ("DELETE FROM case_milestones WHERE (case_id=:cid OR canonical_case_id=:cid) "
                       "AND source='service'")
            c.execute(text(sql), params)


def _svc_rows(db, case_id):
    return [m for m in db.list_case_milestones(case_id) if m["source"] == "service"]


def test_selecting_services_materialises_steps():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["immigration", "schools"])
    rows = _svc_rows(db, "case1")
    assert rows, "expected service milestones"
    keys = {r["service_key"] for r in rows}
    assert keys == {"immigration", "schools"}
    titles = " ".join(r["title"].lower() for r in rows)
    assert "embassy" in titles or "consular" in titles


def test_deselecting_a_service_removes_its_steps():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["immigration", "schools"])
    reconcile_service_milestones(db, "case1", ["immigration"])  # dropped schools
    keys = {r["service_key"] for r in _svc_rows(db, "case1")}
    assert keys == {"immigration"}


def test_reconcile_is_idempotent():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["housing"])
    n1 = len(_svc_rows(db, "case1"))
    reconcile_service_milestones(db, "case1", ["housing"])
    n2 = len(_svc_rows(db, "case1"))
    assert n1 == n2 and n1 > 0


def test_reconcile_never_touches_non_service_rows():
    db = FakeDB()
    db.upsert_case_milestone("case1", "phase_ai_01", "AI step", source="ai")
    db.upsert_case_milestone("case1", "manual_x", "Manual step", source=None)
    reconcile_service_milestones(db, "case1", ["banking"])
    all_rows = db.list_case_milestones("case1")
    assert any(r["source"] == "ai" for r in all_rows)
    assert any(r["source"] is None for r in all_rows)


def test_unknown_service_key_is_skipped():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["banking", "not_a_service"])
    keys = {r["service_key"] for r in _svc_rows(db, "case1")}
    assert keys == {"banking"}


def test_advance_quote_step_sets_in_progress():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["housing"])
    advance_quote_step(db, "case1", ["Housing search"], quote_request_id="q-123")
    quote_rows = [r for r in _svc_rows(db, "case1") if r["milestone_type"].endswith("_quote")]
    assert quote_rows and quote_rows[0]["status"] == "in_progress"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/test_service_roadmap_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: backend.app.services.service_roadmap_bridge`

- [ ] **Step 3: Implement the bridge**

```python
# backend/app/services/service_roadmap_bridge.py
"""Bridge service selections + quote requests into the live roadmap.

`case_milestones` is the roadmap the employee sees (via the relocation plan view).
This module manages ONLY rows with source='service' — it never touches AI,
deterministic-seed, or manual milestones.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from backend.app.services.service_roadmap_steps import (
    steps_for_service, service_key_for_category, _canonical_service_key,
)

log = logging.getLogger(__name__)

# Base sort_order offset per service so service clusters sit after the
# deterministic/AI milestones (which use small sort_orders).
_SERVICE_SORT_BASE = 1000


def _milestone_type(service_key: str, step_key: str) -> str:
    return f"service_{service_key}_{step_key}"


def reconcile_service_milestones(
    db: Any, case_id: str, selected_services: Sequence[str],
    *, request_id: Optional[str] = None,
) -> dict:
    """Make source='service' milestones match `selected_services`. Idempotent.

    Returns {"added": int, "removed": int, "kept": int}. Best-effort: callers
    should wrap so a failure never breaks the originating request.
    """
    # Canonicalise + drop unknown services (no steps in the library).
    keys = []
    for raw in selected_services or []:
        ck = _canonical_service_key(raw)
        if steps_for_service(ck):
            if ck not in keys:
                keys.append(ck)
        else:
            log.info("reconcile_service_milestones: skipping unknown service '%s'", raw)

    # Remove service rows for deselected services first.
    db.delete_service_milestones_not_in(case_id, keys, request_id=request_id)

    existing = {
        m["milestone_type"]: m
        for m in db.list_case_milestones(case_id, request_id=request_id)
        if m.get("source") == "service"
    }

    added = kept = 0
    for service_key in keys:
        for step in steps_for_service(service_key):
            mt = _milestone_type(service_key, step.key)
            row = existing.get(mt)
            if row:
                # Keep employee progress: only refresh copy, never reset status.
                db.upsert_case_milestone(
                    case_id, mt, step.title, description=step.description,
                    sort_order=_SERVICE_SORT_BASE + step.sort_offset,
                    status=row.get("status", "pending"),
                    source="service", service_key=service_key,
                    milestone_id=row["id"], request_id=request_id,
                )
                kept += 1
            else:
                db.upsert_case_milestone(
                    case_id, mt, step.title, description=step.description,
                    sort_order=_SERVICE_SORT_BASE + step.sort_offset,
                    status="pending", source="service", service_key=service_key,
                    request_id=request_id,
                )
                added += 1

    removed_total = len(existing) - kept
    return {"added": added, "removed": max(removed_total, 0), "kept": kept}


def advance_quote_step(
    db: Any, case_id: str, service_categories: Sequence[str],
    *, quote_request_id: str, request_id: Optional[str] = None,
) -> int:
    """Flip each requested service's '*_quote' step to in_progress and stamp the
    quote_request_id in notes. Returns the number of steps advanced. No-op for
    categories that don't resolve or have no quote step. Best-effort."""
    targets = set()
    for cat in service_categories or []:
        key = service_key_for_category(cat)
        if not key:
            continue
        for step in steps_for_service(key):
            if step.key.endswith("quote"):
                targets.add(_milestone_type(key, step.key))

    if not targets:
        return 0

    advanced = 0
    rows = {
        m["milestone_type"]: m
        for m in db.list_case_milestones(case_id, request_id=request_id)
        if m.get("source") == "service"
    }
    for mt in targets:
        row = rows.get(mt)
        if not row:
            continue
        db.upsert_case_milestone(
            case_id, mt, row["title"],
            status="in_progress", source="service",
            service_key=row.get("service_key"),
            notes=f"quote_request_id={quote_request_id}",
            milestone_id=row["id"], request_id=request_id,
        )
        advanced += 1
    return advanced
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_service_roadmap_bridge.py -v`
Expected: PASS (6 tests)

> Note: the FakeDB's `upsert_case_milestone` test double accepts the same kwargs the bridge passes (`description`, `status`, `sort_order`, `source`, `service_key`, `milestone_id`, `notes` via `**_`). The real `Database.upsert_case_milestone` (Task 3) accepts all of these.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/service_roadmap_bridge.py backend/tests/test_service_roadmap_bridge.py
git commit -m "feat(roadmap): reconcile_service_milestones + advance_quote_step bridge"
```

---

## Task 5: Trigger reconcile from services-state save

**Files:**
- Modify: `backend/app/routers/services_state.py` (`put_services_state`, ≈ line 207)

- [ ] **Step 1: Add the best-effort reconcile after the audit call**

Locate (≈ line 207):

```python
    _audit(case_id=case_id, action=action, actor_id=actor_id, byte_size=len(blob))
    return {
```

Insert between the `_audit(...)` line and the `return {`:

```python
    # Bridge the current service selection into the roadmap. Best-effort +
    # idempotent — a reconcile failure must never fail the state save.
    try:
        from backend.app.services.service_roadmap_bridge import reconcile_service_milestones
        selected = body.state.get("selectedServices") if isinstance(body.state, dict) else None
        if isinstance(selected, list):
            reconcile_service_milestones(db, case_id, selected)
    except Exception:  # noqa: BLE001 — non-fatal best-effort bridge
        log.warning("services-state: roadmap reconcile failed for case %s", case_id, exc_info=True)
```

If `log` is not already defined in this module, add near the top imports:

```python
import logging
log = logging.getLogger(__name__)
```

(Check first — many routers already define `log`. Run: `cd backend && rtk proxy grep -n "^log = \|getLogger" app/routers/services_state.py`.)

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd backend && python -c "import backend.app.routers.services_state as m; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Run the existing services_state tests (no regression)**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 python -m pytest tests/ -k services_state -v`
Expected: PASS (or "no tests ran" if none exist — then skip)

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/services_state.py
git commit -m "feat(roadmap): reconcile service milestones on services-state save"
```

---

## Task 6: Trigger quote-advance from the quote endpoint

**Files:**
- Modify: `backend/app/routers/employee_quotes.py` (`create_quote_request`, after the INSERT + audit, before the return ≈ line 189)

- [ ] **Step 1: Read the handler tail to find the return**

Run: `cd backend && sed -n '135,200p' app/routers/employee_quotes.py` *(via Read tool, not echo)* — locate the `return` after `new_value={"event": "quote_request_created", ...}`.

- [ ] **Step 2: Add the best-effort advance before the return**

Immediately before the handler's `return`, insert:

```python
    # Advance the matching service '*_quote' roadmap step to in_progress.
    # Best-effort — never fail the quote request over a roadmap side-effect.
    try:
        from backend.app.services.service_roadmap_bridge import advance_quote_step
        advance_quote_step(db, body.case_id, body.service_categories, quote_request_id=new_id)
    except Exception:  # noqa: BLE001
        log.warning("quote-request: roadmap advance failed for case %s", body.case_id, exc_info=True)
```

Use the variable that holds the inserted row's id (the value bound to `:id` in the INSERT — confirm its name when reading; it may be `new_id`/`qr_id`). Ensure `log` exists in the module (add `import logging; log = logging.getLogger(__name__)` if absent, as in Task 5).

- [ ] **Step 3: Verify import + existing quote tests**

Run: `cd backend && python -c "import backend.app.routers.employee_quotes; print('import OK')"`
Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 python -m pytest tests/ -k quote -v`
Expected: `import OK`; quote tests PASS (or none ran → skip)

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/employee_quotes.py
git commit -m "feat(roadmap): advance service quote step on quote-request create"
```

---

## Task 7: Make service milestones survive AI regeneration

**Files:**
- Modify: `backend/app/services/case_roadmap_profile.py` (`persist_generated_milestones`, lines 141-148)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_service_roadmap_bridge.py`:

```python
def test_ai_regen_preserves_service_rows(monkeypatch):
    """persist_generated_milestones must not delete source='service' rows."""
    from backend.app.services import case_roadmap_profile as crp

    db = FakeDB()
    # add the exclude_source-aware delete the production function calls
    def delete_case_milestones(case_id, *, exclude_source=None, request_id=None):
        with db.engine.begin() as c:
            sql = "DELETE FROM case_milestones WHERE (case_id=:cid OR canonical_case_id=:cid)"
            params = {"cid": case_id}
            if exclude_source is not None:
                sql += " AND (source IS NULL OR source <> :excl)"
                params["excl"] = exclude_source
            c.execute(text(sql), params)
    db.delete_case_milestones = delete_case_milestones

    reconcile_service_milestones(db, "case1", ["housing"])           # service rows
    db.upsert_case_milestone("case1", "old_seed", "Seed", source=None)  # will be replaced

    monkeypatch.setattr(crp, "map_generated_steps_to_milestones",
                        lambda steps, corridor: [
                            {"milestone_type": "pre_departure_ai_01", "title": "AI 1"}])
    crp.persist_generated_milestones(db, "case1", [{"x": 1}], corridor="FR_DE")

    rows = db.list_case_milestones("case1")
    assert any(r["source"] == "service" for r in rows), "service rows must survive regen"
    assert any(r["milestone_type"] == "pre_departure_ai_01" for r in rows), "AI rows written"
    assert not any(r["milestone_type"] == "old_seed" for r in rows), "old seed replaced"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/test_service_roadmap_bridge.py::test_ai_regen_preserves_service_rows -v`
Expected: FAIL (service rows deleted, because the current delete is unscoped and AI rows are written untagged)

- [ ] **Step 3: Scope the delete + tag AI rows**

In `persist_generated_milestones`, change lines 144-147:

```python
    db.delete_case_milestones(case_id, request_id=request_id, exclude_source="service")
    written = 0
    for row in rows:
        db.upsert_case_milestone(case_id=case_id, request_id=request_id, source="ai", **row)
        written += 1
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && python -m pytest tests/test_service_roadmap_bridge.py::test_ai_regen_preserves_service_rows -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/case_roadmap_profile.py backend/tests/test_service_roadmap_bridge.py
git commit -m "feat(roadmap): scope AI-regen delete + tag AI milestones so service steps survive"
```

---

## Task 8: Full verification + push

- [ ] **Step 1: Run the new tests together**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 python -m pytest tests/test_service_roadmap_steps.py tests/test_service_roadmap_bridge.py -v`
Expected: all PASS

- [ ] **Step 2: Run the milestone/roadmap regression tests**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 python -m pytest tests/ -k "milestone or roadmap or services_state or quote" -v`
Expected: PASS (no regressions). Investigate any failure before pushing.

- [ ] **Step 3: Confirm the migration is the only schema-change file & lints**

Run: `git -C . diff --name-only origin/main | rtk proxy grep migrations`
Expected: only `supabase/migrations/20260627000000_case_milestones_source_service_key.sql`

- [ ] **Step 4: Push the branch**

```bash
git push -u origin feat/services-roadmap-bridge
```

- [ ] **Step 5: Open the PR (REST; gh GraphQL 401s in sandbox)**

```bash
gh api -X POST repos/rlecomte1929/rolec/pulls \
  -f title="feat(roadmap): service → roadmap bridge (per-service steps from Services tab)" \
  -f head="feat/services-roadmap-bridge" -f base="main" \
  -f body="$(cat docs/superpowers/specs/2026-06-15-service-roadmap-bridge-design.md)"
```

Do NOT merge — branch + PR for Romain's review. The migration applies on merge per migration discipline.

---

## Self-review notes (coverage check vs spec)

- Migration (source/service_key/backfill/index) → Task 1. ✅
- Step library (generic-first content) → Task 2. ✅
- Reconcile (upsert/remove, never touches non-service) → Task 4 + DB methods in Task 3. ✅
- Trigger on selection → Task 5. ✅
- Quote-advance trigger (dormant until RFQ UI enabled) → Task 6. ✅
- AI-regen coexistence (scoped delete + tag AI) → Task 7. ✅
- Lifecycle = remove on deselect → `delete_service_milestones_not_in` (Task 3) + reconcile (Task 4). ✅
- Verification (unit tests, regression, migration) → Tasks 2/4/7/8. ✅
- Out of scope (corridor content, RFQ button wiring, validate-gate, FE) → not in tasks, by design. ✅

**Type consistency:** `upsert_case_milestone(... source=, service_key=, milestone_id=, notes=)` is defined in Task 3 and called with exactly those kwargs in Task 4/7. `delete_case_milestones(case_id, *, exclude_source=, request_id=)` defined in Task 3, called with `exclude_source="service"` in Task 7. `delete_service_milestones_not_in(case_id, keep_service_keys, *, request_id=)` defined in Task 3, called in Task 4. `service_key_for_category` / `steps_for_service` / `_canonical_service_key` defined in Task 2, used in Task 4. Consistent.
