"""
Conjoint persistence — Parker Step H.

Thin, portable (Postgres + SQLite) data access over the three conjoint tables, mirroring
the ``ai_unit_economics`` access style: ``app/db.py`` SessionLocal + raw ``text()`` SQL,
Python-generated text UUIDs (so the test path needs no Postgres-only ``gen_random_uuid``),
and JSON columns serialised in/out with ``json`` (Postgres jsonb accepts the text via the
text→jsonb assignment cast; SQLite stores it as text).

Also bridges learned utilities into Step B's ``benefit_priors`` table when present
(best-effort: a no-op + TODO log when B is unmerged and the table is absent).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from . import conjoint_service as svc

log = logging.getLogger(__name__)

# Fixed design parameters per study — a balanced-random design is sufficient for an
# aggregate MNL (see conjoint_service.design_study). All respondents see the same design.
CHOICE_SETS_PER_STUDY = 10
N_ALTS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _choice_set_hash(alternatives: List[Dict[str, str]]) -> str:
    canonical = json.dumps(alternatives, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Studies                                                                      #
# --------------------------------------------------------------------------- #


def create_study(
    session: Any,
    *,
    company_id: str,
    name: Optional[str],
    attributes: Dict[str, List[str]],
    n_responses_target: int = 100,
    status: str = "draft",
) -> Dict[str, Any]:
    study_id = _new_id()
    session.execute(
        text(
            "INSERT INTO conjoint_studies "
            "(id, company_id, name, status, attributes_json, n_responses_target, created_at) "
            "VALUES (:id, :cid, :name, :status, :attrs, :target, :now)"
        ),
        {
            "id": study_id,
            "cid": company_id,
            "name": name,
            "status": status,
            "attrs": json.dumps(attributes, separators=(",", ":")),
            "target": int(n_responses_target),
            "now": _now(),
        },
    )
    return {
        "id": study_id,
        "company_id": company_id,
        "name": name,
        "status": status,
        "attributes": attributes,
        "n_responses_target": int(n_responses_target),
    }


def get_study(session: Any, study_id: str) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text(
            "SELECT id, company_id, name, status, attributes_json, n_responses_target "
            "FROM conjoint_studies WHERE id = :id"
        ),
        {"id": study_id},
    ).first()
    if row is None:
        return None
    return {
        "id": row[0],
        "company_id": row[1],
        "name": row[2],
        "status": row[3],
        "attributes": _loads(row[4]) or {},
        "n_responses_target": row[5],
    }


# --------------------------------------------------------------------------- #
# Choice sets + responses                                                      #
# --------------------------------------------------------------------------- #


def _study_design(study: Dict[str, Any]) -> List[svc.ChoiceSet]:
    # Deterministic per study so every respondent sees the same balanced design.
    seed = int(hashlib.sha256(str(study["id"]).encode("utf-8")).hexdigest(), 16) % (2**32)
    return svc.design_study(
        study["attributes"], CHOICE_SETS_PER_STUDY, n_alts=N_ALTS, seed=seed
    )


def next_choice_set_for_respondent(
    session: Any, study: Dict[str, Any], respondent_user_id: str
) -> Optional[Dict[str, Any]]:
    """Return the next unanswered choice set for this respondent (or None when done)."""
    answered = {
        r[0]
        for r in session.execute(
            text(
                "SELECT choice_set_hash FROM conjoint_responses "
                "WHERE study_id = :sid AND respondent_user_id = :uid"
            ),
            {"sid": study["id"], "uid": respondent_user_id},
        ).all()
    }
    for idx, cs in enumerate(_study_design(study)):
        h = _choice_set_hash(cs.alternatives)
        if h not in answered:
            return {"index": idx, "choice_set_hash": h, "alternatives": cs.alternatives}
    return None


def record_response(
    session: Any,
    *,
    study_id: str,
    respondent_user_id: str,
    alternatives: List[Dict[str, str]],
    chosen_index: int,
) -> Dict[str, Any]:
    """Persist a respondent's pick. Idempotent on (study, respondent, choice-set hash)."""
    h = _choice_set_hash(alternatives)
    existing = session.execute(
        text(
            "SELECT id FROM conjoint_responses "
            "WHERE study_id = :sid AND respondent_user_id = :uid AND choice_set_hash = :h"
        ),
        {"sid": study_id, "uid": respondent_user_id, "h": h},
    ).first()
    if existing is not None:
        return {"id": existing[0], "deduplicated": True}

    resp_id = _new_id()
    session.execute(
        text(
            "INSERT INTO conjoint_responses "
            "(id, study_id, respondent_user_id, choice_set_json, choice_set_hash, "
            " chosen_index, responded_at) "
            "VALUES (:id, :sid, :uid, :csj, :h, :ci, :now)"
        ),
        {
            "id": resp_id,
            "sid": study_id,
            "uid": respondent_user_id,
            "csj": json.dumps(alternatives, separators=(",", ":")),
            "h": h,
            "ci": int(chosen_index),
            "now": _now(),
        },
    )
    return {"id": resp_id, "deduplicated": False}


def load_responses(session: Any, study_id: str) -> List[svc.Response]:
    rows = session.execute(
        text(
            "SELECT choice_set_json, chosen_index FROM conjoint_responses "
            "WHERE study_id = :sid"
        ),
        {"sid": study_id},
    ).all()
    out: List[svc.Response] = []
    for cs_json, chosen in rows:
        alts = _loads(cs_json)
        if isinstance(alts, list) and chosen is not None:
            out.append(svc.Response(choice_set=alts, chosen_index=int(chosen)))
    return out


# --------------------------------------------------------------------------- #
# Results                                                                      #
# --------------------------------------------------------------------------- #


def save_results(
    session: Any,
    *,
    study_id: str,
    part_worths: Dict[str, Any],
    fit_quality: Dict[str, Any],
) -> Dict[str, Any]:
    res_id = _new_id()
    session.execute(
        text(
            "INSERT INTO conjoint_results "
            "(id, study_id, part_worths_json, fit_quality_json, computed_at) "
            "VALUES (:id, :sid, :pw, :fq, :now)"
        ),
        {
            "id": res_id,
            "sid": study_id,
            "pw": json.dumps(part_worths, separators=(",", ":")),
            "fq": json.dumps(fit_quality, separators=(",", ":")),
            "now": _now(),
        },
    )
    return {"id": res_id, "part_worths": part_worths, "fit_quality": fit_quality}


def load_results(session: Any, study_id: str) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text(
            "SELECT part_worths_json, fit_quality_json, computed_at FROM conjoint_results "
            "WHERE study_id = :sid ORDER BY computed_at DESC LIMIT 1"
        ),
        {"sid": study_id},
    ).first()
    if row is None:
        return None
    return {
        "part_worths": _loads(row[0]) or {},
        "fit_quality": _loads(row[1]) or {},
        "computed_at": row[2],
    }


# --------------------------------------------------------------------------- #
# Bridge into Step B's benefit_priors (best-effort)                            #
# --------------------------------------------------------------------------- #


def push_to_benefit_priors(
    session: Any,
    *,
    company_id: str,
    part_worths: Dict[str, Dict[str, float]],
) -> int:
    """Upsert learned part-worths into Step B's ``benefit_priors`` as ``source='conjoint'``.

    Maps each (attribute, level) → a ``(company_id, category=attribute, attr_key=level)``
    row with ``expected_satisfaction`` = the part-worth. Best-effort: if the table does
    not exist yet (Step B unmerged), logs a TODO and returns 0 without raising.
    """
    rows = [
        (attr, level, float(pw))
        for attr, levels in part_worths.items()
        for level, pw in levels.items()
    ]
    if not rows:
        return 0
    written = 0
    try:
        for attr, level, pw in rows:
            session.execute(
                text(
                    "INSERT INTO benefit_priors "
                    "(company_id, category, attr_key, expected_satisfaction, source, updated_at) "
                    "VALUES (:cid, :cat, :ak, :es, 'conjoint', :now) "
                    "ON CONFLICT (company_id, category, attr_key) DO UPDATE SET "
                    "expected_satisfaction = EXCLUDED.expected_satisfaction, "
                    "source = 'conjoint', updated_at = EXCLUDED.updated_at"
                ),
                {"cid": company_id, "cat": attr, "ak": level, "es": pw, "now": _now()},
            )
            written += 1
    except Exception:
        # TODO(Parker-H): activate once Step B's benefit_priors migration is applied.
        log.info(
            "conjoint: benefit_priors bridge skipped (table absent / Step B unmerged) "
            "for company_id=%s — %d part-worths not pushed",
            company_id,
            len(rows),
        )
        return 0
    return written
