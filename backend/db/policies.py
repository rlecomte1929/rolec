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

import logging
from typing import Any, Dict, List

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
