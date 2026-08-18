"""[AIQ-1880] Put a confirmed nationality where the requirements gate can read it.

`rules_engine.py` resolves a case's nationality class from exactly one location:

    wizard_cases.draft_json -> employeeProfile.nationality

Everything else that knows a nationality — the immigration intake profile, passport OCR,
`imm_employee_profiles.nationality` — is invisible to it. So a case could have a scanned
passport on file and still gate as "unknown".

That matters because `rules_engine` fail-safes an unknown nationality to THIRD_COUNTRY
(`effective_class = nationality_class or THIRD_COUNTRY`) while reporting no class and
waiving nothing. It over-shows rather than under-shows, which is the correct safety
posture — but it means the engine is guessing, and a guess is only right by luck. Case
6ecadafe-…e323cf51 (ES->IE) is Venezuelan: THIRD_COUNTRY happens to be her real class, so
her dossier looks right while nothing determined it.

This module is the one writer. It is deliberately small and deliberately conservative.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .. import crud

log = logging.getLogger(__name__)

_EMPTY_DRAFT: Dict[str, Any] = {
    "relocationBasics": {},
    "employeeProfile": {},
    "familyMembers": {},
    "assignmentContext": {},
}


def _load_draft(raw: Optional[str]) -> Dict[str, Any]:
    """Parse a draft, degrading to an empty one rather than raising.

    A malformed draft must not make a nationality unrecordable — but it also must not be
    silently replaced, so the failure is logged.
    """
    if not raw:
        return dict(_EMPTY_DRAFT)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        log.warning("nationality_sync: unparseable draft_json; starting from an empty draft")
        return dict(_EMPTY_DRAFT)
    return parsed if isinstance(parsed, dict) else dict(_EMPTY_DRAFT)


def sync_nationality_to_case(db: Session, case_id: str, nationality: Optional[str]) -> bool:
    """Merge `nationality` into the case's wizard draft so the gate can read it.

    Returns True when the draft now carries this value, False when the call was a no-op.

    Two rules, both intentional:

    * **A non-empty existing value is never overwritten.** The write paths are ordered
      by trust, not by recency: an HR correction must outrank a later OCR read of the
      same passport. Clobbering a human's correction with a machine's guess is the
      failure this guards, and it would be invisible — the value would simply be wrong.

    * **A missing wizard row is created.** 809 of 1,524 `relocation_cases` have no
      `wizard_cases` row at all; skipping them would help only the cases that were
      already fine. The caller has authorised the case before reaching here (the
      employee path gates on consent, the HR path on the company tenant check), so
      there is no unauthorised id to create a row for.

    The value is stored as given, trimmed. Normalisation belongs to
    `nationality_class._nationality_to_iso`, which already handles ISO codes, aliases,
    full names and adjectival forms — duplicating it here would give two answers to the
    same question. An unrecognised string stays unrecognised and the gate makes no claim,
    which is the documented behaviour.
    """
    value = (nationality or "").strip()
    if not value:
        return False

    case = crud.get_case(db, case_id)

    if case is None:
        draft = dict(_EMPTY_DRAFT)
        draft["employeeProfile"] = {"nationality": value}
        crud.create_case(db, case_id, draft)
        return True

    draft = _load_draft(case.draft_json)
    profile = draft.get("employeeProfile")
    if not isinstance(profile, dict):
        profile = {}

    if (profile.get("nationality") or "").strip():
        return False

    profile["nationality"] = value
    draft["employeeProfile"] = profile
    case.draft_json = json.dumps(draft)
    db.commit()
    return True
