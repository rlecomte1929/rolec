# Phase 5 — Serving-layer wiring (DRAFT)

**Author:** Claude (Cowork) · **Date:** 2026-08-22 · **Owner:** Romain · **Autonomy tier:** 🔴 (mis-serving legal/tax info)
**Goal:** make the serving layer *use* the fields the ES→IE batch carries (`nationality_scope_basis`, `assertion_mode`, `non_obvious`) so promoted facts are served **correctly** — and, first, so they're served **at all**.

This is a draft for your review, grounded in the actual code. It proposes the change and a test plan; it does **not** touch your serving code yet, because there's a strategic fork below that only you should call.

---

## 1. What I found (worse, and more interesting, than the plan assumed)

### Finding A — the live matcher filters our batch out entirely
The live path for promoted `requirement_facts` is:
`admin approve → db.list_approved_requirement_facts(dest) → compute_requirements_sufficiency → GET /api/requirements/sufficiency`.
The applicability gate is `backend/app/services/requirements_sufficiency.py::_apply_applies_to`:

```python
def _apply_applies_to(applies_to, snapshot) -> bool:
    if not applies_to:
        return True
    for key, value in applies_to.items():      # EVERY key is a hard filter
        if snapshot.get(key) != value:
            return False
    return True
```

The profile snapshot (`guidance_pack_service.build_profile_snapshot`) has these keys only:
`origin_country, destination_country, move_date, employment_type, employer_country, dependents, nationality, current_location, notes, visa_type, dossier_answers, family_members`.

Our batch's `applies_to` carries ~10 keys — `corridor, nationality, status, persona, topic, nationality_scope_basis, assertion_mode, conditional_on, needs_lawyer_review, non_obvious, quote_verbatim_confirmed`. **None of the metadata keys exist in the snapshot**, so `snapshot.get("persona") != "third-country professional"` → `False` on the first metadata key → **the fact is dropped. All 38 would be dropped.** The batch would load and serve nothing.

### Finding B — nationality is compared country-vs-label, and audience_scope is ignored
Even the one legitimately-shared key fails: `snapshot["nationality"]` is a **country** (`"Venezuela"`) while the batch says `"non-EEA"` (a class). `"Venezuela" != "non-EEA"` → dropped. And the matcher has no notion of `nationality_scope_basis`, so if it *did* match, it would hide the **17 `audience_scope`** rules (Emergency Tax, PPSN, tax residence…) from an EEA mover — the exact failure the S1 audit exists to prevent.

### Finding C — there are TWO serving systems (the real decision)
| | System A (where our batch lands) | System B (the mature one) |
|---|---|---|
| Data | `requirement_facts.applies_to` | `requirement_blocks` / `corridor_requirements` (`applies_to_nationality_classes_json`) |
| Filter | `_apply_applies_to` (naive equality) | `rules_engine` + `requirements_builder` + `public_corridor` |
| Nationality logic | none | **`nationality_class.py` — `classify()` → `EU_EEA` / `THIRD_COUNTRY` / `OWN_NATIONAL`**, with an explicit anti-silence contract ("state the nothing-required result") |
| Fed by | Otto NDJSON → `otto-loader` | the `data/corridor-facts/*.jsonl` representation |

System B **already** encodes the EEA/third-country distinction our S1 audit reinvented, and already handles it correctly. System A is primitive. This is the same overlap Phase 6 flags — now with a concrete consequence: **which system should serve the ES→IE corridor?**

---

## 2. The fork you need to decide (blocks the final shape of Phase 5)

- **Option A — harden System A.** Fix `_apply_applies_to` to respect targeting-vs-metadata keys and `nationality_scope_basis`, and serve facts from `requirement_facts`. Smaller change, keeps the batch on its current loader path. §3 drafts this.
- **Option B — route the corridor through System B.** Treat System B (nationality-class-aware blocks) as canonical; the batch's value feeds `requirement_blocks` instead. Bigger, but you stop maintaining two matchers and inherit the anti-silence contract for free.

My recommendation: **do Option A now** (it's the path the batch is already built for, and it unblocks correct serving quickly), and put the A-vs-B consolidation on the Phase 6 editorial-reconciliation table rather than blocking on it. The Option A matcher below is deliberately written to reuse System B's `nationality_class.classify`, so it's a step toward B, not away from it.

---

## 3. Proposed change (Option A) — `requirements_sufficiency.py`

Replace the matcher with a targeting-key allowlist + scope-aware nationality handling. Metadata keys never filter; `nationality` gates only when the rule is `nationality_determined`; the mover's country is mapped to a class before comparison.

```python
from .nationality_class import EU_EEA, THIRD_COUNTRY, classify_best

# Only these applies_to keys gate applicability. Everything else the batch carries
# (persona, topic, nationality_scope_basis, assertion_mode, conditional_on, non_obvious,
# needs_lawyer_review, quote_*) is provenance/metadata and MUST NOT filter a fact out.
_TARGETING_KEYS = ("nationality", "status", "employee_profile")

# Batch nationality vocabulary -> nationality_class.classify() output.
_NAT_LABEL_TO_CLASS = {"non-EEA": THIRD_COUNTRY, "non-EU": THIRD_COUNTRY,
                       "EEA": EU_EEA, "EU": EU_EEA}

def _nationality_applies(applies_to, snapshot) -> bool:
    # audience_scope = nationality-neutral rule shown to a non-EEA audience -> applies to everyone.
    if applies_to.get("nationality_scope_basis") == "audience_scope":
        return True
    want = applies_to.get("nationality")
    if not want:
        return True
    want_class = _NAT_LABEL_TO_CLASS.get(want)
    if want_class is None:                      # unknown label -> fail OPEN (show), log
        log.warning("unknown applies_to.nationality=%r; not gating", want)
        return True
    mover_class = classify_best(
        (snapshot.get("nationality"), snapshot.get("second_nationality")),
        snapshot.get("destination_country"),
    )
    if mover_class is None:                      # unknown mover nationality -> show (anti-silence)
        return True
    return mover_class == want_class

def _apply_applies_to(applies_to, snapshot) -> bool:
    if not applies_to:
        return True
    for key in _TARGETING_KEYS:
        if key not in applies_to:
            continue
        if key == "nationality":
            if not _nationality_applies(applies_to, snapshot):
                return False
            continue
        # status / employee_profile: gate only when the snapshot actually carries the field,
        # else fail OPEN (the snapshot has no 'status' today, so this is a no-op until it does).
        snap_val = snapshot.get(key)
        if snap_val is not None and snap_val != applies_to[key]:
            return False
    return True
```

And extend the served item so the UI can render conditional + trap content (currently it only passes `fact_text`/`source_url`/`required_fields`):

```python
supporting_requirements.append({
    "fact_id": fact.get("id"),
    "fact_text": fact.get("fact_text"),
    "source_url": fact.get("source_url"),
    "required_fields": fact.get("required_fields") or [],
    # NEW — from applies_to, for correct rendering:
    "assertion_mode": (fact.get("applies_to") or {}).get("assertion_mode"),      # "conditional" -> render conditionally
    "conditional_on": (fact.get("applies_to") or {}).get("conditional_on"),
    "non_obvious": (fact.get("applies_to") or {}).get("non_obvious", False),     # -> "easy to miss" trap styling
})
```

**Scope of the code change is small and contained:** for System A, `_apply_applies_to` is the *only* fact matcher (the other `applies_to*` hits — `case_context_service`, `requirements_builder`, `public_corridor`, `requirement_evaluation_service` — operate on System B's blocks/roles, not `requirement_facts`). The router `requirement_facts.py` is superseded (writes to a dead-end candidates table) and is out of scope.

## 4. Regression risk to call out
The new matcher also changes behavior for **existing** `requirement_facts`. The old code hard-filtered on every key, so any existing fact whose `applies_to` had a key the snapshot lacks (`route`, `employee_profile: "all"`, …) was being silently dropped. The new matcher shows those. That's mostly a *fix* (it's the `employee_profile:"all"` over-scoping otto flagged), but it is a live behavior change and must be regression-tested, not just unit-tested on the new batch.

## 5. Test plan (TDD — write these first)
Fixture: the 38-record batch as the fact list + synthetic snapshots. (Note: `docs/esie-andrea-golden-fixture.md` that the batch README references does **not** exist in the clone — I'll create a minimal one from the batch.)

1. **Andrea (non-EEA professional, dest IE):** all 38 records apply (21 nationality_determined + 17 audience_scope), given dest/status match.
2. **Spanish (EEA) professional, dest IE:** the **17 audience_scope** rules still apply; the **21 nationality_determined** do **not**. ← the core anti-mis-serve assertion.
3. **Conditional records** (`assertion_mode: conditional`) are **included**, with `assertion_mode`/`conditional_on` passed through (not filtered).
4. **No metadata key** (`persona`, `topic`, `nationality_scope_basis`, …) causes a false drop.
5. **Regression:** a representative existing fact still serves as before (guard against the §4 change surprising a live corridor).

Proposed location: `backend/tests/test_requirements_sufficiency_scope.py` (runs in the existing backend pytest lane).

## 6. Open decisions for you
1. **A vs B** (§2) — harden System A now (my rec) or route ES→IE through System B. Determines whether this is the final matcher or an interim one.
2. **`status` gating** — the snapshot has `employment_type`, not `status`; the batch is 100% `professional`. OK to leave status fail-open (my draft), or map `status`→`employment_type`?
3. **Frontend rendering** of `assertion_mode`/`non_obvious` — in scope for Phase 5, or a separate 5b once the backend passes the fields through?

## 7. What I can do on your go
- Implement §3 + §5 as a reviewable change (with the golden fixture created from the batch), TypeScript/pytest green, `check_serving_llm_isolation` untouched — delivered files-on-disk for you to commit, same as Phase 2/3.
- It's testable end-to-end only after promotion (Phase 4), but the unit/regression tests stand on their own now.
