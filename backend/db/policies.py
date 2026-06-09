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
from typing import Any, Dict, List, Optional

from sqlalchemy import text

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
