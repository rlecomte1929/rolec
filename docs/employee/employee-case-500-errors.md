# Employee case flow — 500 errors & fixes

## `/api/requirements/sufficiency?case_id=…`

| | |
|--|--|
| **Purpose** | Compute **destination requirement sufficiency**: merge case draft + dossier answers into a profile snapshot, apply approved requirement facts, return `missing_fields` and supporting citations. |
| **Typical 500 causes (fixed / mitigated)** | 1. **`json.loads(case.draft_json)`** on corrupt/non-JSON `draft_json` → raised **`JSONDecodeError`** (subclass of `ValueError`). Handler re-raised non–“Case not found” `ValueError` → **500**. **Fix:** `_safe_parse_case_draft()` in `requirements_sufficiency.py` never raises; invalid JSON becomes `{}`. 2. **`effective["id"]`** when user dict lacked `id` → **KeyError** in `_require_case_access` before handler body. **Fix:** use `effective.get("id")` and 401 if missing in sufficiency handler; same pattern in assignment visibility helpers. |
| **Classification** | Mix of **backend bug** (error handling) + possible **data issue** (bad JSON in DB). |
| **Response shape (after fix)** | Always JSON 200 with `compute_status`: `ok` \| `insufficient_data` \| `unavailable`, optional `message`, plus `missing_fields` / `supporting_requirements`. **404** only when case truly not found for authorized user. |
| **Fallback** | Frontend shows a **degraded banner** on non-`ok` / network error; dossier gating still works off empty `approvedMissingFields` if needed. |

---

## `GET /api/assignments/{assignment_id}/timeline?ensure_defaults=1&…`  
## `GET /api/cases/{case_id}/timeline?ensure_defaults=1&…`

| | |
|--|--|
| **Purpose** | List `case_milestones`; optionally **insert default rows** when none exist (`ensure_defaults`). |
| **Typical 500 causes (mitigated)** | 1. **`json.loads` on `draft_json`** inside ensure block → uncaught. **Fix:** try/except + dict guard. 2. **`upsert_case_milestone` failure** (constraint, DB, RLS via service layer) aborting whole request. **Fix:** per-row try/log + outer try/log; handler still returns listed milestones (possibly empty). 3. **Rare:** unexpected errors in `list_case_services` — already swallowed; ensure block wrapped entirely. |
| **Classification** | **Backend robustness**; some **data/DB** edge cases. |
| **Fallback** | HTTP **200** with empty milestones + zeroed summary when ensure fails; client shows “No tasks yet” / retry / “Create default plan”. |

---

## Frontend-trigger notes

| Behavior | Assessment |
|----------|------------|
| Calling sufficiency with **wrong id** | Should not happen for Step 5 (`caseId` from resolved case). |
| `ensure_defaults` on every navigation | **Reduced** for employee My Case via `deferredEnsureWhenEmpty` + session flag. HR case page still passes **`ensureDefaults`** explicitly. |

---

## Authorization / scoping

No change to **who** may see a case: only visibility checks were hardened to **avoid KeyError** and return proper **401/403** instead of **500**.
