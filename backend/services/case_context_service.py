"""
CaseContextService — deterministic assembly of mobility graph context (no AI).

Reads public.mobility_cases, case_people, case_documents, policy_rules,
requirements_catalog, case_requirement_evaluations.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

log = logging.getLogger(__name__)


class CaseContextError(Exception):
    """Non-fatal context assembly issue (e.g. schema missing)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _strip_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_uuid(case_id_raw: Optional[str]) -> Optional[uuid.UUID]:
    s = _strip_str(case_id_raw)
    if not s:
        return None
    try:
        return uuid.UUID(s)
    except (ValueError, AttributeError):
        return None


def _coerce_json(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            out = json.loads(s)
            return dict(out) if isinstance(out, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            return None
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def _row_to_plain(row: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    d: Dict[str, Any] = {}
    for key, value in dict(row).items():
        k = str(key)
        if k in ("metadata", "conditions"):
            d[k] = _coerce_json(value)
        else:
            d[k] = _serialize_value(value)
    return d


def _case_match_ok(match: Mapping[str, Any], case_row: Mapping[str, Any]) -> bool:
    if not match:
        return True
    for key, expected in match.items():
        if expected is None:
            continue
        actual = case_row.get(key)
        if actual is None:
            return False
        if str(actual) != str(expected):
            return False
    return True


def _metadata_subset_ok(spec: Mapping[str, Any], case_metadata: Mapping[str, Any]) -> bool:
    for key, expected in spec.items():
        if case_metadata.get(key) != expected:
            return False
    return True


def _only_if_ok(only_if: Any, case_metadata: Mapping[str, Any]) -> bool:
    if only_if is None or only_if == {}:
        return True
    if not isinstance(only_if, dict):
        return True
    cm_spec = only_if.get("case_metadata")
    if cm_spec is None:
        return True
    if not isinstance(cm_spec, dict):
        return True
    return _metadata_subset_ok(cm_spec, case_metadata)


def _roles_overlap(applies_to_roles: Any, people: Sequence[Mapping[str, Any]]) -> bool:
    if applies_to_roles is None:
        return True
    if not isinstance(applies_to_roles, list):
        return True
    if len(applies_to_roles) == 0:
        return True
    allowed = {str(r) for r in applies_to_roles}
    for p in people:
        role = p.get("role")
        if role is not None and str(role) in allowed:
            return True
    return False


def _rule_applies(
    conditions: Mapping[str, Any],
    case_row: Mapping[str, Any],
    people: Sequence[Mapping[str, Any]],
) -> bool:
    case_plain = {k: case_row.get(k) for k in case_row.keys()}
    meta = _coerce_json(case_plain.get("metadata"))
    match = conditions.get("match") if isinstance(conditions, dict) else None
    if not isinstance(match, dict):
        match = {}
    if not _case_match_ok(match, case_plain):
        return False
    only_if = conditions.get("only_if") if isinstance(conditions, dict) else None
    if not _only_if_ok(only_if, meta):
        return False
    applies_to_roles = conditions.get("applies_to_roles") if isinstance(conditions, dict) else None
    if not _roles_overlap(applies_to_roles, people):
        return False
    return True


class CaseContextService:
    """Loads and normalizes mobility case graph context for a single case."""

    def fetch(self, conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
        uid = _parse_uuid(case_id_raw)
        base: Dict[str, Any] = {
            "meta": {
                "ok": True,
                "case_id": str(uid) if uid else None,
                "case_found": False,
                "error": None,
            },
            "case": None,
            "people": [],
            "documents": [],
            "applicable_rules": [],
            "requirements": [],
            "evaluations": [],
        }

        if uid is None:
            base["meta"]["ok"] = False
            base["meta"]["error"] = {"code": "invalid_case_id", "message": "case_id must be a valid UUID"}
            return base

        case_id_str = str(uid)

        try:
            case_row = conn.execute(
                text(
                    """
                    SELECT id, company_id, employee_user_id, origin_country, destination_country,
                           case_type, metadata, created_at, updated_at
                    FROM mobility_cases
                    WHERE id = :case_id
                    LIMIT 1
                    """
                ),
                {"case_id": case_id_str},
            ).mappings().first()
        except ProgrammingError as ex:
            log.warning("CaseContextService: mobility schema unavailable: %s", ex)
            raise CaseContextError(
                "mobility_schema_unavailable",
                "mobility_cases (or database) not available for this environment",
            ) from ex

        case = _row_to_plain(case_row)
        if not case:
            return base

        base["meta"]["case_found"] = True
        base["case"] = case

        try:
            people = self._fetch_people(conn, case_id_str)
            documents = self._fetch_documents(conn, case_id_str)
            evaluations = self._fetch_evaluations(conn, case_id_str)

            base["people"] = people
            base["documents"] = documents
            base["evaluations"] = evaluations

            all_rules = self._fetch_all_policy_rules(conn)
            applicable: List[Dict[str, Any]] = []
            for rule in all_rules:
                cond = rule.get("conditions")
                if not isinstance(cond, dict):
                    cond = {}
                if _rule_applies(cond, case, people):
                    applicable.append(rule)

            base["applicable_rules"] = applicable

            req_codes = self._collect_requirement_codes(applicable)
            req_ids_from_eval = self._collect_requirement_ids(evaluations)
            requirements = self._fetch_requirements_catalog(conn, req_codes, req_ids_from_eval)
            base["requirements"] = requirements

            code_by_id: Dict[str, Any] = {}
            for r in requirements:
                rid = r.get("id")
                if rid is not None:
                    code_by_id[str(rid)] = r.get("requirement_code")
            for ev in base["evaluations"]:
                rid = ev.get("requirement_id")
                if rid is not None and str(rid) in code_by_id:
                    ev["requirement_code"] = code_by_id[str(rid)]
        except ProgrammingError as ex:
            log.warning("CaseContextService: related mobility tables missing: %s", ex)
            raise CaseContextError(
                "mobility_schema_unavailable",
                "mobility graph tables incomplete or unavailable",
            ) from ex

        return base

    def _fetch_people(self, conn: Connection, case_id_str: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text(
                """
                SELECT id, case_id, role, metadata, created_at, updated_at
                FROM case_people
                WHERE case_id = :case_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"case_id": case_id_str},
        ).mappings().all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            p = _row_to_plain(row)
            if p:
                out.append(p)
        return out

    def _fetch_documents(self, conn: Connection, case_id_str: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text(
                """
                SELECT id, case_id, person_id, document_key, document_status, metadata, created_at, updated_at
                FROM case_documents
                WHERE case_id = :case_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"case_id": case_id_str},
        ).mappings().all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            d = _row_to_plain(row)
            if d:
                out.append(d)
        return out

    def _fetch_evaluations(self, conn: Connection, case_id_str: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text(
                """
                SELECT id, case_id, person_id, requirement_id, source_rule_id,
                       evaluation_status, reason_text, evaluated_at, evaluated_by,
                       created_at, updated_at
                FROM case_requirement_evaluations
                WHERE case_id = :case_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"case_id": case_id_str},
        ).mappings().all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            e = _row_to_plain(row)
            if e:
                out.append(e)
        return out

    def _fetch_all_policy_rules(self, conn: Connection) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text(
                """
                SELECT id, rule_code, conditions, metadata, created_at, updated_at
                FROM policy_rules
                ORDER BY rule_code ASC, id ASC
                """
            ),
        ).mappings().all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            r = _row_to_plain(row)
            if r:
                out.append(r)
        return out

    def _collect_requirement_codes(self, applicable_rules: Sequence[Mapping[str, Any]]) -> List[str]:
        codes: List[str] = []
        seen: set[str] = set()
        for rule in applicable_rules:
            cond = rule.get("conditions")
            if not isinstance(cond, dict):
                continue
            raw = cond.get("requires_requirement_codes")
            if not isinstance(raw, list):
                continue
            for c in raw:
                if c is None:
                    continue
                s = str(c).strip()
                if s and s not in seen:
                    seen.add(s)
                    codes.append(s)
        return codes

    def _collect_requirement_ids(self, evaluations: Sequence[Mapping[str, Any]]) -> List[str]:
        ids: List[str] = []
        seen: set[str] = set()
        for ev in evaluations:
            rid = ev.get("requirement_id")
            if rid is None:
                continue
            s = str(rid).strip()
            if s and s not in seen:
                seen.add(s)
                ids.append(s)
        return ids

    def _fetch_requirements_catalog(
        self,
        conn: Connection,
        codes: Sequence[str],
        requirement_ids: Sequence[str],
    ) -> List[Dict[str, Any]]:
        if not codes and not requirement_ids:
            return []
        p2: Dict[str, Any] = {}
        for k, c in enumerate(codes):
            p2[f"c{k}"] = c
        for k, rid in enumerate(requirement_ids):
            p2[f"r{k}"] = rid
        if not codes:
            sql = f"""
                SELECT id, requirement_code, metadata, created_at, updated_at
                FROM requirements_catalog
                WHERE id IN ({", ".join(f":r{k}" for k in range(len(requirement_ids)))})
                ORDER BY requirement_code ASC, id ASC
            """
        elif not requirement_ids:
            sql = f"""
                SELECT id, requirement_code, metadata, created_at, updated_at
                FROM requirements_catalog
                WHERE requirement_code IN ({", ".join(f":c{k}" for k in range(len(codes)))})
                ORDER BY requirement_code ASC, id ASC
            """
        else:
            sql = f"""
                SELECT DISTINCT id, requirement_code, metadata, created_at, updated_at
                FROM requirements_catalog
                WHERE requirement_code IN ({", ".join(f":c{k}" for k in range(len(codes)))})
                   OR id IN ({", ".join(f":r{k}" for k in range(len(requirement_ids)))})
                ORDER BY requirement_code ASC, id ASC
            """

        rows = conn.execute(text(sql), p2).mappings().all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            r = _row_to_plain(row)
            if r:
                out.append(r)
        return out


def fetch_case_context(conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
    """Convenience wrapper."""
    return CaseContextService().fetch(conn, case_id_raw)
