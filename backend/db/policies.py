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
