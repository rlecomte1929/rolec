"""[AUDIT-C1.3] Policies-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class. They live here as a
mixin (:class:`PoliciesMixin`) that ``Database`` inherits, so every existing
caller (``db.list_policy_benefit_rules(...)`` etc.) keeps working unchanged via
normal MRO. The methods reference instance state (``self.engine``) and sibling
helpers (``self._rows_to_list``, ``self._parse_json_col``) which resolve on the
composed ``Database`` instance — not on this class in isolation.

Extraction is incremental (AUDIT-C1.3, batch 1 of N), mirroring the proven
AUDIT-C1.2 ``CasesMixin`` pattern. This first batch holds the low-coupling
``list_policy_*`` readers (policy-version child tables). Remaining policies-domain
methods (policy_document/version/config writers, requirement_* adapters) follow
the same pattern. None of the methods in this batch need module-level helpers
from database.py, which keeps this module free of any import cycle back to it.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
# [AUDIT-C1.6a] imports for appended policies methods
from typing import Callable
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError

log = logging.getLogger(__name__)


class PoliciesMixin:
    """Policies-domain methods mixed into :class:`backend.database.Database`."""

    def list_policy_benefit_rules(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_benefit_rules WHERE policy_version_id = :vid ORDER BY benefit_key"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "metadata_json")
        return items

    def list_policy_exclusions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_exclusions WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_evidence_requirements(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_evidence_requirements WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "evidence_items_json")
        return items

    def list_policy_rule_conditions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_rule_conditions WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "condition_value_json")
        return items

    def list_policy_family_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_family_status_applicability WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_tier_overrides(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_tier_overrides WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "override_limits_json")
        return items

    # ── policy_versions lifecycle (AUDIT-C1.3 batch 2) ───────────────────────

    def get_latest_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid ORDER BY version_number DESC, created_at DESC LIMIT 1"),
                {"pid": policy_id},
            ).fetchone()
        d = self._row_to_dict(row)
        self._decode_policy_version_row(d)
        return d

    def get_published_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest published version. Employees see only published policies."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid AND status = 'published' ORDER BY version_number DESC, created_at DESC LIMIT 1"),
                {"pid": policy_id},
            ).fetchone()
        d = self._row_to_dict(row)
        self._decode_policy_version_row(d)
        return d

    def update_policy_version_status(self, version_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE policy_versions SET status = :s, updated_at = :now WHERE id = :id"),
                {"id": version_id, "s": status, "now": datetime.utcnow().isoformat()},
            )

    def archive_other_published_versions(self, policy_id: str, keep_version_id: str) -> int:
        """Set status=archived for all published versions except keep_version_id. Returns count updated."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("""
                    UPDATE policy_versions SET status = 'archived', updated_at = :now
                    WHERE policy_id = :pid AND status = 'published' AND id != :keep
                """),
                {"pid": policy_id, "keep": keep_version_id, "now": datetime.utcnow().isoformat()},
            )
            return r.rowcount

    def archive_all_published_versions(self, policy_id: str) -> int:
        """Set status=archived for all published versions of this policy (unpublish). Returns count updated."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("""
                    UPDATE policy_versions SET status = 'archived', updated_at = :now
                    WHERE policy_id = :pid AND status = 'published'
                """),
                {"pid": policy_id, "now": datetime.utcnow().isoformat()},
            )
            return r.rowcount

    def get_policy_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE id = :id"),
                {"id": version_id},
            ).fetchone()
        d = self._row_to_dict(row)
        self._decode_policy_version_row(d)
        return d

    def list_policy_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid ORDER BY version_number DESC"),
                {"pid": policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._decode_policy_version_row(d)
        return items

    def list_policy_versions_by_source_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Versions created from normalization of this policy_documents row (newest first)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT * FROM policy_versions
                    WHERE source_policy_document_id = :did
                    ORDER BY version_number DESC, created_at DESC
                    """
                ),
                {"did": str(document_id)},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._decode_policy_version_row(d)
        return items

    def _decode_policy_version_row(self, d: Optional[Dict[str, Any]]) -> None:
        if not d:
            return
        self._parse_json_col(d, "normalization_draft_json")

    def update_policy_version_normalization_draft(
        self,
        version_id: str,
        draft: Dict[str, Any],
        *,
        request_id: Optional[str] = None,
        normalization_state: Optional[str] = None,
        connection: Any = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        payload = json.dumps(draft, default=str)
        if request_id:
            log.info(
                "request_id=%s policy_versions normalization_draft_json updated version_id=%s bytes=%s",
                request_id,
                version_id,
                len(payload),
            )

        def _upd(conn: Any) -> None:
            if normalization_state is not None:
                conn.execute(
                    text(
                        """
                        UPDATE policy_versions
                        SET normalization_draft_json = :draft, normalization_state = :ns, updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"id": str(version_id), "draft": payload, "now": now, "ns": normalization_state},
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE policy_versions
                        SET normalization_draft_json = :draft, updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"id": str(version_id), "draft": payload, "now": now},
                )

        if connection is not None:
            _upd(connection)
        else:
            with self.engine.begin() as conn:
                _upd(conn)

    # ── policy_documents / clauses CRUD (AUDIT-C1.3 batch 3) ─────────────────

    def policy_version_references_document(self, doc_id: str) -> bool:
        """True if any policy_version has source_policy_document_id = doc_id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM policy_versions WHERE source_policy_document_id = :id LIMIT 1"),
                {"id": doc_id},
            ).fetchone()
        return row is not None

    def delete_policy_document(self, doc_id: str, request_id: Optional[str] = None) -> bool:
        """Delete policy_document and its clauses. Returns True if a row was deleted."""
        self.delete_policy_document_clauses(doc_id, request_id=request_id)
        with self.engine.begin() as conn:
            r = conn.execute(text("DELETE FROM policy_documents WHERE id = :id"), {"id": doc_id})
            return r.rowcount > 0

    def delete_policy_document_clauses(self, doc_id: str, request_id: Optional[str] = None) -> int:
        """Remove all clauses for a document (before re-segment)."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("DELETE FROM policy_document_clauses WHERE policy_document_id = :id"),
                {"id": doc_id},
            )
            return r.rowcount

    def upsert_policy_document_clauses(
        self,
        doc_id: str,
        clauses: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> int:
        """Replace clauses for a document. Deletes existing and inserts new."""
        self.delete_policy_document_clauses(doc_id, request_id=request_id)
        if not clauses:
            return 0
        now = datetime.utcnow().isoformat()
        valid_types = {
            "scope", "eligibility", "benefit", "exclusion", "approval_rule",
            "evidence_rule", "tax_rule", "definition", "lifecycle_rule", "unknown",
        }
        with self.engine.begin() as conn:
            for c in clauses:
                cid = str(uuid.uuid4())
                ctype = str(c.get("clause_type") or "unknown")
                if ctype not in valid_types:
                    ctype = "unknown"
                conn.execute(
                    text("""
                        INSERT INTO policy_document_clauses
                        (id, policy_document_id, section_label, section_path, clause_type,
                         title, raw_text, normalized_hint_json, source_page_start, source_page_end,
                         source_anchor, confidence, created_at, updated_at)
                        VALUES (:id, :doc_id, :sl, :sp, :ct, :title, :raw, :hint,
                                :ps, :pe, :anchor, :conf, :now, :now)
                    """),
                    {
                        "id": cid,
                        "doc_id": doc_id,
                        "sl": c.get("section_label"),
                        "sp": c.get("section_path"),
                        "ct": ctype,
                        "title": c.get("title"),
                        "raw": c.get("raw_text") or "",
                        "hint": json.dumps(c.get("normalized_hint_json")) if c.get("normalized_hint_json") else None,
                        "ps": c.get("source_page_start"),
                        "pe": c.get("source_page_end"),
                        "anchor": c.get("source_anchor"),
                        "conf": float(c.get("confidence", 0.5)),
                        "now": now,
                    },
                )
        return len(clauses)

    def list_policy_document_clauses(
        self,
        doc_id: str,
        clause_type: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM policy_document_clauses WHERE policy_document_id = :id"
        params: Dict[str, Any] = {"id": doc_id}
        if clause_type:
            sql += " AND clause_type = :ct"
            params["ct"] = clause_type
        sql += " ORDER BY source_page_start ASC NULLS LAST, created_at ASC"
        with self.engine.connect() as conn:
            try:
                rows = conn.execute(text(sql), params).fetchall()
            except Exception:
                sql = sql.replace(" NULLS LAST", "")
                rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            if d.get("normalized_hint_json") and isinstance(d["normalized_hint_json"], str):
                try:
                    d["normalized_hint_json"] = json.loads(d["normalized_hint_json"])
                except Exception:
                    d["normalized_hint_json"] = None
        return items

    def get_policy_document_clause(
        self, clause_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_document_clauses WHERE id = :id"),
                {"id": clause_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d and d.get("normalized_hint_json") and isinstance(d["normalized_hint_json"], str):
            try:
                d["normalized_hint_json"] = json.loads(d["normalized_hint_json"])
            except Exception:
                d["normalized_hint_json"] = None
        return d

    def update_policy_document_clause(
        self,
        clause_id: str,
        clause_type: Optional[str] = None,
        title: Optional[str] = None,
        hr_override_notes: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        valid_types = {
            "scope", "eligibility", "benefit", "exclusion", "approval_rule",
            "evidence_rule", "tax_rule", "definition", "lifecycle_rule", "unknown",
        }
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": clause_id, "now": datetime.utcnow().isoformat()}
        if clause_type is not None:
            ctype = clause_type if clause_type in valid_types else "unknown"
            fields.append("clause_type = :ct")
            params["ct"] = ctype
        if title is not None:
            fields.append("title = :title")
            params["title"] = title
        if hr_override_notes is not None:
            fields.append("hr_override_notes = :notes")
            params["notes"] = hr_override_notes
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_document_clauses SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    # ── policy_versions create (AUDIT-C1.3 batch 4) ──────────────────────────

    def create_policy_version(
        self,
        version_id: str,
        policy_id: str,
        source_policy_document_id: Optional[str] = None,
        version_number: int = 1,
        status: str = "auto_generated",
        auto_generated: bool = True,
        review_status: str = "pending",
        confidence: Optional[float] = None,
        created_by: Optional[str] = None,
        request_id: Optional[str] = None,
        *,
        normalization_state: Optional[str] = None,
        connection: Any = None,
    ) -> None:
        # Module-level policy-boolean helpers live in database.py; lazy-import here
        # to avoid an import cycle (database.py imports this module at load time).
        from ..database import _policy_ag_sql, _policy_bool_bind, normalize_policy_boolean_fields
        now = datetime.utcnow().isoformat()
        # Coerce to str for Postgres uuid columns (driver may return UUID from list_company_policies)
        params = {
            "id": str(version_id),
            "pid": str(policy_id),
            "doc_id": str(source_policy_document_id) if source_policy_document_id is not None else None,
            "vn": version_number,
            "status": status,
            "ag": _policy_bool_bind(auto_generated),
            "rs": review_status,
            "conf": confidence,
            "cb": created_by,
            "now": now,
            "ns": normalization_state,
        }
        params = normalize_policy_boolean_fields(params)
        if request_id:
            log.info(
                "request_id=%s policy_versions insert payload keys=%s status=%s auto_generated=%s review_status=%s ag_type=%s doc_id=%s",
                request_id, list(params.keys()), params.get("status"), params.get("ag"),
                params.get("rs"), type(params.get("ag")).__name__, params.get("doc_id"),
            )
        ag_sql = _policy_ag_sql()

        def _ins(conn: Any) -> None:
            conn.execute(
                text(f"""
                    INSERT INTO policy_versions
                    (id, policy_id, source_policy_document_id, version_number, status,
                     auto_generated, review_status, confidence, created_by, created_at, updated_at,
                     normalization_state)
                    VALUES (:id, :pid, :doc_id, :vn, :status, {ag_sql}, :rs, :conf, :cb, :now, :now, :ns)
                """),
                params,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)

    # ── policy benefit-rule / exclusion / condition writers + benefits (AUDIT-C1.3 batch 5) ──

    def update_policy_benefit_rule(
        self,
        rule_id: str,
        amount_value: Optional[float] = None,
        amount_unit: Optional[str] = None,
        currency: Optional[str] = None,
        frequency: Optional[str] = None,
        description: Optional[str] = None,
        review_status: Optional[str] = None,
        benefit_key: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": rule_id, "now": datetime.utcnow().isoformat()}
        if amount_value is not None:
            fields.append("amount_value = :av")
            params["av"] = amount_value
        if amount_unit is not None:
            fields.append("amount_unit = :au")
            params["au"] = amount_unit
        if currency is not None:
            fields.append("currency = :cur")
            params["cur"] = currency
        if frequency is not None:
            fields.append("frequency = :freq")
            params["freq"] = frequency
        if description is not None:
            fields.append("description = :desc")
            params["desc"] = description
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if benefit_key is not None:
            fields.append("benefit_key = :bk")
            params["bk"] = benefit_key
        if metadata_json is not None:
            fields.append("metadata_json = :meta")
            params["meta"] = json.dumps(metadata_json)
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_benefit_rules SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def update_policy_exclusion(
        self,
        excl_id: str,
        description: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": excl_id, "now": datetime.utcnow().isoformat()}
        if description is not None:
            fields.append("description = :desc")
            params["desc"] = description
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_exclusions SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def update_policy_rule_condition(
        self,
        cond_id: str,
        condition_value_json: Optional[Dict[str, Any]] = None,
        review_status: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": cond_id, "now": datetime.utcnow().isoformat()}
        if condition_value_json is not None:
            fields.append("condition_value_json = :val")
            params["val"] = json.dumps(condition_value_json)
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_rule_conditions SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def get_policy_benefit_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_benefit_rules WHERE id = :id"),
                {"id": rule_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            self._parse_json_col(d, "metadata_json")
        return d

    def list_policy_benefits(self, policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_extracted_benefits WHERE policy_id = :pid ORDER BY service_category, benefit_label"),
                {"pid": policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            try:
                item["eligibility"] = json.loads(item.get("eligibility") or "null")
            except Exception:
                item["eligibility"] = None
            try:
                item["limits"] = json.loads(item.get("limits") or "null")
            except Exception:
                item["limits"] = None
        return items

    def replace_policy_benefits(
        self,
        policy_id: str,
        benefits: List[Dict[str, Any]],
        updated_by: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM policy_extracted_benefits WHERE policy_id = :pid"), {"pid": policy_id})
            for item in benefits:
                conn.execute(
                    text(
                        "INSERT INTO policy_extracted_benefits "
                        "(id, policy_id, service_category, benefit_key, benefit_label, eligibility, limits, notes, "
                        "source_quote, source_section, confidence, updated_by, updated_at) "
                        "VALUES (:id, :pid, :cat, :key, :label, :elig, :limits, :notes, :quote, :section, :conf, :ub, :ua)"
                    ),
                    {
                        "id": item.get("id") or str(uuid.uuid4()),
                        "pid": policy_id,
                        "cat": item.get("service_category"),
                        "key": item.get("benefit_key"),
                        "label": item.get("benefit_label"),
                        "elig": json.dumps(item.get("eligibility")) if item.get("eligibility") is not None else None,
                        "limits": json.dumps(item.get("limits")) if item.get("limits") is not None else None,
                        "notes": item.get("notes"),
                        "quote": item.get("source_quote"),
                        "section": item.get("source_section"),
                        "conf": item.get("confidence"),
                        "ub": updated_by,
                        "ua": now,
                    },
                )

    # ── policy_config + config-version reads/writes (AUDIT-C1.3 batch 6) ──────

    def _normalize_policy_config_benefit_row(self, d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not d:
            return None
        for k in ("cap_rule_json", "conditions_json", "assignment_types", "family_statuses", "employee_levels"):
            self._parse_json_col(d, k)
        for bk in ("covered", "is_active"):
            v = d.get(bk)
            if v is not None and not isinstance(v, bool):
                try:
                    d[bk] = bool(int(v))
                except (TypeError, ValueError):
                    d[bk] = bool(v)
        return d

    def get_policy_config(self, company_id: str, config_key: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT * FROM policy_configs WHERE company_id = :cid AND config_key = :ck"
                ),
                {"cid": str(company_id), "ck": str(config_key)},
            ).fetchone()
        d = self._row_to_dict(row)
        if not d:
            return None
        for bk in ("is_active",):
            v = d.get(bk)
            if v is not None and not isinstance(v, bool):
                try:
                    d[bk] = bool(int(v))
                except (TypeError, ValueError):
                    d[bk] = bool(v)
        return d

    def ensure_policy_config(
        self, company_id: str, config_key: str, *, created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        from ..database import _is_sqlite
        existing = self.get_policy_config(company_id, config_key)
        if existing:
            return existing
        pid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_configs
                    (id, company_id, name, config_key, description, is_active, created_by, created_at, updated_at)
                    VALUES (:id, :cid, :name, :ck, NULL, :ia, :cb, :ca, :ua)
                    """
                ),
                {
                    "id": pid,
                    "cid": str(company_id),
                    "name": "Compensation & Allowance",
                    "ck": str(config_key),
                    "ia": 1 if _is_sqlite else True,
                    "cb": created_by,
                    "ca": now,
                    "ua": now,
                },
            )
        got = self.get_policy_config(company_id, config_key)
        assert got
        return got

    def get_policy_config_version_row(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_config_versions WHERE id = :id"),
                {"id": str(version_id)},
            ).fetchone()
        return self._row_to_dict(row)

    def get_policy_config_version_with_config(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT v.*, c.company_id AS _company_id, c.config_key AS _config_key
                    FROM policy_config_versions v
                    JOIN policy_configs c ON c.id = v.policy_config_id
                    WHERE v.id = :id
                    """
                ),
                {"id": str(version_id)},
            ).fetchone()
        return self._row_to_dict(row)

    def archive_policy_config_drafts(self, policy_config_id: str) -> int:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE policy_config_versions
                    SET status = 'archived', updated_at = :now
                    WHERE policy_config_id = :pid AND status = 'draft'
                    """
                ),
                {"pid": str(policy_config_id), "now": now},
            )
            try:
                return int(r.rowcount or 0)
            except Exception:
                return 0

    def max_policy_config_version_number(self, policy_config_id: str) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT MAX(version_number) AS m FROM policy_config_versions WHERE policy_config_id = :pid"
                ),
                {"pid": str(policy_config_id)},
            ).fetchone()
        m = row._mapping.get("m") if row else None
        if m is None:
            return 0
        try:
            return int(m)
        except (TypeError, ValueError):
            return 0

    def insert_policy_config_version(
        self,
        policy_config_id: str,
        version_number: int,
        status: str,
        effective_date: str,
        *,
        created_by: Optional[str] = None,
    ) -> str:
        vid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_config_versions
                    (id, policy_config_id, version_number, status, effective_date, published_at,
                     created_by, created_at, updated_at)
                    VALUES (:id, :pid, :vn, :st, :ed, NULL, :cb, :ca, :ua)
                    """
                ),
                {
                    "id": vid,
                    "pid": str(policy_config_id),
                    "vn": int(version_number),
                    "st": str(status),
                    "ed": str(effective_date),
                    "cb": created_by,
                    "ca": now,
                    "ua": now,
                },
            )
        return vid

    # ── policy_config benefit rows (AUDIT-C1.3 batch 7) ──────────────────────

    def list_policy_config_benefits(self, policy_config_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT * FROM policy_config_benefits
                    WHERE policy_config_version_id = :vid
                    ORDER BY display_order, benefit_key, targeting_signature
                    """
                ),
                {"vid": str(policy_config_version_id)},
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            d = self._row_to_dict(row)
            if d:
                out.append(self._normalize_policy_config_benefit_row(d) or d)
        return out

    def delete_policy_config_benefits_for_version(self, policy_config_version_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM policy_config_benefits WHERE policy_config_version_id = :vid"),
                {"vid": str(policy_config_version_id)},
            )

    def delete_policy_config_benefit_by_key(
        self,
        policy_config_version_id: str,
        *,
        benefit_key: str,
        targeting_signature: str,
    ) -> int:
        """
        Delete one benefit row from a specific version, matched by the
        (benefit_key, targeting_signature) pair that uniquely identifies
        a row within a version. Used by the diff "revert row" flow to
        replace a single draft row without touching its siblings.
        Returns the number of rows deleted (0 or 1).
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    DELETE FROM policy_config_benefits
                    WHERE policy_config_version_id = :vid
                      AND benefit_key = :bk
                      AND targeting_signature = :tsig
                    """
                ),
                {
                    "vid": str(policy_config_version_id),
                    "bk": str(benefit_key),
                    "tsig": str(targeting_signature or "global"),
                },
            )
            return int(result.rowcount or 0)

    def insert_policy_config_benefit_row(self, row: Dict[str, Any]) -> str:
        from ..database import _is_sqlite
        bid = str(row.get("id") or uuid.uuid4())
        now = datetime.utcnow().isoformat()
        cap_j = row.get("cap_rule_json")
        if isinstance(cap_j, dict):
            cap_j = json.dumps(cap_j)
        elif cap_j is None:
            cap_j = "{}"
        cond_j = row.get("conditions_json")
        if isinstance(cond_j, dict):
            cond_j = json.dumps(cond_j)
        elif cond_j is None:
            cond_j = "{}"
        at_j = row.get("assignment_types")
        if isinstance(at_j, list):
            at_j = json.dumps(at_j)
        elif at_j is None:
            at_j = "[]"
        fs_j = row.get("family_statuses")
        if isinstance(fs_j, list):
            fs_j = json.dumps(fs_j)
        elif fs_j is None:
            fs_j = "[]"
        el_j = row.get("employee_levels")
        if isinstance(el_j, list):
            el_j = json.dumps(el_j)
        elif el_j is None:
            el_j = "[]"
        cov = row.get("covered", False)
        if _is_sqlite:
            cov = 1 if cov else 0
        iact = row.get("is_active", True)
        if _is_sqlite:
            iact = 1 if iact else 0
        ag = row.get("auto_generated", True)
        if _is_sqlite:
            ag = 1 if ag else 0
        params = {
            "id": bid,
            "vid": str(row["policy_config_version_id"]),
            "bk": str(row["benefit_key"]),
            "bl": str(row["benefit_label"]),
            "cat": str(row["category"]),
            "cov": cov,
            "vt": str(row.get("value_type") or "none"),
            "av": row.get("amount_value"),
            "cc": row.get("currency_code"),
            "pv": row.get("percentage_value"),
            "uf": str(row.get("unit_frequency") or "one_time"),
            "crj": cap_j,
            "notes": row.get("notes"),
            "cj": cond_j,
            "atj": at_j,
            "fsj": fs_j,
            "elj": el_j,
            "tsig": str(row.get("targeting_signature") or "global"),
            "ia": iact,
            "do": int(row.get("display_order") or 0),
            "src": (str(row["source"]) if row.get("source") else None),
            "ag": ag,
            "fc": row.get("field_confidence"),
            "ca": now,
            "ua": now,
        }
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_config_benefits
                    (id, policy_config_version_id, benefit_key, benefit_label, category, covered,
                     value_type, amount_value, currency_code, percentage_value, unit_frequency,
                     cap_rule_json, notes, conditions_json, assignment_types, family_statuses,
                     employee_levels, targeting_signature, is_active, display_order, source,
                     auto_generated, field_confidence, created_at, updated_at)
                    VALUES
                    (:id, :vid, :bk, :bl, :cat, :cov, :vt, :av, :cc, :pv, :uf, :crj, :notes, :cj,
                     :atj, :fsj, :elj, :tsig, :ia, :do, :src, :ag, :fc, :ca, :ua)
"""
                ),
                params,
            )
        return bid

    # ── policy_config_version publish / draft / history (AUDIT-C1.3 batch 8) ──

    def publish_policy_config_version_atomic(self, version_id: str) -> None:
        vid = str(version_id)
        meta = self.get_policy_config_version_with_config(vid)
        if not meta:
            raise ValueError("policy_config_version not found")
        st = str(meta.get("status") or "")
        if st not in ("draft", "approved"):
            raise ValueError(f"cannot publish version in status {st!r}")
        cfg_id = str(meta.get("policy_config_id") or "")
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE policy_config_versions
                    SET status = 'archived', updated_at = :now
                    WHERE policy_config_id = :cid AND status = 'published'
                    """
                ),
                {"cid": cfg_id, "now": now},
            )
            conn.execute(
                text(
                    """
                    UPDATE policy_config_versions
                    SET status = 'published', published_at = :now, updated_at = :now
                    WHERE id = :vid AND status IN ('draft', 'approved')
                    """
                ),
                {"vid": vid, "now": now},
            )
        check = self.get_policy_config_version_row(vid)
        if not check or str(check.get("status")) != "published":
            raise ValueError("publish failed (version missing or not published)")

    def get_latest_published_policy_config_version(
        self, company_id: str, config_key: str
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT v.*
                    FROM policy_config_versions v
                    JOIN policy_configs c ON c.id = v.policy_config_id
                    WHERE c.company_id = :cid AND c.config_key = :ck AND v.status = 'published'
                    ORDER BY v.effective_date DESC, v.version_number DESC
                    LIMIT 1
                    """
                ),
                {"cid": str(company_id), "ck": str(config_key)},
            ).fetchone()
        return self._row_to_dict(row)

    def get_policy_config_draft_for_config(self, policy_config_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM policy_config_versions
                    WHERE policy_config_id = :pid AND status = 'draft'
                    LIMIT 1
                    """
                ),
                {"pid": str(policy_config_id)},
            ).fetchone()
        return self._row_to_dict(row)

    def list_policy_config_versions_history(self, policy_config_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, policy_config_id, version_number, status, effective_date,
                           published_at, created_by, created_at, updated_at
                    FROM policy_config_versions
                    WHERE policy_config_id = :pid
                    ORDER BY version_number DESC, created_at DESC
                    """
                ),
                {"pid": str(policy_config_id)},
            ).fetchall()
        return self._rows_to_list(rows)

    def update_policy_config_version_effective_date(
        self, version_id: str, effective_date: str, *, only_if_draft: bool = True
    ) -> None:
        now = datetime.utcnow().isoformat()
        vid = str(version_id)
        ed = str(effective_date)[:10]
        with self.engine.begin() as conn:
            if only_if_draft:
                conn.execute(
                    text(
                        """
                        UPDATE policy_config_versions
                        SET effective_date = :ed, updated_at = :now
                        WHERE id = :vid AND status = 'draft'
                        """
                    ),
                    {"ed": ed, "now": now, "vid": vid},
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE policy_config_versions
                        SET effective_date = :ed, updated_at = :now
                        WHERE id = :vid
                        """
                    ),
                    {"ed": ed, "now": now, "vid": vid},
                )

    # ── company_policies reads/writes (AUDIT-C1.3 batch 9) ───────────────────

    def get_company_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM company_policies WHERE id = :id"),
                {"id": policy_id},
            ).fetchone()
        return self._row_to_dict(row)

    def get_latest_company_policy(self, company_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT * FROM company_policies WHERE company_id = :cid "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"cid": company_id},
            ).fetchone()
        return self._row_to_dict(row)

    def get_company_policy_with_published_version(
        self, company_id: str
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Return (policy, version) for the best-matching published policy for this company.

        Uses one indexed lookup for (policy_id, version_id) instead of N queries per policy row
        (list_company_policies × get_published_policy_version).
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT cp.id AS policy_id, pv.id AS version_id
                    FROM company_policies cp
                    INNER JOIN policy_versions pv
                        ON pv.policy_id = cp.id AND LOWER(TRIM(pv.status)) = 'published'
                    WHERE cp.company_id = :cid
                    ORDER BY cp.created_at DESC, pv.version_number DESC, pv.created_at DESC
                    LIMIT 1
                    """
                ),
                {"cid": company_id},
            ).fetchone()
        if not row:
            return None
        m = row._mapping
        pid, vid = str(m["policy_id"]), str(m["version_id"])
        policy = self.get_company_policy(pid)
        version = self.get_policy_version(vid)
        if policy and version:
            return (policy, version)
        return None

    def list_company_ids_with_published_policy(self) -> List[Dict[str, Any]]:
        """Return list of {company_id, company_name} for companies that have at least one published policy (for debug logging)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT DISTINCT c.id AS company_id, c.name AS company_name
                    FROM companies c
                    JOIN company_policies cp ON cp.company_id = c.id::text
                    JOIN policy_versions pv ON pv.policy_id = cp.id AND pv.status = 'published'
                """),
                {},
            ).fetchall()
        return [{"company_id": r._mapping["company_id"], "company_name": r._mapping.get("company_name")} for r in rows]

    def update_company_policy_status(
        self,
        policy_id: str,
        status: str,
        extracted_at: Optional[str] = None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE company_policies SET extraction_status = :status, extracted_at = :ea "
                    "WHERE id = :id"
                ),
                {"status": status, "ea": extracted_at, "id": policy_id},
            )

    def update_company_policy_meta(
        self,
        policy_id: str,
        title: Optional[str] = None,
        version: Optional[str] = None,
        effective_date: Optional[str] = None,
    ) -> None:
        fields = []
        params: Dict[str, Any] = {"id": policy_id}
        if title is not None:
            fields.append("title = :title")
            params["title"] = title
        if version is not None:
            fields.append("version = :version")
            params["version"] = version
        if effective_date is not None:
            fields.append("effective_date = :effective_date")
            params["effective_date"] = effective_date
        if not fields:
            return
        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE company_policies SET {', '.join(fields)} WHERE id = :id"), params)

    # ── policy_documents (upload/intake) CRUD (AUDIT-C1.3 batch 10) ───────────

    def create_policy_document(
        self,
        doc_id: str,
        company_id: str,
        uploaded_by_user_id: str,
        filename: str,
        mime_type: str,
        storage_path: str,
        checksum: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        assistant_import_status: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from ..database import _is_sqlite
        now = datetime.utcnow().isoformat()
        ais = assistant_import_status if assistant_import_status is not None else "uploaded"
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(
                    text("""
                        INSERT INTO policy_documents
                        (id, company_id, uploaded_by_user_id, filename, mime_type, storage_path,
                         checksum, uploaded_at, processing_status, created_at, updated_at,
                         file_size_bytes, assistant_import_status)
                        VALUES (:id, :cid, :uid, :fn, :mt, :sp, :cs, :now, 'uploaded', :now, :now,
                         :fsz, :ais)
                    """),
                    {
                        "id": doc_id,
                        "cid": company_id,
                        "uid": uploaded_by_user_id,
                        "fn": filename,
                        "mt": mime_type,
                        "sp": storage_path,
                        "cs": checksum,
                        "now": now,
                        "fsz": file_size_bytes,
                        "ais": ais,
                    },
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO policy_documents
                        (id, company_id, uploaded_by_user_id, filename, mime_type, storage_path,
                         checksum, uploaded_at, processing_status, created_at, updated_at,
                         file_size_bytes, assistant_import_status)
                        VALUES (CAST(:id AS uuid), :cid, :uid, :fn, :mt, :sp, :cs, CAST(:now AS timestamptz), 'uploaded',
                         CAST(:now AS timestamptz), CAST(:now AS timestamptz), :fsz, :ais)
                    """),
                    {
                        "id": doc_id,
                        "cid": company_id,
                        "uid": uploaded_by_user_id,
                        "fn": filename,
                        "mt": mime_type,
                        "sp": storage_path,
                        "cs": checksum,
                        "now": now,
                        "fsz": file_size_bytes,
                        "ais": ais,
                    },
                )
        return self.get_policy_document(doc_id, request_id=request_id) or {}

    def get_active_policy_document_by_checksum(
        self,
        company_id: str,
        checksum: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Idempotency lookup: return the newest non-failed policy_documents row
        for (company_id, checksum), or None.

        Used by the upload endpoint so double-clicks / refresh-resubmits /
        network retries don't create duplicate rows and re-run LLM extraction.
        Rows with processing_status='failed' are excluded so the caller can
        re-trigger extraction by uploading again.
        """
        if not (company_id and checksum):
            return None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM policy_documents "
                "WHERE company_id = :cid AND checksum = :chk "
                "AND COALESCE(processing_status, '') != 'failed' "
                "ORDER BY uploaded_at DESC LIMIT 1",
                {"cid": company_id, "chk": checksum},
                op_name="get_active_policy_document_by_checksum",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def get_policy_document(
        self, doc_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM policy_documents WHERE id = :id",
                {"id": doc_id},
                op_name="get_policy_document",
                request_id=request_id,
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            try:
                val = d.get("extracted_metadata")
                raw = json.loads(val) if isinstance(val, str) else (val if isinstance(val, dict) else None)
                from ..app.services.policy_document_intake import normalize_extracted_metadata
                d["extracted_metadata"] = normalize_extracted_metadata(raw)
            except Exception:
                d["extracted_metadata"] = {}
        return d

    def list_policy_documents(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM policy_documents WHERE company_id = :cid ORDER BY uploaded_at DESC",
                {"cid": company_id},
                op_name="list_policy_documents",
                request_id=request_id,
            ).fetchall()
        items = self._rows_to_list(rows)
        from ..app.services.policy_document_intake import normalize_extracted_metadata
        for d in items:
            try:
                val = d.get("extracted_metadata")
                raw = json.loads(val) if isinstance(val, str) else (val if isinstance(val, dict) else None)
                d["extracted_metadata"] = normalize_extracted_metadata(raw)
            except Exception:
                d["extracted_metadata"] = {}
        return items

    def update_policy_document(
        self,
        doc_id: str,
        processing_status: Optional[str] = None,
        detected_document_type: Optional[str] = None,
        detected_policy_scope: Optional[str] = None,
        version_label: Optional[str] = None,
        effective_date: Optional[str] = None,
        raw_text: Optional[str] = None,
        extraction_error: Optional[str] = None,
        extracted_metadata: Optional[Dict[str, Any]] = None,
        assistant_import_status: Optional[str] = None,
        processed_at: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": doc_id, "now": now}
        if processing_status is not None:
            fields.append("processing_status = :ps")
            params["ps"] = processing_status
        if detected_document_type is not None:
            fields.append("detected_document_type = :ddt")
            params["ddt"] = detected_document_type
        if detected_policy_scope is not None:
            fields.append("detected_policy_scope = :dps")
            params["dps"] = detected_policy_scope
        if version_label is not None:
            fields.append("version_label = :vl")
            params["vl"] = version_label
        if effective_date is not None:
            fields.append("effective_date = :ed")
            params["ed"] = effective_date
        if raw_text is not None:
            fields.append("raw_text = :rt")
            params["rt"] = raw_text
        if extraction_error is not None:
            fields.append("extraction_error = :ee")
            params["ee"] = extraction_error
        if extracted_metadata is not None:
            fields.append("extracted_metadata = :em")
            params["em"] = json.dumps(extracted_metadata)
        if assistant_import_status is not None:
            fields.append("assistant_import_status = :ais")
            params["ais"] = assistant_import_status
        if processed_at is not None:
            fields.append("processed_at = :pat")
            params["pat"] = processed_at
        if file_size_bytes is not None:
            fields.append("file_size_bytes = :fsz")
            params["fsz"] = file_size_bytes
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_documents SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    # ── requirement_* adapters (AUDIT-C1.3 batch 11) ─────────────────────────

    def list_requirement_entities(self, destination_country: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_entities WHERE destination_country = :dest AND status = :status "
                    "ORDER BY updated_at DESC"
                ), {"dest": destination_country, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_entities WHERE destination_country = :dest ORDER BY updated_at DESC"
                ), {"dest": destination_country}).fetchall()
        return self._rows_to_list(rows)

    def list_requirement_facts(self, entity_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_facts WHERE entity_id = :eid AND status = :status ORDER BY created_at DESC"
                ), {"eid": entity_id, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_facts WHERE entity_id = :eid ORDER BY created_at DESC"
                ), {"eid": entity_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def list_requirement_facts_by_destination(self, destination_country: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT f.* FROM requirement_facts f "
                    "JOIN requirement_entities e ON e.id = f.entity_id "
                    "WHERE e.destination_country = :dest AND f.status = :status "
                    "ORDER BY f.created_at DESC"
                ), {"dest": destination_country, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT f.* FROM requirement_facts f "
                    "JOIN requirement_entities e ON e.id = f.entity_id "
                    "WHERE e.destination_country = :dest "
                    "ORDER BY f.created_at DESC"
                ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def list_approved_requirement_facts(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT f.* FROM requirement_facts f "
                "JOIN requirement_entities e ON e.id = f.entity_id "
                "WHERE e.destination_country = :dest AND f.status = 'approved'"
            ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def update_requirement_fact_status(
        self,
        fact_ids: List[str],
        status: str,
        reviewer_user_id: str,
        notes: Optional[str] = None,
    ) -> None:
        if not fact_ids:
            return
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for fid in fact_ids:
                conn.execute(text(
                    "UPDATE requirement_facts SET status = :status WHERE id = :id"
                ), {"status": status, "id": fid})
                conn.execute(text(
                    "INSERT INTO requirement_reviews "
                    "(id, entity_id, fact_id, reviewer_user_id, action, notes, created_at) "
                    "VALUES (:id, :entity_id, :fact_id, :reviewer_user_id, :action, :notes, :created_at)"
                ), {
                    "id": str(uuid.uuid4()),
                    "entity_id": None,
                    "fact_id": fid,
                    "reviewer_user_id": reviewer_user_id,
                    "action": "approve" if status == "approved" else "reject",
                    "notes": notes,
                    "created_at": now,
                })

    # ── policy knowledge snapshots / document chunks (AUDIT-C1.3 batch 12) ────

    def list_policy_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return []
        from ..database import _coerce_json_dict
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_document_chunks WHERE policy_document_id = :id "
                    "ORDER BY chunk_index ASC"
                ),
                {"id": doc_id},
            ).fetchall()
        out = self._rows_to_list(rows)
        for d in out:
            d["metadata_json"] = _coerce_json_dict(d.get("metadata_json"))
        return out

    def list_policy_document_chunks_for_snapshot(self, doc_id: str, snapshot_id: str) -> List[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return []
        from ..database import _coerce_json_dict
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_document_chunks WHERE policy_document_id = :id "
                    "AND snapshot_id = :sid ORDER BY chunk_index ASC"
                ),
                {"id": doc_id, "sid": snapshot_id},
            ).fetchall()
        out = self._rows_to_list(rows)
        for d in out:
            d["metadata_json"] = _coerce_json_dict(d.get("metadata_json"))
        return out

    def insert_policy_knowledge_snapshot(
        self,
        company_id: str,
        doc_id: str,
        *,
        version_label: Optional[str] = None,
        status: str = "failed",
        extraction_method: str = "deterministic_v1",
        revision_number: int = 1,
        parent_snapshot_id: Optional[str] = None,
        activation_state: str = "candidate",
    ) -> str:
        sid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_knowledge_snapshots
                    (id, company_id, policy_document_id, version_label, status, extraction_method, created_at,
                     revision_number, parent_snapshot_id, activation_state)
                    VALUES (:id, :cid, :doc, :vl, :st, :em, :now, :rn, :par, :as)
                    """
                ),
                {
                    "id": sid,
                    "cid": company_id,
                    "doc": doc_id,
                    "vl": version_label,
                    "st": status,
                    "em": extraction_method,
                    "now": now,
                    "rn": revision_number,
                    "par": parent_snapshot_id,
                    "as": activation_state,
                },
            )
        return sid

    def update_policy_knowledge_snapshot(
        self,
        snapshot_id: str,
        *,
        status: Optional[str] = None,
        superseded_at: Optional[str] = None,
    ) -> None:
        fields = []
        params: Dict[str, Any] = {"id": snapshot_id}
        if status is not None:
            fields.append("status = :st")
            params["st"] = status
        if superseded_at is not None:
            fields.append("superseded_at = :sa")
            params["sa"] = superseded_at
        if not fields:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_knowledge_snapshots SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def supersede_active_snapshots_for_company(self, company_id: str, except_snapshot_id: Optional[str] = None) -> None:
        """Mark active_for_assistant snapshots as superseded for this company."""
        if not self.policy_assistant_tables_available():
            return
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if except_snapshot_id:
                conn.execute(
                    text(
                        """
                        UPDATE policy_knowledge_snapshots
                        SET status = 'superseded', superseded_at = :now
                        WHERE company_id = :cid AND status = 'active_for_assistant'
                          AND id <> :ex
                        """
                    ),
                    {"cid": company_id, "now": now, "ex": except_snapshot_id},
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE policy_knowledge_snapshots
                        SET status = 'superseded', superseded_at = :now
                        WHERE company_id = :cid AND status = 'active_for_assistant'
                        """
                    ),
                    {"cid": company_id, "now": now},
                )

    # ── policy_facts + assistant binding reads (AUDIT-C1.3 batch 13) ──────────

    def insert_policy_fact(
        self,
        snapshot_id: str,
        fact_type: str,
        category: str,
        *,
        subcategory: Optional[str] = None,
        normalized_value_json: Optional[Dict[str, Any]] = None,
        applicability_json: Optional[Dict[str, Any]] = None,
        ambiguity_flag: bool = False,
        confidence_score: Optional[float] = None,
        source_chunk_id: str = "",
        source_page: Optional[int] = None,
        source_section: Optional[str] = None,
        source_quote: Optional[str] = None,
    ) -> str:
        from ..database import _is_sqlite
        fid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        nv = normalized_value_json if normalized_value_json is not None else {}
        ap = applicability_json if applicability_json is not None else {}
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_facts
                    (id, snapshot_id, fact_type, category, subcategory, normalized_value_json,
                     applicability_json, ambiguity_flag, confidence_score, source_chunk_id,
                     source_page, source_section, source_quote, created_at)
                    VALUES (:id, :sid, :ft, :cat, :sub, :nv, :ap, :af, :cs, :ch, :pg, :sec, :sq, :now)
                    """
                ),
                {
                    "id": fid,
                    "sid": snapshot_id,
                    "ft": fact_type,
                    "cat": category,
                    "sub": subcategory,
                    "nv": json.dumps(nv),
                    "ap": json.dumps(ap),
                    "af": (1 if ambiguity_flag else 0) if _is_sqlite else bool(ambiguity_flag),
                    "cs": confidence_score,
                    "ch": source_chunk_id,
                    "pg": source_page,
                    "sec": source_section,
                    "sq": source_quote,
                    "now": now,
                },
            )
        return fid

    def count_policy_document_chunks(self, doc_id: str) -> int:
        if not self.policy_assistant_tables_available():
            return 0
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS n FROM policy_document_chunks WHERE policy_document_id = :id"),
                {"id": doc_id},
            ).fetchone()
        return int(row[0]) if row else 0

    def count_policy_facts_for_snapshot(self, snapshot_id: str) -> int:
        if not self.policy_assistant_tables_available():
            return 0
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS n FROM policy_facts WHERE snapshot_id = :id"),
                {"id": snapshot_id},
            ).fetchone()
        return int(row[0]) if row else 0

    def policy_fact_counts_by_type(self, snapshot_id: str) -> Dict[str, int]:
        if not self.policy_assistant_tables_available():
            return {}
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT fact_type, COUNT(*) AS n FROM policy_facts "
                    "WHERE snapshot_id = :id GROUP BY fact_type"
                ),
                {"id": snapshot_id},
            ).fetchall()
        out: Dict[str, int] = {}
        for r in rows:
            m = dict(r._mapping) if hasattr(r, "_mapping") else dict(r)
            out[str(m["fact_type"])] = int(m["n"])
        return out

    def list_policy_facts_for_snapshot(self, snapshot_id: str) -> List[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return []
        from ..database import _coerce_json_dict
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_facts WHERE snapshot_id = :id ORDER BY created_at"),
                {"id": snapshot_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            d["normalized_value_json"] = _coerce_json_dict(d.get("normalized_value_json"))
            d["applicability_json"] = _coerce_json_dict(d.get("applicability_json"))
            if "ambiguity_flag" in d and d["ambiguity_flag"] in (0, 1):
                d["ambiguity_flag"] = bool(d["ambiguity_flag"])
        return items

    def get_policy_document_chunks_by_ids(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        if not chunk_ids or not self.policy_assistant_tables_available():
            return []
        from ..database import _coerce_json_dict
        placeholders = ",".join([f":c{i}" for i in range(len(chunk_ids))])
        params: Dict[str, Any] = {f"c{i}": chunk_ids[i] for i in range(len(chunk_ids))}
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT * FROM policy_document_chunks WHERE id IN ({placeholders})"),
                params,
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            d["metadata_json"] = _coerce_json_dict(d.get("metadata_json"))
        return items

    def get_company_policy_assistant_binding(self, company_id: str) -> Optional[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM company_policy_assistant_bindings WHERE company_id = :cid"),
                {"cid": company_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ── assistant binding upsert + knowledge-snapshot getters (AUDIT-C1.3 batch 14) ──

    def upsert_company_policy_assistant_binding(
        self,
        company_id: str,
        active_snapshot_id: Optional[str],
        policy_document_id: Optional[str],
    ) -> None:
        if not self.policy_assistant_tables_available():
            return
        from ..database import _is_sqlite
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(
                    text(
                        """
                        INSERT INTO company_policy_assistant_bindings
                        (company_id, active_snapshot_id, policy_document_id, updated_at)
                        VALUES (:cid, :sid, :doc, :now)
                        ON CONFLICT(company_id) DO UPDATE SET
                          active_snapshot_id = excluded.active_snapshot_id,
                          policy_document_id = excluded.policy_document_id,
                          updated_at = excluded.updated_at
                        """
                    ),
                    {"cid": company_id, "sid": active_snapshot_id, "doc": policy_document_id, "now": now},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO company_policy_assistant_bindings
                        (company_id, active_snapshot_id, policy_document_id, updated_at)
                        VALUES (:cid, :sid, :doc, :now::timestamptz)
                        ON CONFLICT (company_id) DO UPDATE SET
                          active_snapshot_id = EXCLUDED.active_snapshot_id,
                          policy_document_id = EXCLUDED.policy_document_id,
                          updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {"cid": company_id, "sid": active_snapshot_id, "doc": policy_document_id, "now": now},
                )

    def get_active_policy_knowledge_snapshot_for_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT s.* FROM policy_knowledge_snapshots s
                    WHERE s.company_id = :cid
                      AND COALESCE(
                        NULLIF(TRIM(s.activation_state), ''),
                        CASE WHEN s.status = 'active_for_assistant' THEN 'active_for_assistant' ELSE s.status END
                      ) = 'active_for_assistant'
                    ORDER BY s.created_at DESC
                    LIMIT 1
                    """
                ),
                {"cid": company_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_latest_policy_knowledge_snapshot_for_document(self, policy_document_id: str) -> Optional[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM policy_knowledge_snapshots
                    WHERE policy_document_id = :id
                    ORDER BY COALESCE(revision_number, 0) DESC, created_at DESC
                    LIMIT 1
                    """
                ),
                {"id": policy_document_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def count_policy_facts_for_document_via_snapshots(self, policy_document_id: str) -> int:
        """Count facts tied to this document through any snapshot (latest snapshot row used in UI)."""
        snap = self.get_latest_policy_knowledge_snapshot_for_document(policy_document_id)
        if not snap:
            return 0
        return self.count_policy_facts_for_snapshot(str(snap.get("id")))

    def policy_hardening_tables_available(self) -> bool:
        from ..database import _is_sqlite
        try:
            with self.engine.connect() as conn:
                if _is_sqlite:
                    r = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='policy_extraction_locks'"
                        )
                    ).fetchone()
                    return r is not None
                r = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'policy_extraction_locks'"
                    )
                ).fetchone()
                return r is not None
        except Exception:
            return False

    def get_policy_knowledge_snapshot_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_knowledge_snapshots WHERE id = :id"),
                {"id": snapshot_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def next_snapshot_revision_number(self, policy_document_id: str) -> int:
        if not self.policy_assistant_tables_available():
            return 1
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(MAX(revision_number), 0) AS m FROM policy_knowledge_snapshots "
                    "WHERE policy_document_id = :id"
                ),
                {"id": policy_document_id},
            ).fetchone()
        m = int(row[0]) if row and row[0] is not None else 0
        return m + 1

    # ── snapshot activation + extraction locks (AUDIT-C1.3 batch 15) ──────────

    def activate_policy_knowledge_snapshot(
        self,
        new_snapshot_id: str,
        company_id: str,
        policy_document_id: str,
        activated_by_user_id: str,
    ) -> None:
        """Supersede prior active snapshot for company; activate new snapshot and update binding."""
        if not self.policy_assistant_tables_available():
            return
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE policy_knowledge_snapshots
                    SET activation_state = 'superseded', status = 'superseded', superseded_at = :now,
                        superseded_by_snapshot_id = :new_id
                    WHERE company_id = :cid
                      AND CAST(id AS TEXT) <> CAST(:new_id AS TEXT)
                      AND COALESCE(activation_state, CASE WHEN status = 'active_for_assistant' THEN 'active_for_assistant' ELSE status END) = 'active_for_assistant'
                    """
                ),
                {"now": now, "new_id": new_snapshot_id, "cid": company_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE policy_knowledge_snapshots
                    SET activation_state = 'active_for_assistant', status = 'active_for_assistant',
                        activated_at = :now, activated_by_user_id = :uid
                    WHERE id = :sid
                    """
                ),
                {"now": now, "uid": activated_by_user_id, "sid": new_snapshot_id},
            )
        self.upsert_company_policy_assistant_binding(company_id, new_snapshot_id, policy_document_id)

    def mark_policy_snapshot_failed(self, snapshot_id: str) -> None:
        if not self.policy_assistant_tables_available():
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE policy_knowledge_snapshots
                    SET activation_state = 'failed', status = 'failed'
                    WHERE id = :id
                    """
                ),
                {"id": snapshot_id},
            )

    def try_acquire_policy_extraction_lock(
        self,
        policy_document_id: str,
        company_id: str,
        locked_by_user_id: str,
        *,
        ttl_seconds: int = 900,
    ) -> Optional[str]:
        """
        Returns lock_token if acquired; None if table missing.
        Caller should check for active lock and raise 409 if row exists and not expired.
        """
        if not self.policy_hardening_tables_available():
            return str(uuid.uuid4())
        token = str(uuid.uuid4())
        now = datetime.utcnow()
        expires = datetime.utcfromtimestamp(now.timestamp() + ttl_seconds).isoformat()
        now_iso = now.isoformat()
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT id, expires_at, status FROM policy_extraction_locks WHERE policy_document_id = :doc"
                ),
                {"doc": policy_document_id},
            ).fetchone()
            if row:
                d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
                exp = d.get("expires_at")
                st = (d.get("status") or "").strip()
                if st == "active" and exp:
                    try:
                        from datetime import datetime as dt

                        ex = dt.fromisoformat(str(exp).replace("Z", "+00:00"))
                        if ex.timestamp() > now.timestamp():
                            return None
                    except Exception:
                        if st == "active":
                            return None
                conn.execute(
                    text("DELETE FROM policy_extraction_locks WHERE policy_document_id = :doc"),
                    {"doc": policy_document_id},
                )
            lid = str(uuid.uuid4())
            conn.execute(
                text(
                    """
                    INSERT INTO policy_extraction_locks
                    (id, policy_document_id, company_id, locked_by_user_id, lock_token, acquired_at, expires_at, status)
                    VALUES (:id, :doc, :cid, :uid, :tok, :acq, :exp, 'active')
                    """
                ),
                {
                    "id": lid,
                    "doc": policy_document_id,
                    "cid": company_id,
                    "uid": locked_by_user_id,
                    "tok": token,
                    "acq": now_iso,
                    "exp": expires,
                },
            )
        return token

    def release_policy_extraction_lock(self, policy_document_id: str, lock_token: str) -> None:
        if not self.policy_hardening_tables_available():
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE policy_extraction_locks
                    SET status = 'released'
                    WHERE policy_document_id = :doc AND lock_token = :tok AND status = 'active'
                    """
                ),
                {"doc": policy_document_id, "tok": lock_token},
            )

    def _maybe_ensure_policy_versions_normalization_draft_json(self) -> None:
        """policy_versions.normalization_draft_json — HR normalized draft blob. Supabase: 20260422100000_policy_versions_normalization_draft_json.sql"""
        from ..database import _is_sqlite  # lazy: avoid import cycle
        if _is_sqlite:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE public.policy_versions ADD COLUMN IF NOT EXISTS normalization_draft_json JSONB"
                    )
                )
            log.info(
                "Ensured policy_versions.normalization_draft_json exists (idempotent). "
                "Prefer applying supabase/migrations/20260422100000_policy_versions_normalization_draft_json.sql in CI."
            )
        except Exception as ex:
            log.warning("policy_versions.normalization_draft_json ensure failed (run Supabase migration): %s", ex)

    def _maybe_ensure_policy_versions_normalization_state(self) -> None:
        """policy_versions.normalization_state — normalization pipeline lifecycle marker."""
        from ..database import _is_sqlite  # lazy: avoid import cycle
        if _is_sqlite:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE public.policy_versions ADD COLUMN IF NOT EXISTS normalization_state TEXT"
                    )
                )
            log.info(
                "Ensured policy_versions.normalization_state exists (idempotent). "
                "Prefer supabase/migrations/20260321120000_policy_versions_normalization_state.sql in CI."
            )
        except Exception as ex:
            log.warning("policy_versions.normalization_state ensure failed (run Supabase migration): %s", ex)

    def _maybe_ensure_policy_benefit_rule_hr_overrides(self) -> None:
        """HR override layer tables. Supabase: 20260422120000_policy_benefit_rule_hr_overrides.sql"""
        from ..database import _is_sqlite  # lazy: avoid import cycle
        if _is_sqlite:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS public.policy_benefit_rule_hr_overrides (
                          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                          policy_version_id uuid NOT NULL REFERENCES public.policy_versions (id) ON DELETE CASCADE,
                          benefit_rule_id uuid NOT NULL REFERENCES public.policy_benefit_rules (id) ON DELETE CASCADE,
                          service_visibility text NULL,
                          amount_value_override numeric NULL,
                          amount_unit_override text NULL,
                          currency_override text NULL,
                          duration_quantity_json jsonb NULL,
                          approval_required_override boolean NULL,
                          hr_notes text NULL,
                          created_by text NULL,
                          updated_by text NULL,
                          created_at timestamptz NOT NULL DEFAULT now(),
                          updated_at timestamptz NOT NULL DEFAULT now(),
                          UNIQUE (policy_version_id, benefit_rule_id)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS public.policy_benefit_rule_hr_override_audit (
                          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                          override_id uuid NOT NULL REFERENCES public.policy_benefit_rule_hr_overrides (id) ON DELETE CASCADE,
                          action text NOT NULL,
                          previous_json jsonb NULL,
                          new_json jsonb NULL,
                          actor_id text NULL,
                          created_at timestamptz NOT NULL DEFAULT now()
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_pbr_hr_overrides_version
                        ON public.policy_benefit_rule_hr_overrides (policy_version_id)
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_pbr_hr_override_audit_override
                        ON public.policy_benefit_rule_hr_override_audit (override_id, created_at DESC)
                        """
                    )
                )
            log.info(
                "Ensured policy_benefit_rule_hr_overrides tables exist (idempotent). "
                "Prefer supabase/migrations/20260422120000_policy_benefit_rule_hr_overrides.sql for RLS."
            )
        except Exception as ex:
            log.warning("policy_benefit_rule_hr_overrides ensure failed (run Supabase migration): %s", ex)

    def _maybe_ensure_compensation_allowance_policy_config(self) -> None:
        """
        Structured Compensation & Allowance matrix (policy_configs / versions / benefits).
        Supabase: supabase/migrations/20260425100000_compensation_allowance_policy_config.sql

        Idempotent CREATE TABLE for dev DBs without migrations; production RLS lives in the migration.
        """
        from ..database import _is_sqlite  # lazy: avoid import cycle
        if _is_sqlite:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS public.policy_configs (
                          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                          company_id text NOT NULL,
                          name text NOT NULL DEFAULT 'Compensation & Allowance',
                          config_key text NOT NULL DEFAULT 'compensation_allowance',
                          description text,
                          is_active boolean NOT NULL DEFAULT true,
                          created_by text,
                          created_at timestamptz NOT NULL DEFAULT now(),
                          updated_at timestamptz NOT NULL DEFAULT now(),
                          UNIQUE (company_id, config_key)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS public.policy_config_versions (
                          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                          policy_config_id uuid NOT NULL REFERENCES public.policy_configs (id) ON DELETE CASCADE,
                          version_number int NOT NULL,
                          status text NOT NULL DEFAULT 'draft',
                          effective_date date NOT NULL,
                          published_at timestamptz,
                          created_by text,
                          created_at timestamptz NOT NULL DEFAULT now(),
                          updated_at timestamptz NOT NULL DEFAULT now(),
                          UNIQUE (policy_config_id, version_number),
                          CHECK (status IN ('draft', 'approved', 'published', 'archived'))
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS public.policy_config_benefits (
                          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                          policy_config_version_id uuid NOT NULL
                            REFERENCES public.policy_config_versions (id) ON DELETE CASCADE,
                          benefit_key text NOT NULL,
                          benefit_label text NOT NULL,
                          category text NOT NULL,
                          covered boolean NOT NULL DEFAULT false,
                          value_type text NOT NULL DEFAULT 'none',
                          amount_value numeric,
                          currency_code text,
                          percentage_value numeric,
                          unit_frequency text NOT NULL DEFAULT 'one_time',
                          cap_rule_json jsonb NOT NULL DEFAULT '{}',
                          notes text,
                          conditions_json jsonb NOT NULL DEFAULT '{}',
                          assignment_types jsonb NOT NULL DEFAULT '[]',
                          family_statuses jsonb NOT NULL DEFAULT '[]',
                          employee_levels jsonb NOT NULL DEFAULT '[]',
                          targeting_signature text NOT NULL DEFAULT 'global',
                          is_active boolean NOT NULL DEFAULT true,
                          display_order int NOT NULL DEFAULT 0,
                          source text DEFAULT 'seeded',
                          auto_generated boolean NOT NULL DEFAULT true,
                          created_at timestamptz NOT NULL DEFAULT now(),
                          updated_at timestamptz NOT NULL DEFAULT now(),
                          UNIQUE (policy_config_version_id, benefit_key, targeting_signature)
                        )
                        """
                    )
                )
                # Back-compat: idempotent add for tables created before the
                # employee_levels targeting axis landed (Phase 1). Postgres
                # "ADD COLUMN IF NOT EXISTS" is safe on 9.6+; this is a no-op
                # on fresh schemas where the CREATE TABLE above already added it.
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE public.policy_config_benefits "
                            "ADD COLUMN IF NOT EXISTS employee_levels jsonb NOT NULL DEFAULT '[]'::jsonb"
                        )
                    )
                except Exception:
                    pass
                # AIQ-838: provenance marker (extracted_llm | template_default | manual_hr | seeded).
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE public.policy_config_benefits "
                            "ADD COLUMN IF NOT EXISTS source text"
                        )
                    )
                except Exception:
                    pass
                # AIQ-839: auto_generated flag + field-level audit table.
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE public.policy_config_benefits "
                            "ADD COLUMN IF NOT EXISTS auto_generated boolean NOT NULL DEFAULT true"
                        )
                    )
                except Exception:
                    pass
                try:
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS public.policy_config_benefits_audit (
                              id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                              benefit_id uuid,
                              policy_config_version_id uuid,
                              benefit_key text,
                              action text NOT NULL,
                              old_value jsonb,
                              new_value jsonb,
                              source text,
                              changed_by text,
                              changed_at timestamptz NOT NULL DEFAULT now()
                            )
                            """
                        )
                    )
                except Exception:
                    pass
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_policy_configs_company ON public.policy_configs (company_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_pc_versions_config "
                        "ON public.policy_config_versions (policy_config_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_pc_versions_status "
                        "ON public.policy_config_versions (policy_config_id, status)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_pc_versions_effective "
                        "ON public.policy_config_versions (effective_date)"
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_config_one_published
                        ON public.policy_config_versions (policy_config_id)
                        WHERE status = 'published'
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_config_one_draft
                        ON public.policy_config_versions (policy_config_id)
                        WHERE status = 'draft'
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_pc_benefits_version "
                        "ON public.policy_config_benefits (policy_config_version_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_pc_benefits_key "
                        "ON public.policy_config_benefits (benefit_key)"
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_pc_benefits_category
                        ON public.policy_config_benefits (policy_config_version_id, category)
                        """
                    )
                )
            log.info(
                "Ensured compensation_allowance policy_config tables exist (idempotent). "
                "Apply supabase/migrations/20260425100000_compensation_allowance_policy_config.sql for RLS."
            )
        except Exception as ex:
            log.warning("compensation_allowance policy_config ensure failed (run Supabase migration): %s", ex)

    def list_policy_exceptions(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM policy_exceptions WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def create_policy_exception(
        self,
        exception_id: str,
        assignment_id: str,
        category: str,
        status: str,
        reason: Optional[str],
        requested_amount: Optional[float],
        requested_by: str,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO policy_exceptions "
                "(id, assignment_id, category, status, reason, requested_amount, requested_by, created_at, updated_at) "
                "VALUES (:id, :aid, :cat, :status, :reason, :amount, :by, :ca, :ua)"
            ), {
                "id": exception_id, "aid": assignment_id, "cat": category,
                "status": status, "reason": reason, "amount": requested_amount,
                "by": requested_by, "ca": now, "ua": now,
            })

    def create_hr_policy(
        self,
        policy_id: str,
        policy_json: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(policy_json)
        status = policy_json.get("status", "draft")
        company_entity = policy_json.get("companyEntity", "")
        effective_date = policy_json.get("effectiveDate", "")
        version = policy_json.get("version", 1)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO hr_policies "
                "(id, policy_json, status, company_entity, effective_date, created_at, updated_at, created_by, version) "
                "VALUES (:id, :pj, :status, :ce, :ed, :ca, :ua, :cb, :ver)"
            ), {
                "id": policy_id, "pj": pj, "status": status, "ce": company_entity,
                "ed": effective_date, "ca": now, "ua": now, "cb": created_by, "ver": version,
            })

    def update_hr_policy(
        self,
        policy_id: str,
        policy_json: Dict[str, Any],
    ) -> bool:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(policy_json)
        status = policy_json.get("status", "draft")
        company_entity = policy_json.get("companyEntity", "")
        effective_date = policy_json.get("effectiveDate", "")
        version = policy_json.get("version", 1)
        with self.engine.begin() as conn:
            r = conn.execute(text(
                "UPDATE hr_policies SET policy_json = :pj, status = :status, company_entity = :ce, "
                "effective_date = :ed, updated_at = :ua, version = :ver WHERE id = :id"
            ), {"pj": pj, "status": status, "ce": company_entity, "ed": effective_date, "ua": now, "ver": version, "id": policy_id})
            return r.rowcount > 0

    def get_hr_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT policy_json, status, created_at, updated_at, version FROM hr_policies WHERE id = :id"
            ), {"id": policy_id}).fetchone()
        if not row:
            return None
        policy = json.loads(row._mapping["policy_json"])
        policy["_meta"] = {
            "status": row._mapping["status"],
            "created_at": row._mapping["created_at"],
            "updated_at": row._mapping["updated_at"],
            "version": row._mapping["version"],
        }
        return policy

    def list_hr_policies(
        self,
        status_filter: Optional[str] = None,
        company_entity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            q = "SELECT id, policy_json, status, company_entity, effective_date, created_at, updated_at, version FROM hr_policies WHERE 1=1"
            params: Dict[str, Any] = {}
            if status_filter:
                q += " AND status = :status"
                params["status"] = status_filter
            if company_entity:
                q += " AND company_entity = :ce"
                params["ce"] = company_entity
            q += " ORDER BY effective_date DESC, created_at DESC"
            rows = conn.execute(text(q), params).fetchall()
        result = []
        for row in rows:
            policy = json.loads(row._mapping["policy_json"])
            policy["id"] = row._mapping["id"]
            policy["_meta"] = {
                "status": row._mapping["status"],
                "created_at": row._mapping["created_at"],
                "updated_at": row._mapping["updated_at"],
                "version": row._mapping["version"],
            }
            result.append(policy)
        return result

    def get_published_hr_policy_for_employee(
        self,
        employee_band: str,
        assignment_type: str,
        country_code: Optional[str] = None,
        company_entity: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the first published policy that matches band, assignment type, optionally country/entity."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, policy_json FROM hr_policies WHERE status = 'published' "
                "ORDER BY effective_date DESC, created_at DESC"
            )).fetchall()
        for row in rows:
            policy = json.loads(row._mapping["policy_json"])
            bands = policy.get("employeeBands", [])
            types = policy.get("assignmentTypes", [])
            if employee_band in bands and assignment_type in types:
                if company_entity and policy.get("companyEntity") != company_entity:
                    continue
                policy["id"] = row._mapping["id"]
                return policy
        return None

    def delete_hr_policy(self, policy_id: str) -> bool:
        with self.engine.begin() as conn:
            r = conn.execute(text("DELETE FROM hr_policies WHERE id = :id"), {"id": policy_id})
            return r.rowcount > 0

    def run_policy_normalization_transaction(self, fn: Callable[[Any], None]) -> None:
        """
        Execute ``fn(connection)`` in a single commit/rollback boundary for policy normalization
        persistence (company shell + policy_version + Layer-2 + draft).
        """
        with self.engine.begin() as conn:
            fn(conn)

    def list_admin_policy_overview(
        self, company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Per-company policy status for admin overview."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        params: Dict[str, Any] = {}
        where = "WHERE c.id::text = :cid" if company_id else ""
        if company_id:
            params["cid"] = company_id
        sql = f"""
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                (SELECT cp.id FROM company_policies cp WHERE cp.company_id = c.id::text ORDER BY cp.created_at DESC LIMIT 1) AS policy_id,
                (SELECT cp.title FROM company_policies cp WHERE cp.company_id = c.id::text ORDER BY cp.created_at DESC LIMIT 1) AS policy_title,
                (SELECT cp.extraction_status FROM company_policies cp WHERE cp.company_id = c.id::text ORDER BY cp.created_at DESC LIMIT 1) AS extraction_status,
                (SELECT cp.created_at FROM company_policies cp WHERE cp.company_id = c.id::text ORDER BY cp.created_at DESC LIMIT 1) AS policy_updated_at,
                (SELECT COUNT(*) FROM policy_documents pd WHERE pd.company_id = c.id::text) AS doc_count,
                (SELECT COUNT(*) FROM policy_versions pv
                 JOIN company_policies cp2 ON cp2.id = pv.policy_id WHERE cp2.company_id = c.id::text) AS version_count,
                (SELECT pv2.status FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id::text
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_status,
                (SELECT pv2.version_number FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id::text
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_number,
                (SELECT pv2.updated_at FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id::text
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_updated_at,
                (SELECT COUNT(*) FROM resolved_assignment_policies rap
                 JOIN case_assignments ca ON ca.id = rap.assignment_id
                 LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("ca")}
                 WHERE rc.company_id = c.id::text) AS resolved_count
            FROM companies c
            {where}
            ORDER BY c.name ASC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        result = []
        for row in rows:
            m = row._mapping
            status = "no_policy"
            if m.get("policy_id"):
                vs = m.get("latest_version_status")
                if vs == "published":
                    status = "published"
                elif vs == "reviewed":
                    status = "reviewed"
                elif vs == "review_required":
                    status = "review_required"
                elif vs:
                    status = "draft"
            r = dict(m)
            r["policy_status"] = status
            result.append(r)
        return result

    def get_admin_policy_detail(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Admin: single policy with company, versions, published version."""
        policy = self.get_company_policy(policy_id)
        if not policy:
            return None
        cid = policy.get("company_id")
        company = self.get_company(cid) if cid else None
        versions = self.list_policy_versions(policy_id)
        published = self.get_published_policy_version(policy_id)
        doc_count = len(self.list_policy_documents(cid)) if cid else 0
        out = dict(policy)
        out["company_name"] = company.get("name") if company else None
        out["source_document_count"] = doc_count
        out["versions"] = versions
        out["published_version"] = published
        out["published_version_id"] = published.get("id") if published else None
        out["published_at"] = published.get("updated_at") if published else None
        return out

    def list_default_policy_templates(self) -> List[Dict[str, Any]]:
        """List platform default policy templates (for admin UI)."""
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT id, template_name, version, status, is_default_template, snapshot_json, created_at, updated_at "
                        "FROM default_policy_templates ORDER BY is_default_template DESC, created_at ASC"
                    ),
                    {},
                ).fetchall()
            items = self._rows_to_list(rows)
            for d in items:
                self._parse_json_col(d, "snapshot_json")
                if d.get("is_default_template") is not None and not isinstance(d["is_default_template"], bool):
                    d["is_default_template"] = bool(d["is_default_template"])
            return items
        except (OperationalError, ProgrammingError, OSError, ValueError) as e:
            log.warning("list_default_policy_templates failed (returning empty): %s", e)
            return []
        except Exception as e:
            log.warning("list_default_policy_templates unexpected error (returning empty): %s", e, exc_info=True)
            return []

    def get_default_policy_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get one default policy template by id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM default_policy_templates WHERE id = :id"),
                {"id": template_id},
            ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        self._parse_json_col(d, "snapshot_json")
        if d.get("is_default_template") is not None and not isinstance(d["is_default_template"], bool):
            d["is_default_template"] = bool(d["is_default_template"])
        return d

    def get_admin_policies_index(
        self, company_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List company_policies for admin with company name; optional company_id filter.
        Returns (list of policies), summary with count and orphans_without_company.
        """
        params: Dict[str, Any] = {}
        where = "WHERE 1=1"
        if company_id:
            where += " AND cp.company_id = :cid"
            params["cid"] = company_id
        sql = f"""
            SELECT cp.id, cp.company_id, cp.title, cp.version, cp.effective_date, cp.file_url, cp.file_type,
                   cp.extraction_status, cp.extracted_at, cp.created_by, cp.created_at,
                   c.name AS company_name
            FROM company_policies cp
            LEFT JOIN companies c ON CAST(c.id AS TEXT) = cp.company_id
            {where}
            ORDER BY cp.company_id, cp.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        policies = [dict(r._mapping) for r in rows]
        try:
            orphan_sql = text("""
                SELECT COUNT(*) AS n FROM company_policies cp
                WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = cp.company_id)
            """)
            with self.engine.connect() as conn:
                o = conn.execute(orphan_sql, {}).fetchone()
            orphans = int(o._mapping["n"]) if o else 0
        except Exception as e:
            log.warning("admin_policies_index: orphan count failed: %s", e)
            orphans = 0
        summary = {"count": len(policies), "orphans_without_company": orphans}
        return policies, summary

    def policy_assistant_tables_available(self) -> bool:
        """True when policy assistant import tables exist (migration applied)."""
        from ..database import _is_sqlite  # lazy: avoid import cycle
        try:
            with self.engine.connect() as conn:
                if _is_sqlite:
                    r = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='policy_document_chunks'"
                        )
                    ).fetchone()
                    return r is not None
                r = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'policy_document_chunks'"
                    )
                ).fetchone()
                return r is not None
        except Exception:
            return False

    def clear_policy_assistant_pipeline_for_document(self, doc_id: str) -> None:
        """
        Append-only pipeline: snapshots and chunks are not bulk-deleted here.
        Each extraction creates a new snapshot revision and new chunk rows linked by snapshot_id.
        """
        return

    def insert_policy_processing_run(
        self,
        doc_id: str,
        run_type: str,
        status: str = "running",
    ) -> str:
        rid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_processing_runs
                    (id, policy_document_id, run_type, status, started_at)
                    VALUES (:id, :doc, :rt, :st, :now)
                    """
                ),
                {"id": rid, "doc": doc_id, "rt": run_type, "st": status, "now": now},
            )
        return rid

    def finish_policy_processing_run(
        self,
        run_id: str,
        status: str,
        error_message: Optional[str] = None,
        metrics_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE policy_processing_runs
                    SET status = :st, finished_at = :now, error_message = :em, metrics_json = :mj
                    WHERE id = :id
                    """
                ),
                {
                    "id": run_id,
                    "st": status,
                    "now": now,
                    "em": error_message,
                    "mj": json.dumps(metrics_json) if metrics_json is not None else None,
                },
            )

    def insert_policy_document_chunk(
        self,
        doc_id: str,
        chunk_index: int,
        text_content: str,
        *,
        page_number: Optional[int] = None,
        section_title: Optional[str] = None,
        token_count: Optional[int] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
    ) -> str:
        cid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        meta = metadata_json if metadata_json is not None else {}
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_document_chunks
                    (id, policy_document_id, chunk_index, page_number, section_title,
                     text_content, token_count, metadata_json, created_at, snapshot_id)
                    VALUES (:id, :doc, :idx, :pn, :st, :tx, :tc, :mj, :now, :snap)
                    """
                ),
                {
                    "id": cid,
                    "doc": doc_id,
                    "idx": chunk_index,
                    "pn": page_number,
                    "st": section_title,
                    "tx": text_content,
                    "tc": token_count,
                    "mj": json.dumps(meta),
                    "now": now,
                    "snap": snapshot_id,
                },
            )
        return cid

    def canonical_policy_tables_available(self) -> bool:
        from ..database import _is_sqlite  # lazy: avoid import cycle
        try:
            with self.engine.connect() as conn:
                if _is_sqlite:
                    row = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='canonical_policy_documents'"
                        )
                    ).fetchone()
                    return row is not None
                row = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'canonical_policy_documents'"
                    )
                ).fetchone()
                return row is not None
        except Exception:
            return False

    def insert_canonical_policy_document(
        self,
        *,
        company_id: str,
        source_policy_document_id: Optional[str] = None,
        source_type: str = "local_file",
        source_uri: Optional[str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        title: Optional[str] = None,
        policy_scope: Optional[str] = None,
        document_type: Optional[str] = None,
        version_label: Optional[str] = None,
        effective_date: Optional[str] = None,
        default_currency: Optional[str] = None,
        assignment_types: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
        normalized_text: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        ingestion_status: str = "ingested",
        extraction_status: str = "pending",
    ) -> str:
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO canonical_policy_documents
                    (id, company_id, source_policy_document_id, source_type, source_uri, filename, mime_type, title,
                     policy_scope, document_type, version_label, effective_date, default_currency,
                     assignment_types_json, raw_text, normalized_text, metadata_json, ingestion_status,
                     extraction_status, created_at, updated_at)
                    VALUES (:id, :company_id, :src_doc, :src_type, :src_uri, :filename, :mime_type, :title,
                     :policy_scope, :document_type, :version_label, :effective_date, :default_currency,
                     :assignment_types_json, :raw_text, :normalized_text, :metadata_json, :ingestion_status,
                     :extraction_status, :now, :now)
                    """
                ),
                {
                    "id": doc_id,
                    "company_id": company_id,
                    "src_doc": source_policy_document_id,
                    "src_type": source_type,
                    "src_uri": source_uri,
                    "filename": filename,
                    "mime_type": mime_type,
                    "title": title,
                    "policy_scope": policy_scope,
                    "document_type": document_type,
                    "version_label": version_label,
                    "effective_date": effective_date,
                    "default_currency": default_currency,
                    "assignment_types_json": json.dumps(assignment_types or []),
                    "raw_text": raw_text,
                    "normalized_text": normalized_text,
                    "metadata_json": json.dumps(metadata_json or {}),
                    "ingestion_status": ingestion_status,
                    "extraction_status": extraction_status,
                    "now": now,
                },
            )
        return doc_id

    def update_canonical_policy_document(self, document_id: str, **kwargs: Any) -> None:
        fields = ["updated_at = :updated_at"]
        params: Dict[str, Any] = {"id": document_id, "updated_at": datetime.utcnow().isoformat()}
        mapping = {
            "company_id": "company_id",
            "title": "title",
            "policy_scope": "policy_scope",
            "document_type": "document_type",
            "version_label": "version_label",
            "effective_date": "effective_date",
            "default_currency": "default_currency",
            "raw_text": "raw_text",
            "normalized_text": "normalized_text",
            "ingestion_status": "ingestion_status",
            "extraction_status": "extraction_status",
            "filename": "filename",
            "mime_type": "mime_type",
        }
        for key, col in mapping.items():
            if key in kwargs and kwargs[key] is not None:
                fields.append(f"{col} = :{key}")
                params[key] = kwargs[key]
        if "assignment_types" in kwargs and kwargs["assignment_types"] is not None:
            fields.append("assignment_types_json = :assignment_types_json")
            params["assignment_types_json"] = json.dumps(kwargs["assignment_types"])
        if "metadata_json" in kwargs and kwargs["metadata_json"] is not None:
            fields.append("metadata_json = :metadata_json")
            params["metadata_json"] = json.dumps(kwargs["metadata_json"])
        if len(fields) == 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE canonical_policy_documents SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def get_canonical_policy_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        from ..database import _coerce_json_dict, _coerce_json_list  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM canonical_policy_documents WHERE id = :id"),
                {"id": document_id},
            ).fetchone()
        doc = self._row_to_dict(row)
        if not doc:
            return None
        doc["assignment_types_json"] = _coerce_json_list(doc.get("assignment_types_json"))
        doc["metadata_json"] = _coerce_json_dict(doc.get("metadata_json"))
        return doc

    def list_canonical_policy_documents(
        self,
        *,
        company_id: Optional[str] = None,
        source_policy_document_id: Optional[str] = None,
        extraction_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_dict, _coerce_json_list  # lazy: avoid import cycle
        sql = "SELECT * FROM canonical_policy_documents WHERE 1=1"
        params: Dict[str, Any] = {}
        if company_id:
            sql += " AND company_id = :company_id"
            params["company_id"] = company_id
        if source_policy_document_id:
            sql += " AND source_policy_document_id = :src_doc"
            params["src_doc"] = source_policy_document_id
        if extraction_status:
            sql += " AND extraction_status = :st"
            params["st"] = extraction_status
        sql += " ORDER BY created_at DESC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["assignment_types_json"] = _coerce_json_list(item.get("assignment_types_json"))
            item["metadata_json"] = _coerce_json_dict(item.get("metadata_json"))
        return items

    def delete_canonical_policy_artifacts(self, document_id: str) -> None:
        if not self.canonical_policy_tables_available():
            return
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM canonical_policy_fact_validation_errors WHERE canonical_policy_document_id = :id"),
                {"id": document_id},
            )
            conn.execute(
                text("DELETE FROM canonical_policy_facts WHERE canonical_policy_document_id = :id"),
                {"id": document_id},
            )
            conn.execute(
                text("DELETE FROM canonical_policy_document_chunks WHERE canonical_policy_document_id = :id"),
                {"id": document_id},
            )

    def insert_canonical_policy_document_chunk(
        self,
        *,
        company_id: str,
        canonical_policy_document_id: str,
        chunk_index: int,
        section_path: Optional[str],
        structure_type: Optional[str],
        page_number: Optional[int],
        char_start: Optional[int],
        char_end: Optional[int],
        text_content: str,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        chunk_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO canonical_policy_document_chunks
                    (id, company_id, canonical_policy_document_id, chunk_index, section_path, structure_type,
                     page_number, char_start, char_end, text_content, metadata_json, created_at)
                    VALUES (:id, :company_id, :doc_id, :chunk_index, :section_path, :structure_type,
                     :page_number, :char_start, :char_end, :text_content, :metadata_json, :created_at)
                    """
                ),
                {
                    "id": chunk_id,
                    "company_id": company_id,
                    "doc_id": canonical_policy_document_id,
                    "chunk_index": chunk_index,
                    "section_path": section_path,
                    "structure_type": structure_type,
                    "page_number": page_number,
                    "char_start": char_start,
                    "char_end": char_end,
                    "text_content": text_content,
                    "metadata_json": json.dumps(metadata_json or {}),
                    "created_at": now,
                },
            )
        return chunk_id

    def list_canonical_policy_document_chunks(self, document_id: str, *, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_dict  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            sql = (
                "SELECT * FROM canonical_policy_document_chunks "
                "WHERE canonical_policy_document_id = :id"
            )
            params: Dict[str, Any] = {"id": document_id}
            if company_id:
                sql += " AND company_id = :company_id"
                params["company_id"] = company_id
            sql += " ORDER BY chunk_index ASC"
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["metadata_json"] = _coerce_json_dict(item.get("metadata_json"))
        return items

    def insert_canonical_policy_fact(
        self,
        *,
        company_id: str,
        canonical_policy_document_id: str,
        canonical_policy_document_chunk_id: str,
        source_policy_document_id: Optional[str] = None,
        phase: Optional[str] = None,
        benefit_category: Optional[str] = None,
        value_type: str,
        frequency: Optional[str] = None,
        provider_entity: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        eligibility_json: Optional[Dict[str, Any]] = None,
        assignment_types_json: Optional[List[str]] = None,
        amount: Optional[Any] = None,
        currency: Optional[str] = None,
        percentage: Optional[float] = None,
        quantity: Optional[float] = None,
        duration_value: Optional[int] = None,
        duration_unit: Optional[str] = None,
        value_text: Optional[str] = None,
        is_taxable: Optional[bool] = None,
        reimbursement_required: Optional[bool] = None,
        source_quote: Optional[str] = None,
        confidence_score: Optional[float] = None,
        raw_payload_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        from ..database import _policy_bool_bind  # lazy: avoid import cycle
        fact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO canonical_policy_facts
                    (id, company_id, canonical_policy_document_id, canonical_policy_document_chunk_id, source_policy_document_id,
                     phase, benefit_category, value_type, frequency, provider_entity, title, description,
                     eligibility_json, assignment_types_json, amount, currency, percentage, quantity,
                     duration_value, duration_unit, value_text, is_taxable, reimbursement_required,
                     source_quote, confidence_score, raw_payload_json, created_at)
                    VALUES (:id, :company_id, :doc_id, :chunk_id, :src_doc, :phase, :benefit_category, :value_type,
                     :frequency, :provider_entity, :title, :description, :eligibility_json,
                     :assignment_types_json, :amount, :currency, :percentage, :quantity, :duration_value,
                     :duration_unit, :value_text, :is_taxable, :reimbursement_required, :source_quote,
                     :confidence_score, :raw_payload_json, :created_at)
                    """
                ),
                {
                    "id": fact_id,
                    "company_id": company_id,
                    "doc_id": canonical_policy_document_id,
                    "chunk_id": canonical_policy_document_chunk_id,
                    "src_doc": source_policy_document_id,
                    "phase": phase,
                    "benefit_category": benefit_category,
                    "value_type": value_type,
                    "frequency": frequency,
                    "provider_entity": provider_entity,
                    "title": title,
                    "description": description,
                    "eligibility_json": json.dumps(eligibility_json or {}),
                    "assignment_types_json": json.dumps(assignment_types_json or []),
                    "amount": amount,
                    "currency": currency,
                    "percentage": percentage,
                    "quantity": quantity,
                    "duration_value": duration_value,
                    "duration_unit": duration_unit,
                    "value_text": value_text,
                    "is_taxable": None if is_taxable is None else _policy_bool_bind(is_taxable),
                    "reimbursement_required": None if reimbursement_required is None else _policy_bool_bind(reimbursement_required),
                    "source_quote": source_quote,
                    "confidence_score": confidence_score,
                    "raw_payload_json": json.dumps(raw_payload_json or {}),
                    "created_at": now,
                },
            )
        return fact_id

    def list_canonical_policy_facts(
        self,
        document_id: str,
        *,
        company_id: Optional[str] = None,
        phase: Optional[str] = None,
        benefit_category: Optional[str] = None,
        value_type: Optional[str] = None,
        provider_entity: Optional[str] = None,
        assignment_type: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List canonical policy facts for a document, scoped by company.

        The ``tier`` kwarg implements the P5-9 C1 tier isolation rule
        (migration ``20260522160000_canonical_policy_facts_tier.sql``):

        - ``tier=None``  → no tier filter (HR/admin path: return everything)
        - ``tier="X"``   → return facts where ``tier IS NULL OR tier = 'X'``.
                          NULL rows are universal (apply to every tier).

        Callers in the assistant retrieval path MUST pass the caller's
        resolved tier; passing ``None`` there leaks Executive-tier
        content to lower-tier employees.
        """
        from ..database import _coerce_json_dict, _coerce_json_list  # lazy: avoid import cycle
        sql = "SELECT * FROM canonical_policy_facts WHERE canonical_policy_document_id = :id"
        params: Dict[str, Any] = {"id": document_id}
        if company_id:
            sql += " AND company_id = :company_id"
            params["company_id"] = company_id
        if phase:
            sql += " AND phase = :phase"
            params["phase"] = phase
        if benefit_category:
            sql += " AND benefit_category = :benefit_category"
            params["benefit_category"] = benefit_category
        if value_type:
            sql += " AND value_type = :value_type"
            params["value_type"] = value_type
        if provider_entity:
            sql += " AND provider_entity = :provider_entity"
            params["provider_entity"] = provider_entity
        # [P5-9 C1] Tier isolation: include only matching tier + universal (NULL).
        if tier is not None:
            sql += " AND (tier IS NULL OR tier = :tier_filter)"
            params["tier_filter"] = tier
        sql += " ORDER BY created_at ASC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        out: List[Dict[str, Any]] = []
        for item in items:
            item["eligibility_json"] = _coerce_json_dict(item.get("eligibility_json"))
            item["assignment_types_json"] = _coerce_json_list(item.get("assignment_types_json"))
            item["raw_payload_json"] = _coerce_json_dict(item.get("raw_payload_json"))
            if item.get("is_taxable") in (0, 1):
                item["is_taxable"] = bool(item["is_taxable"])
            if item.get("reimbursement_required") in (0, 1):
                item["reimbursement_required"] = bool(item["reimbursement_required"])
            if assignment_type and assignment_type not in item["assignment_types_json"]:
                continue
            out.append(item)
        return out

    def insert_canonical_policy_validation_error(
        self,
        *,
        company_id: str,
        canonical_policy_document_id: str,
        canonical_policy_document_chunk_id: str,
        raw_payload_json: Optional[Dict[str, Any]] = None,
        errors_json: Optional[List[str]] = None,
    ) -> str:
        error_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO canonical_policy_fact_validation_errors
                    (id, company_id, canonical_policy_document_id, canonical_policy_document_chunk_id,
                     raw_payload_json, errors_json, created_at)
                    VALUES (:id, :company_id, :doc_id, :chunk_id, :raw_payload_json, :errors_json, :created_at)
                    """
                ),
                {
                    "id": error_id,
                    "company_id": company_id,
                    "doc_id": canonical_policy_document_id,
                    "chunk_id": canonical_policy_document_chunk_id,
                    "raw_payload_json": json.dumps(raw_payload_json or {}),
                    "errors_json": json.dumps(errors_json or []),
                    "created_at": now,
                },
            )
        return error_id

    def list_canonical_policy_validation_errors(self, document_id: str, *, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_dict, _coerce_json_list  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            sql = (
                "SELECT * FROM canonical_policy_fact_validation_errors "
                "WHERE canonical_policy_document_id = :id"
            )
            params: Dict[str, Any] = {"id": document_id}
            if company_id:
                sql += " AND company_id = :company_id"
                params["company_id"] = company_id
            sql += " ORDER BY created_at ASC"
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["raw_payload_json"] = _coerce_json_dict(item.get("raw_payload_json"))
            item["errors_json"] = _coerce_json_list(item.get("errors_json"))
        return items

    def get_canonical_policy_audit_summary(self, document_id: str, *, company_id: Optional[str] = None) -> Dict[str, Any]:
        chunks = self.list_canonical_policy_document_chunks(document_id, company_id=company_id)
        facts = self.list_canonical_policy_facts(document_id, company_id=company_id)
        errors = self.list_canonical_policy_validation_errors(document_id, company_id=company_id)
        by_category: Dict[str, int] = {}
        by_phase: Dict[str, int] = {}
        for fact in facts:
            cat = str(fact.get("benefit_category") or "uncategorized")
            ph = str(fact.get("phase") or "unspecified")
            by_category[cat] = by_category.get(cat, 0) + 1
            by_phase[ph] = by_phase.get(ph, 0) + 1
        valid = len(facts)
        total = valid + len(errors)
        return {
            "document_id": document_id,
            "chunks_count": len(chunks),
            "facts_count": valid,
            "validation_error_count": len(errors),
            "validation_pass_rate": (valid / total) if total else 1.0,
            "counts_by_category": by_category,
            "counts_by_phase": by_phase,
        }

    def insert_canonical_policy_query_audit_log(
        self,
        *,
        company_id: str,
        user_id: str,
        user_role: str,
        canonical_policy_document_id: str,
        query_text: str,
        redacted_query_text: str,
        retrieved_chunk_ids: List[str],
        answer_preview: Optional[str],
    ) -> str:
        audit_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO canonical_policy_query_audit_logs
                    (id, company_id, user_id, user_role, canonical_policy_document_id, query_text,
                     redacted_query_text, retrieved_chunk_ids_json, answer_preview, created_at)
                    VALUES (:id, :company_id, :user_id, :user_role, :canonical_policy_document_id, :query_text,
                     :redacted_query_text, :retrieved_chunk_ids_json, :answer_preview, :created_at)
                    """
                ),
                {
                    "id": audit_id,
                    "company_id": company_id,
                    "user_id": user_id,
                    "user_role": user_role,
                    "canonical_policy_document_id": canonical_policy_document_id,
                    "query_text": query_text,
                    "redacted_query_text": redacted_query_text,
                    "retrieved_chunk_ids_json": json.dumps(retrieved_chunk_ids),
                    "answer_preview": answer_preview,
                    "created_at": now,
                },
            )
        return audit_id

    def list_canonical_policy_query_audit_logs(
        self,
        *,
        company_id: Optional[str] = None,
        canonical_policy_document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_list  # lazy: avoid import cycle
        sql = "SELECT * FROM canonical_policy_query_audit_logs WHERE 1=1"
        params: Dict[str, Any] = {"limit": limit}
        if company_id:
            sql += " AND company_id = :company_id"
            params["company_id"] = company_id
        if canonical_policy_document_id:
            sql += " AND canonical_policy_document_id = :canonical_policy_document_id"
            params["canonical_policy_document_id"] = canonical_policy_document_id
        if user_id:
            sql += " AND user_id = :user_id"
            params["user_id"] = user_id
        sql += " ORDER BY created_at DESC LIMIT :limit"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["retrieved_chunk_ids_json"] = _coerce_json_list(item.get("retrieved_chunk_ids_json"))
        return items

    def insert_policy_assistant_trace(
        self,
        *,
        trace_id: str,
        session_id: Optional[str],
        query_hash: str,
        company_id: str,
        steps_json: str,
        total_latency_ms: int,
        fallback_triggered: bool,
        feature_key: Optional[str] = None,
        customer_id: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        cost_usd_estimated: Optional[float] = None,
        co2e_grams_estimated: Optional[float] = None,
        prompt_version_id: Optional[str] = None,
        canary_arm: Optional[str] = None,
        cited_chunk_ids: Optional[List[str]] = None,
        answer_kind: Optional[str] = None,
        grounding_verdict: Optional[str] = None,
        verification_skipped: Optional[bool] = None,
        grounding_score: Optional[float] = None,
    ) -> None:
        """
        Persist one trace row. Called by ai_trace_logger._write_to_db().
        Never raises — caller wraps in try/except.
        Raw query text is NOT passed here; only the anonymised query_hash.

        Parker Step G: feature_key / customer_id + token / cost / CO2e estimates feed
        the per-customer unit-economics rollup.
        Parker Step D: prompt_version_id / canary_arm attribute the trace to a registry
        arm; both None when the registry was absent (literal fallback).
        """
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_assistant_traces
                    (id, session_id, query_hash, company_id, steps_json,
                     total_latency_ms, fallback_triggered,
                     feature_key, customer_id, tokens_in, tokens_out,
                     cost_usd_estimated, co2e_grams_estimated,
                     prompt_version_id, canary_arm, cited_chunk_ids,
                     answer_kind, grounding_verdict, verification_skipped,
                     grounding_score, created_at)
                    VALUES (:id, :sid, :qh, :cid, :sj, :lms, :fb,
                            :fk, :cust, :tin, :tout, :cost, :co2e,
                            :pvid, :arm, :cc,
                            :ak, :gv, :vs, :gs, :now)
                    ON CONFLICT(id) DO NOTHING
                    """
                ),
                {
                    "id": trace_id,
                    "sid": session_id,
                    "qh": query_hash,
                    "cid": company_id,
                    "sj": steps_json,
                    "lms": int(total_latency_ms),
                    "fb": 1 if fallback_triggered else 0,
                    "fk": feature_key,
                    "cust": customer_id,
                    "tin": int(tokens_in) if tokens_in is not None else None,
                    "tout": int(tokens_out) if tokens_out is not None else None,
                    "cost": float(cost_usd_estimated) if cost_usd_estimated is not None else None,
                    "co2e": float(co2e_grams_estimated) if co2e_grams_estimated is not None else None,
                    "pvid": prompt_version_id,
                    "arm": canary_arm,
                    "cc": json.dumps(list(cited_chunk_ids or [])),
                    "ak": answer_kind,
                    "gv": grounding_verdict,
                    # OBS-1 (AIQ-1242): bind a real bool — the column is Postgres
                    # `boolean`, and binding int 1/0 makes Postgres reject the INSERT
                    # ("type boolean but expression is of type integer"), which the
                    # tracer swallows → every successful policy-assistant trace was
                    # silently dropped (only None/NULL fallbacks survived). SQLite
                    # accepts int-into-boolean, so unit tests never caught it.
                    "vs": bool(verification_skipped) if verification_skipped is not None else None,
                    "gs": float(grounding_score) if grounding_score is not None else None,
                    "now": now,
                },
            )

    def list_policy_knowledge_snapshots_for_document(self, policy_document_id: str) -> List[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_knowledge_snapshots WHERE policy_document_id = :id "
                    "ORDER BY revision_number DESC, created_at DESC"
                ),
                {"id": policy_document_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_processing_runs_for_document(self, policy_document_id: str) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_dict  # lazy: avoid import cycle
        if not self.policy_assistant_tables_available():
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_processing_runs WHERE policy_document_id = :id "
                    "ORDER BY started_at DESC"
                ),
                {"id": policy_document_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            if d.get("metrics_json"):
                d["metrics_json"] = _coerce_json_dict(d.get("metrics_json"))
        return items

    def latest_policy_processing_run(self, doc_id: str, run_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        from ..database import _coerce_json_dict  # lazy: avoid import cycle
        if not self.policy_assistant_tables_available():
            return None
        sql = (
            "SELECT * FROM policy_processing_runs WHERE policy_document_id = :id "
        )
        params: Dict[str, Any] = {"id": doc_id}
        if run_type:
            sql += " AND run_type = :rt "
            params["rt"] = run_type
        sql += " ORDER BY started_at DESC LIMIT 1"
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), params).fetchone()
        d = self._row_to_dict(row) if row else None
        if d and d.get("metrics_json"):
            d["metrics_json"] = _coerce_json_dict(d.get("metrics_json"))
        return d

    @staticmethod
    def _coerce_policy_boolean_fields(payload: Dict[str, Any], boolean_keys: List[str]) -> Dict[str, Any]:
        """Ensure boolean DB columns receive Python bool, not int. Safe for Postgres."""
        out = dict(payload)
        for k in boolean_keys:
            if k in out and out[k] is not None:
                v = out[k]
                if isinstance(v, int):
                    out[k] = bool(v)
                elif not isinstance(v, bool):
                    out[k] = bool(v)
        return out

    def list_hr_benefit_rule_overrides(self, policy_version_id: str) -> List[Dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT * FROM policy_benefit_rule_hr_overrides
                        WHERE policy_version_id = :vid
                        ORDER BY benefit_rule_id
                        """
                    ),
                    {"vid": str(policy_version_id)},
                ).fetchall()
        except Exception:
            return []
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "duration_quantity_json")
            avo = d.get("approval_required_override")
            if avo is not None and not isinstance(avo, bool):
                try:
                    d["approval_required_override"] = bool(int(avo))
                except (TypeError, ValueError):
                    d["approval_required_override"] = bool(avo)
        return items

    def get_hr_benefit_rule_override(
        self, policy_version_id: str, benefit_rule_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT * FROM policy_benefit_rule_hr_overrides
                        WHERE policy_version_id = :vid AND benefit_rule_id = :bid
                        """
                    ),
                    {"vid": str(policy_version_id), "bid": str(benefit_rule_id)},
                ).fetchone()
        except Exception:
            return None
        d = self._row_to_dict(row)
        if not d:
            return None
        self._parse_json_col(d, "duration_quantity_json")
        avo = d.get("approval_required_override")
        if avo is not None and not isinstance(avo, bool):
            try:
                d["approval_required_override"] = bool(int(avo))
            except (TypeError, ValueError):
                d["approval_required_override"] = bool(avo)
        return d

    def upsert_hr_benefit_rule_override(
        self,
        policy_version_id: str,
        benefit_rule_id: str,
        patch: Dict[str, Any],
        *,
        actor_id: Optional[str] = None,
    ) -> str:
        """
        Merge patch into existing override row (or create). Only keys present in patch are updated.
        """
        from ..database import _is_sqlite  # lazy: avoid import cycle
        vid, bid = str(policy_version_id), str(benefit_rule_id)
        prev = self.get_hr_benefit_rule_override(vid, bid)
        prev_json = json.dumps(prev, default=str) if prev else None
        merge: Dict[str, Any] = dict(prev) if prev else {}
        override_keys = (
            "service_visibility",
            "amount_value_override",
            "amount_unit_override",
            "currency_override",
            "duration_quantity_json",
            "approval_required_override",
            "hr_notes",
        )
        for k in override_keys:
            if k in patch:
                merge[k] = patch[k]
        now = datetime.utcnow().isoformat()
        oid = str(merge.get("id")) if merge.get("id") else str(uuid.uuid4())

        dqj = merge.get("duration_quantity_json")
        if isinstance(dqj, dict):
            dqj_s = json.dumps(dqj)
        elif isinstance(dqj, str):
            dqj_s = dqj
        else:
            dqj_s = None

        apbind = merge.get("approval_required_override")
        if _is_sqlite and apbind is not None:
            apbind = 1 if apbind else 0

        params = {
            "id": oid,
            "vid": vid,
            "bid": bid,
            "sv": merge.get("service_visibility"),
            "avo": merge.get("amount_value_override"),
            "auo": merge.get("amount_unit_override"),
            "cur": merge.get("currency_override"),
            "dqj": dqj_s,
            "aro": apbind,
            "notes": merge.get("hr_notes"),
            "actor": actor_id,
            "now": now,
        }

        with self.engine.begin() as conn:
            if prev:
                conn.execute(
                    text(
                        """
                        UPDATE policy_benefit_rule_hr_overrides SET
                          service_visibility = :sv,
                          amount_value_override = :avo,
                          amount_unit_override = :auo,
                          currency_override = :cur,
                          duration_quantity_json = :dqj,
                          approval_required_override = :aro,
                          hr_notes = :notes,
                          updated_by = :actor,
                          updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    params,
                )
                action = "update"
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO policy_benefit_rule_hr_overrides
                        (id, policy_version_id, benefit_rule_id, service_visibility,
                         amount_value_override, amount_unit_override, currency_override,
                         duration_quantity_json, approval_required_override, hr_notes,
                         created_by, updated_by, created_at, updated_at)
                        VALUES (:id, :vid, :bid, :sv, :avo, :auo, :cur, :dqj, :aro, :notes, :actor, :actor, :now, :now)
                        """
                    ),
                    params,
                )
                action = "insert"

        new_row = self.get_hr_benefit_rule_override(vid, bid)
        new_json = json.dumps(new_row, default=str) if new_row else None
        self._append_hr_benefit_rule_override_audit(oid, action, prev_json, new_json, actor_id)
        return oid

    def _append_hr_benefit_rule_override_audit(
        self,
        override_id: str,
        action: str,
        previous_json: Optional[str],
        new_json: Optional[str],
        actor_id: Optional[str],
    ) -> None:
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO policy_benefit_rule_hr_override_audit
                        (id, override_id, action, previous_json, new_json, actor_id, created_at)
                        VALUES (:id, :oid, :act, :prev, :newj, :actor, :now)
                        """
                    ),
                    {
                        "id": aid,
                        "oid": str(override_id),
                        "act": action,
                        "prev": previous_json,
                        "newj": new_json,
                        "actor": actor_id,
                        "now": now,
                    },
                )
        except Exception as exc:
            log.warning("hr override audit append failed: %s", exc)

    def delete_hr_benefit_rule_override(
        self, policy_version_id: str, benefit_rule_id: str, *, actor_id: Optional[str] = None
    ) -> bool:
        prev = self.get_hr_benefit_rule_override(policy_version_id, benefit_rule_id)
        if not prev:
            return False
        oid = str(prev.get("id"))
        prev_json = json.dumps(prev, default=str)
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM policy_benefit_rule_hr_overrides WHERE id = :id"),
                    {"id": oid},
                )
        except Exception:
            return False
        self._append_hr_benefit_rule_override_audit(oid, "delete", prev_json, None, actor_id)
        return True

    def list_policy_source_links(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_source_links WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def insert_policy_benefit_rule(self, rule: Dict[str, Any], *, connection: Any = None) -> str:
        from ..database import _policy_ag_sql, _policy_bool_bind  # lazy: avoid import cycle
        rid = rule.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        bind = {
            "id": rid,
            "vid": rule["policy_version_id"],
            "bk": rule["benefit_key"],
            "bc": rule["benefit_category"],
            "ct": rule.get("calc_type"),
            "av": rule.get("amount_value"),
            "au": rule.get("amount_unit"),
            "cur": rule.get("currency"),
            "freq": rule.get("frequency"),
            "desc": rule.get("description"),
            "meta": json.dumps(rule.get("metadata_json")) if rule.get("metadata_json") else None,
            "ag": _policy_bool_bind(rule.get("auto_generated", True)),
            "rs": rule.get("review_status", "pending"),
            "conf": rule.get("confidence"),
            "raw": rule.get("raw_text"),
            "now": now,
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text(f"""
                    INSERT INTO policy_benefit_rules
                    (id, policy_version_id, benefit_key, benefit_category, calc_type, amount_value,
                     amount_unit, currency, frequency, description, metadata_json, auto_generated,
                     review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :bk, :bc, :ct, :av, :au, :cur, :freq, :desc, :meta, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return rid

    def insert_policy_exclusion(self, excl: Dict[str, Any], *, connection: Any = None) -> str:
        from ..database import _policy_ag_sql, _policy_bool_bind  # lazy: avoid import cycle
        eid = excl.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        bind = {
            "id": eid,
            "vid": excl["policy_version_id"],
            "bk": excl.get("benefit_key"),
            "dom": excl["domain"],
            "desc": excl.get("description"),
            "ag": _policy_bool_bind(excl.get("auto_generated", True)),
            "rs": excl.get("review_status", "pending"),
            "conf": excl.get("confidence"),
            "raw": excl.get("raw_text"),
            "now": now,
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text(f"""
                    INSERT INTO policy_exclusions
                    (id, policy_version_id, benefit_key, domain, description, auto_generated,
                     review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :bk, :dom, :desc, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return eid

    def insert_policy_evidence_requirement(self, ev: Dict[str, Any], *, connection: Any = None) -> str:
        from ..database import _policy_ag_sql, _policy_bool_bind  # lazy: avoid import cycle
        eid = ev.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        bind = {
            "id": eid,
            "vid": ev["policy_version_id"],
            "brid": ev.get("benefit_rule_id"),
            "items": json.dumps(ev.get("evidence_items_json") or []),
            "desc": ev.get("description"),
            "ag": _policy_bool_bind(ev.get("auto_generated", True)),
            "rs": ev.get("review_status", "pending"),
            "conf": ev.get("confidence"),
            "raw": ev.get("raw_text"),
            "now": now,
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text(f"""
                    INSERT INTO policy_evidence_requirements
                    (id, policy_version_id, benefit_rule_id, evidence_items_json, description,
                     auto_generated, review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :brid, :items, :desc, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return eid

    def insert_policy_rule_condition(self, cond: Dict[str, Any], *, connection: Any = None) -> str:
        from ..database import _policy_ag_sql, _policy_bool_bind  # lazy: avoid import cycle
        cid = cond.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        bind = {
            "id": cid,
            "vid": cond["policy_version_id"],
            "ot": cond["object_type"],
            "oid": cond["object_id"],
            "ct": cond["condition_type"],
            "val": json.dumps(cond.get("condition_value_json") or {}),
            "ag": _policy_bool_bind(cond.get("auto_generated", True)),
            "rs": cond.get("review_status", "pending"),
            "conf": cond.get("confidence"),
            "now": now,
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text(f"""
                    INSERT INTO policy_rule_conditions
                    (id, policy_version_id, object_type, object_id, condition_type, condition_value_json,
                     auto_generated, review_status, confidence, created_at, updated_at)
                    VALUES (:id, :vid, :ot, :oid, :ct, :val, {ag_sql}, :rs, :conf, :now, :now)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return cid

    def insert_policy_family_applicability(self, app: Dict[str, Any], *, connection: Any = None) -> str:
        fid = app.get("id") or str(uuid.uuid4())
        bind = {
            "id": fid,
            "vid": app["policy_version_id"],
            "brid": app["benefit_rule_id"],
            "fs": app["family_status"],
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text("""
                    INSERT INTO policy_family_status_applicability
                    (id, policy_version_id, benefit_rule_id, family_status)
                    VALUES (:id, :vid, :brid, :fs)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return fid

    def insert_policy_source_link(self, link: Dict[str, Any], *, connection: Any = None) -> str:
        lid = link.get("id") or str(uuid.uuid4())
        bind = {
            "id": lid,
            "vid": link["policy_version_id"],
            "ot": link["object_type"],
            "oid": link["object_id"],
            "cid": link["clause_id"],
            "ps": link.get("source_page_start"),
            "pe": link.get("source_page_end"),
            "anchor": link.get("source_anchor"),
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text("""
                    INSERT INTO policy_source_links
                    (id, policy_version_id, object_type, object_id, clause_id, source_page_start, source_page_end, source_anchor)
                    VALUES (:id, :vid, :ot, :oid, :cid, :ps, :pe, :anchor)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return lid

    def list_resolved_policy_benefits(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM resolved_assignment_policy_benefits WHERE resolved_policy_id = :rid ORDER BY benefit_key"),
                {"rid": resolved_policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "evidence_required_json")
            self._parse_json_col(d, "exclusions_json")
            self._parse_json_col(d, "source_rule_ids_json")
        return items

    def list_resolved_policy_exclusions(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM resolved_assignment_policy_exclusions WHERE resolved_policy_id = :rid"),
                {"rid": resolved_policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "source_rule_ids_json")
        return items

    def insert_policy_config_benefit_audit_row(self, row: Dict[str, Any]) -> str:
        """AIQ-839: append one field-level audit entry for a policy_config_benefits change."""
        aid = str(row.get("id") or uuid.uuid4())
        now = datetime.utcnow().isoformat()
        # old/new values are snapshots of policy_config_benefits rows whose
        # numeric columns (amount_value, percentage_value) come back from
        # Postgres as Decimal — not JSON-serializable by default. default=str
        # keeps the audit write from 500ing on any amount-bearing benefit.
        ov = row.get("old_value")
        if isinstance(ov, (dict, list)):
            ov = json.dumps(ov, default=str)
        nv = row.get("new_value")
        if isinstance(nv, (dict, list)):
            nv = json.dumps(nv, default=str)
        params = {
            "id": aid,
            "bid": str(row["benefit_id"]) if row.get("benefit_id") else None,
            "vid": str(row["policy_config_version_id"]) if row.get("policy_config_version_id") else None,
            "bk": row.get("benefit_key"),
            "act": str(row.get("action") or "update"),
            "ov": ov,
            "nv": nv,
            "src": row.get("source"),
            "cb": row.get("changed_by"),
            "ca": now,
        }
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_config_benefits_audit
                    (id, benefit_id, policy_config_version_id, benefit_key, action,
                     old_value, new_value, source, changed_by, changed_at)
                    VALUES
                    (:id, :bid, :vid, :bk, :act, :ov, :nv, :src, :cb, :ca)
"""
                ),
                params,
            )
        return aid

    # AIQ-1070: column/param spec shared by the single-row insert and the
    # batched replace below — keep these in sync with insert_policy_config_benefit_row.
    _PCB_INSERT_SQL = """
                    INSERT INTO policy_config_benefits
                    (id, policy_config_version_id, benefit_key, benefit_label, category, covered,
                     value_type, amount_value, currency_code, percentage_value, unit_frequency,
                     cap_rule_json, notes, conditions_json, assignment_types, family_statuses,
                     employee_levels, targeting_signature, is_active, display_order, source,
                     auto_generated, field_confidence, created_at, updated_at)
                    VALUES
                    (:id, :vid, :bk, :bl, :cat, :cov, :vt, :av, :cc, :pv, :uf, :crj, :notes, :cj,
                     :atj, :fsj, :elj, :tsig, :ia, :do, :src, :ag, :fc, :ca, :ua)
"""
    _PCB_AUDIT_INSERT_SQL = """
                    INSERT INTO policy_config_benefits_audit
                    (id, benefit_id, policy_config_version_id, benefit_key, action,
                     old_value, new_value, source, changed_by, changed_at)
                    VALUES
                    (:id, :bid, :vid, :bk, :act, :ov, :nv, :src, :cb, :ca)
"""

    def _policy_config_benefit_insert_params(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Build the bound-param dict for one policy_config_benefits row.
        Mirrors insert_policy_config_benefit_row exactly (JSON + sqlite-bool
        coercion); used by the batched replace so the two paths agree."""
        from ..database import _is_sqlite
        bid = str(row.get("id") or uuid.uuid4())
        now = datetime.utcnow().isoformat()
        cap_j = row.get("cap_rule_json")
        cap_j = json.dumps(cap_j) if isinstance(cap_j, dict) else ("{}" if cap_j is None else cap_j)
        cond_j = row.get("conditions_json")
        cond_j = json.dumps(cond_j) if isinstance(cond_j, dict) else ("{}" if cond_j is None else cond_j)
        at_j = row.get("assignment_types")
        at_j = json.dumps(at_j) if isinstance(at_j, list) else ("[]" if at_j is None else at_j)
        fs_j = row.get("family_statuses")
        fs_j = json.dumps(fs_j) if isinstance(fs_j, list) else ("[]" if fs_j is None else fs_j)
        el_j = row.get("employee_levels")
        el_j = json.dumps(el_j) if isinstance(el_j, list) else ("[]" if el_j is None else el_j)
        cov = row.get("covered", False)
        iact = row.get("is_active", True)
        ag = row.get("auto_generated", True)
        if _is_sqlite:
            cov = 1 if cov else 0
            iact = 1 if iact else 0
            ag = 1 if ag else 0
        return {
            "id": bid, "vid": str(row["policy_config_version_id"]),
            "bk": str(row["benefit_key"]), "bl": str(row["benefit_label"]),
            "cat": str(row["category"]), "cov": cov,
            "vt": str(row.get("value_type") or "none"), "av": row.get("amount_value"),
            "cc": row.get("currency_code"), "pv": row.get("percentage_value"),
            "uf": str(row.get("unit_frequency") or "one_time"), "crj": cap_j,
            "notes": row.get("notes"), "cj": cond_j, "atj": at_j, "fsj": fs_j, "elj": el_j,
            "tsig": str(row.get("targeting_signature") or "global"), "ia": iact,
            "do": int(row.get("display_order") or 0),
            "src": (str(row["source"]) if row.get("source") else None), "ag": ag,
            "fc": row.get("field_confidence"), "ca": now, "ua": now,
        }

    def _policy_config_benefit_audit_params(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Bound-param dict for one policy_config_benefits_audit row.
        Mirrors insert_policy_config_benefit_audit_row."""
        aid = str(row.get("id") or uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ov = row.get("old_value")
        ov = json.dumps(ov, default=str) if isinstance(ov, (dict, list)) else ov
        nv = row.get("new_value")
        nv = json.dumps(nv, default=str) if isinstance(nv, (dict, list)) else nv
        return {
            "id": aid,
            "bid": str(row["benefit_id"]) if row.get("benefit_id") else None,
            "vid": str(row["policy_config_version_id"]) if row.get("policy_config_version_id") else None,
            "bk": row.get("benefit_key"), "act": str(row.get("action") or "update"),
            "ov": ov, "nv": nv, "src": row.get("source"), "cb": row.get("changed_by"), "ca": now,
        }

    def replace_policy_config_benefits(
        self,
        policy_config_version_id: str,
        rows: List[Dict[str, Any]],
        audit_rows: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """AIQ-1070: atomically replace all benefit rows for a draft version.

        Deletes the version's existing benefit rows and re-inserts ``rows`` (plus
        any ``audit_rows``) using batched multi-row inserts inside a SINGLE
        transaction. Replaces the old delete-then-per-row-insert loop, which made
        hundreds of sequential round-trips (~33s for a full matrix) and could leave
        a partial/empty draft if it failed mid-loop. Each row in ``rows`` must carry
        a pre-generated ``id`` so callers can reference it in ``audit_rows``.
        """
        vid = str(policy_config_version_id)
        benefit_params = [self._policy_config_benefit_insert_params(r) for r in rows]
        audit_params = [self._policy_config_benefit_audit_params(a) for a in (audit_rows or [])]
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM policy_config_benefits WHERE policy_config_version_id = :vid"),
                {"vid": vid},
            )
            if benefit_params:
                conn.execute(text(self._PCB_INSERT_SQL), benefit_params)
            if audit_params:
                conn.execute(text(self._PCB_AUDIT_INSERT_SQL), audit_params)

    def list_jurisdiction_overrides_for_benefit_rows(
        self, benefit_row_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Bulk fetch overrides for a list of benefit rows (one query, grouped
        in Python). Returns dict keyed by benefit_row_id; missing entries
        get an empty list. jurisdiction_countries comes back as either a
        Postgres text[] (already a Python list) or a SQLite JSON-string;
        the resolver handles both shapes.
        """
        if not benefit_row_ids:
            return {}
        ids = [str(b) for b in benefit_row_ids if b]
        if not ids:
            return {}
        # SQLAlchemy parametrizes the IN list as expanding bindparam by
        # building :id_0, :id_1 etc., but we keep this simple and use a
        # tuple param to stay portable across Postgres and SQLite.
        with self.engine.connect() as conn:
            placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
            params = {f"id_{i}": v for i, v in enumerate(ids)}
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, benefit_row_id, jurisdiction_countries,
                           employee_level, assignment_type,
                           amount_value, currency_code, cap_rule_json,
                           reimbursement_md, repayment_md, display_order,
                           created_at, updated_at
                    FROM policy_benefit_jurisdiction_overrides
                    WHERE benefit_row_id IN ({placeholders})
                    ORDER BY display_order ASC, created_at ASC
                    """
                ),
                params,
            ).fetchall()
        out: Dict[str, List[Dict[str, Any]]] = {bid: [] for bid in ids}
        for r in rows:
            m = dict(r._mapping)
            cap = m.get("cap_rule_json")
            if isinstance(cap, str):
                try:
                    m["cap_rule_json"] = json.loads(cap)
                except Exception:
                    m["cap_rule_json"] = {}
            elif cap is None:
                m["cap_rule_json"] = {}
            out.setdefault(str(m["benefit_row_id"]), []).append(m)
        return out

    def replace_jurisdiction_overrides_for_benefit(
        self,
        benefit_row_id: str,
        overrides: List[Dict[str, Any]],
    ) -> None:
        """
        Delete-and-insert all override rows for one benefit. Called from
        put_draft after the benefit row itself has been (re)inserted.
        Cascade delete on policy_config_benefits.id covers the case where
        the benefit row goes away; this method handles the case where the
        benefit stays but its overrides change.

        SQLite caveat: jurisdiction_countries is JSON-encoded TEXT.
        Postgres: native text[]; we let the driver coerce a Python list.
        """
        from ..database import _is_sqlite  # lazy: avoid import cycle
        bid = str(benefit_row_id)
        rows: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()
        for ov in overrides or []:
            countries = list(ov.get("jurisdiction_countries") or [])
            cap = ov.get("cap_rule_json") or {}
            if isinstance(cap, dict):
                cap_serialized: Any = json.dumps(cap)
            else:
                cap_serialized = "{}"
            row_id = str(ov.get("id") or uuid.uuid4())
            rows.append(
                {
                    "id": row_id,
                    "benefit_row_id": bid,
                    "jurisdiction_countries": (
                        json.dumps(countries) if _is_sqlite else countries
                    ),
                    "employee_level": ov.get("employee_level"),
                    "assignment_type": ov.get("assignment_type"),
                    "amount_value": ov.get("amount_value"),
                    "currency_code": ov.get("currency_code"),
                    "cap_rule_json": cap_serialized,
                    "reimbursement_md": ov.get("reimbursement_md"),
                    "repayment_md": ov.get("repayment_md"),
                    "display_order": int(ov.get("display_order") or 0),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM policy_benefit_jurisdiction_overrides "
                    "WHERE benefit_row_id = :bid"
                ),
                {"bid": bid},
            )
            for r in rows:
                conn.execute(
                    text(
                        """
                        INSERT INTO policy_benefit_jurisdiction_overrides
                        (id, benefit_row_id, jurisdiction_countries,
                         employee_level, assignment_type,
                         amount_value, currency_code, cap_rule_json,
                         reimbursement_md, repayment_md, display_order,
                         created_at, updated_at)
                        VALUES
                        (:id, :benefit_row_id, :jurisdiction_countries,
                         :employee_level, :assignment_type,
                         :amount_value, :currency_code, :cap_rule_json,
                         :reimbursement_md, :repayment_md, :display_order,
                         :created_at, :updated_at)
                        """
                    ),
                    r,
                )
