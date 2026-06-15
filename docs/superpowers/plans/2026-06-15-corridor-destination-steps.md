# Destination-Specific Roadmap Steps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Tailor non-immigration service roadmap steps by destination country (augment-only), starting with DE + NO.

**Architecture:** Add a `SERVICE_STEPS_BY_DESTINATION` map + merge helper to the pure step library; the bridge resolves the case's destination ISO and materialises generic + destination-extra steps; reconcile prunes any service milestone no longer in the desired set so destination changes clean up. No migration, no frontend.

**Tech Stack:** Python 3.11, SQLAlchemy core, pytest. Backend tests via `<venv311>/python -m pytest` from repo root with `RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1`.

**Spec:** `docs/superpowers/specs/2026-06-15-corridor-destination-steps-design.md`

---

## Task 1: Destination step map + merge (pure library)

**Files:** Modify `backend/app/services/service_roadmap_steps.py`; Test `backend/tests/test_service_roadmap_steps.py`

- [ ] **Step 1: Write the failing test** (append to `test_service_roadmap_steps.py`)

```python
def test_destination_merge_augments_generic_steps():
    from backend.app.services.service_roadmap_steps import (
        steps_for_service_in_destination, steps_for_service, normalize_destination_iso,
    )
    de = steps_for_service_in_destination("banking", "DE")
    keys = [s.key for s in de]
    # generic banking steps still present
    assert {"appt", "open_account"} <= set(keys)
    # DE adds an Anmeldung step, sorted before opening the account
    assert "anmeldung" in keys
    assert keys.index("anmeldung") < keys.index("open_account")
    # unknown destination -> generic only
    assert [s.key for s in steps_for_service_in_destination("banking", "ZZ")] == \
           [s.key for s in steps_for_service("banking")]
    # name or code both normalise
    assert normalize_destination_iso("Germany") == "DE"
    assert normalize_destination_iso("de") == "DE"
    assert normalize_destination_iso(None) is None


def test_immigration_has_no_destination_overrides():
    from backend.app.services.service_roadmap_steps import SERVICE_STEPS_BY_DESTINATION
    assert "immigration" not in SERVICE_STEPS_BY_DESTINATION
```

- [ ] **Step 2: Run → fail** `cd backend && <venv311>/python -m pytest tests/test_service_roadmap_steps.py -q` (ImportError).

- [ ] **Step 3: Implement** — add to `service_roadmap_steps.py` after `SERVICE_STEPS`:

```python
# Destination-specific EXTRA steps that augment the generic per-service steps.
# Keyed service_key -> destination ISO2 -> [ServiceStep]. Immigration is excluded
# on purpose — the AI roadmap generator already produces corridor-specific
# immigration steps. sort_offset slots each extra into the generic sequence.
SERVICE_STEPS_BY_DESTINATION: Dict[str, Dict[str, List[ServiceStep]]] = {
    "banking": {
        "DE": [
            ServiceStep("anmeldung", "Register your address (Anmeldung) first",
                        "German banks require an Anmeldung (address registration) confirmation to open an account.",
                        "arrival", 5),
        ],
    },
    "housing": {
        "DE": [
            ServiceStep("anmeldung", "Register your address (Anmeldung) at the Bürgeramt",
                        "Within ~2 weeks of moving in, register your address — it's needed for banking, tax ID and more.",
                        "arrival", 35),
        ],
    },
    "schools": {
        "DE": [
            ServiceStep("school_year_de", "Check the German school year & Schulpflicht",
                        "Schooling is compulsory (Schulpflicht); the school year starts in late summer — plan enrolment around it.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("school_year_no", "Check the Norwegian school year",
                        "The school year starts in mid-August; contact the local kommune about enrolment.",
                        "pre_departure", 5),
        ],
    },
    "pets": {
        "DE": [
            ServiceStep("import_de", "Prepare EU pet entry documents",
                        "For Germany (EU): microchip, valid rabies vaccination, and an EU pet passport or health certificate.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("import_no", "Meet Norway's pet import rules",
                        "Norway requires microchip, rabies vaccination, and (for dogs) tapeworm treatment 24–120h before arrival.",
                        "pre_departure", 5),
        ],
    },
    "movers": {
        "DE": [
            ServiceStep("customs_de", "Prepare EU customs/removal-goods paperwork",
                        "Moving within the EU is simpler; keep an inventory and proof of prior residence for removal-goods relief.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("customs_no", "Prepare Norwegian customs declaration",
                        "Norway is outside the EU customs union — you'll declare household goods; a moving-goods exemption may apply.",
                        "pre_departure", 5),
        ],
    },
}

# Minimal, self-contained country -> ISO2 normaliser (kept light so this pure
# module doesn't pull in the heavier country/RAG stacks). Covers the destinations
# we support plus ISO2 pass-through.
_DEST_NAME_TO_ISO = {
    "germany": "DE", "de": "DE", "deu": "DE",
    "norway": "NO", "no": "NO", "nor": "NO",
    "france": "FR", "fr": "FR",
    "india": "IN", "in": "IN",
}


def normalize_destination_iso(value: Optional[str]) -> Optional[str]:
    """Country name or code -> ISO2 (e.g. 'Germany'/'de' -> 'DE'). None if unknown."""
    if not value:
        return None
    raw = str(value).strip()
    hit = _DEST_NAME_TO_ISO.get(raw.lower())
    if hit:
        return hit
    return raw.upper() if len(raw) == 2 and raw.isalpha() else None


def destination_steps(service_key: str, dest_iso: Optional[str]) -> List[ServiceStep]:
    """Destination-specific extra steps for a service (alias-aware). [] if none."""
    if not dest_iso:
        return []
    by_dest = SERVICE_STEPS_BY_DESTINATION.get(_canonical_service_key(service_key))
    if not by_dest:
        return []
    return by_dest.get(dest_iso.upper(), [])


def steps_for_service_in_destination(service_key: str, dest_iso: Optional[str]) -> List[ServiceStep]:
    """Generic steps merged with the destination's extras, sorted by sort_offset."""
    merged = list(steps_for_service(service_key)) + destination_steps(service_key, dest_iso)
    return sorted(merged, key=lambda s: s.sort_offset)
```

- [ ] **Step 4: Run → pass.** `cd backend && <venv311>/python -m pytest tests/test_service_roadmap_steps.py -q` (all pass).

- [ ] **Step 5: Commit** `git add backend/app/services/service_roadmap_steps.py backend/tests/test_service_roadmap_steps.py && git commit -m "feat(roadmap): destination-specific step overrides (augment generic per-service steps)"`

---

## Task 2: Bridge resolves destination + prunes stale steps

**Files:** Modify `backend/app/services/service_roadmap_bridge.py`; Test `backend/tests/test_service_roadmap_bridge.py`

- [ ] **Step 1: Write the failing test** (append; extend the existing FakeDB so it can store a case destination + expose `delete_service_milestones_not_in_types`).

```python
def test_destination_steps_materialise_and_prune(monkeypatch):
    from backend.app.services import service_roadmap_bridge as bridge

    db = FakeDB()
    # Pretend this case's destination is Germany.
    monkeypatch.setattr(bridge, "_destination_iso_for_case", lambda d, c, request_id=None: "DE")

    bridge.reconcile_service_milestones(db, "case1", ["banking"])
    rows = [m for m in db.list_case_milestones("case1") if m["source"] == "service"]
    types = {r["milestone_type"] for r in rows}
    assert "service_banking_anmeldung" in types      # DE extra present
    assert "service_banking_open_account" in types   # generic present

    # Destination changes to Norway -> the DE-only Anmeldung step is pruned.
    monkeypatch.setattr(bridge, "_destination_iso_for_case", lambda d, c, request_id=None: "NO")
    bridge.reconcile_service_milestones(db, "case1", ["banking"])
    types2 = {r["milestone_type"] for r in db.list_case_milestones("case1") if r["source"] == "service"}
    assert "service_banking_anmeldung" not in types2
    assert "service_banking_open_account" in types2
```

Extend `FakeDB` (Task-4 class from #762's test file) with:

```python
    def delete_service_milestones_not_in_types(self, case_id, keep_types, request_id=None):
        keep = set(keep_types)
        with self.engine.begin() as c:
            rows = c.execute(text(
                "SELECT id, milestone_type FROM case_milestones "
                "WHERE (case_id=:cid OR canonical_case_id=:cid) AND source='service'"
            ), {"cid": case_id}).mappings().all()
            for r in rows:
                if r["milestone_type"] not in keep:
                    c.execute(text("DELETE FROM case_milestones WHERE id=:id"), {"id": r["id"]})
```

- [ ] **Step 2: Run → fail** (`_destination_iso_for_case` / dest merge not wired).

- [ ] **Step 3: Implement** in `service_roadmap_bridge.py`:

Update imports:
```python
from backend.app.services.service_roadmap_steps import (
    steps_for_service, steps_for_service_in_destination, service_key_for_category,
    normalize_destination_iso, _canonical_service_key,
)
```

Add the resolver (best-effort, light — reads the case draft's destCountry, falls back to relocation_cases.host_country):
```python
def _destination_iso_for_case(db: Any, case_id: str, *, request_id: Optional[str] = None) -> Optional[str]:
    """Resolve the case's destination country to ISO2, best-effort. None if unknown."""
    import json
    cid = db.coalesce_case_lookup_id(case_id)
    try:
        with db.engine.connect() as conn:
            row = conn.execute(_sql_text(
                "SELECT draft_json FROM cases WHERE id = :cid"
            ), {"cid": cid}).fetchone()
            if row and row[0]:
                draft = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                dest = ((draft or {}).get("relocationBasics") or {}).get("destCountry")
                iso = normalize_destination_iso(dest)
                if iso:
                    return iso
            row = conn.execute(_sql_text(
                "SELECT host_country FROM relocation_cases WHERE id::text = :cid"
            ), {"cid": cid}).fetchone()
            if row and row[0]:
                return normalize_destination_iso(str(row[0]))
    except Exception:
        log.debug("destination resolve failed for case %s", case_id, exc_info=True)
    return None
```

Add `from sqlalchemy import text as _sql_text` to the imports.

In `reconcile_service_milestones`, resolve destination once and use the dest-aware lookup; collect desired types and prune. Replace the body's step loop region:

```python
    dest_iso = _destination_iso_for_case(db, case_id, request_id=request_id)

    db.delete_service_milestones_not_in(case_id, keys, request_id=request_id)

    existing = {
        m["milestone_type"]: m
        for m in db.list_case_milestones(case_id, request_id=request_id)
        if m.get("source") == "service"
    }

    desired_types: list = []
    added = kept = 0
    for service_key in keys:
        for step in steps_for_service_in_destination(service_key, dest_iso):
            mt = _milestone_type(service_key, step.key)
            desired_types.append(mt)
            row = existing.get(mt)
            if row:
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

    # Prune service rows for selected services that are no longer desired (e.g. a
    # destination change dropped a destination-specific step).
    db.delete_service_milestones_not_in_types(case_id, desired_types, request_id=request_id)

    removed_total = len(existing) - kept
    return {"added": added, "removed": max(removed_total, 0), "kept": kept}
```

- [ ] **Step 4: Add the real DB helper** to `backend/db/cases.py` (next to `delete_service_milestones_not_in`):

```python
    def delete_service_milestones_not_in_types(
        self, case_id: str, keep_types: Sequence[str],
        *, request_id: Optional[str] = None,
    ) -> int:
        """Delete source='service' milestones whose milestone_type is NOT in
        keep_types. Used so a changed step set (e.g. destination change) cleans up
        stale rows. Never touches AI/deterministic/manual rows."""
        cid = self.coalesce_case_lookup_id(case_id)
        types = list(keep_types)
        with self.engine.begin() as conn:
            if types:
                ph = ", ".join(f":t{i}" for i in range(len(types)))
                params: Dict[str, Any] = {"cid": cid, **{f"t{i}": t for i, t in enumerate(types)}}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service' "
                    f"AND milestone_type NOT IN ({ph})"
                )
            else:
                params = {"cid": cid}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) AND source = 'service'"
                )
            result = self._exec(conn, sql, params, op_name="delete_service_milestones_not_in_types", request_id=request_id)
        return getattr(result, "rowcount", 0) or 0
```

- [ ] **Step 5: Run → pass.** `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest tests/test_service_roadmap_bridge.py tests/test_service_roadmap_steps.py -q`

- [ ] **Step 6: Commit** `git add backend/app/services/service_roadmap_bridge.py backend/db/cases.py backend/tests/test_service_roadmap_bridge.py && git commit -m "feat(roadmap): bridge resolves destination + prunes stale service milestones"`

---

## Task 3: Verify + push + PR

- [ ] **Step 1:** `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest tests/test_service_roadmap_steps.py tests/test_service_roadmap_bridge.py tests/test_persist_generated_milestones.py -q` → all pass.
- [ ] **Step 2:** `<venv311>/python -c "import backend.app.services.service_roadmap_bridge, backend.db.cases; print('imports OK')"`.
- [ ] **Step 3:** Confirm no migration/frontend files changed: `git diff --name-only origin/main...HEAD`.
- [ ] **Step 4:** Push `git push -u origin feat/corridor-destination-steps`.
- [ ] **Step 5:** PR via REST (gh GraphQL 401s): `gh api -X POST repos/rlecomte1929/rolec/pulls -f title="feat(roadmap): destination-specific roadmap step overrides" -f head="feat/corridor-destination-steps" -f base="main" -f body="$(cat docs/superpowers/specs/2026-06-15-corridor-destination-steps-design.md)"`. Do NOT merge.

---

## Self-review
- Dest map + merge + normaliser → Task 1. ✅
- Bridge resolves destination + dest-aware materialise → Task 2. ✅
- Prune stale (destination change correctness) → Task 2 (bridge + DB helper). ✅
- Immigration excluded → no immigration key in the dest map (asserted). ✅
- No migration / no frontend → confirmed in Task 3. ✅
- **Types:** `steps_for_service_in_destination(service_key, dest_iso)`, `normalize_destination_iso`, `_canonical_service_key` defined in Task 1, used in Task 2. `delete_service_milestones_not_in_types(case_id, keep_types)` defined in Task 2 (cases.py) + FakeDB, called in the bridge. Consistent.
