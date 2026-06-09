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
