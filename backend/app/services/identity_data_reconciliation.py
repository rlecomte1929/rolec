"""
Audit and conservatively repair historical identity / assignment data.

Designed for dry-run first; safe auto-fixes only when rules in
docs/identity/data-reconciliation-plan.md apply. Ambiguous cases are reported
for manual review — never silent merges of conflicting auth links.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from backend import database as dbmod
from backend.identity_normalize import email_normalized_from_identifier, normalize_invite_key

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class IdentityDataReport:
    """Aggregated audit + planned actions."""

    counts: Dict[str, int] = field(default_factory=dict)
    manual_review: List[Dict[str, Any]] = field(default_factory=list)
    auto_fixes: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "counts": dict(self.counts),
            "manualReviewSamples": list(self.manual_review),
            "autoFixes": list(self.auto_fixes),
            "errors": list(self.errors),
        }


def _fetchall_dicts(conn, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    rows = conn.execute(text(sql), params or {}).fetchall()
    return [dict(r._mapping) for r in rows]


def _group_duplicate_contacts_by_email(rows: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group contacts with same (company_id, normalized non-empty email)."""
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in rows:
        cid = (r.get("company_id") or "").strip()
        raw_en = r.get("email_normalized")
        en = (raw_en or "").strip().lower()
        if not cid or not en:
            continue
        key = (cid, en)
        buckets.setdefault(key, []).append(r)
    return [g for g in buckets.values() if len(g) > 1]


def _pick_canonical_contact(group: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Choose survivor: prefer row with linked_auth_user_id; then oldest created_at.
    Returns (canonical_row or None, reason_for_manual).
    """
    linked_vals = {
        (r.get("linked_auth_user_id") or "").strip()
        for r in group
        if (r.get("linked_auth_user_id") or "").strip()
    }
    if len(linked_vals) > 1:
        return None, "conflicting_linked_auth_user_id"

    with_link = [r for r in group if (r.get("linked_auth_user_id") or "").strip()]
    pool = with_link if with_link else group

    def sort_key(r: Dict[str, Any]) -> Tuple[int, str]:
        ca = (r.get("created_at") or "") or ""
        return (0 if (r.get("linked_auth_user_id") or "").strip() else 1, ca)

    pool_sorted = sorted(pool, key=sort_key)
    return pool_sorted[0], ""


def audit_identity_data(engine) -> IdentityDataReport:
    """Read-only classification. Safe to run in production (uses SELECT only)."""
    report = IdentityDataReport()
    counts: Dict[str, int] = {k: 0 for k in (
        "duplicate_contact_groups",
        "duplicate_contact_rows_extra",
        "duplicate_contact_manual_conflict",
        "assignment_missing_employee_contact_id",
        "assignment_orphan_employee_contact_id",
        "assignment_contact_company_mismatch",
        "contact_linkable_to_user",
        "contact_linked_auth_user_missing",
        "claim_invite_pending_but_assignment_assigned",
        "claim_invite_claimed_user_mismatch",
        "claim_invite_multiple_pending_per_assignment",
        "legacy_invite_active_but_assigned",
        "employee_user_id_orphan",
        "suspicious_employee_user_no_password",
    )}
    join_on = dbmod._relocation_cases_join_on("a", "standard")

    try:
        with engine.connect() as conn:
            # --- Duplicate employee_contacts (same company + normalized email) ---
            rows = _fetchall_dicts(
                conn,
                "SELECT id, company_id, invite_key, email_normalized, linked_auth_user_id, created_at "
                "FROM employee_contacts",
            )
            groups = _group_duplicate_contacts_by_email(rows)
            counts["duplicate_contact_groups"] = len(groups)
            for g in groups:
                canon, manual_reason = _pick_canonical_contact(g)
                if manual_reason:
                    counts["duplicate_contact_manual_conflict"] += 1
                    report.manual_review.append(
                        {
                            "type": "duplicate_employee_contacts",
                            "reason": manual_reason,
                            "company_id": g[0].get("company_id"),
                            "email_normalized": (g[0].get("email_normalized") or "").strip().lower(),
                            "contact_ids": [x.get("id") for x in g],
                        }
                    )
                    continue
                assert canon is not None
                losers = [x for x in g if x.get("id") != canon.get("id")]
                counts["duplicate_contact_rows_extra"] += len(losers)
                invite_keys = sorted({(x.get("invite_key") or "") for x in g})
                report.auto_fixes.append(
                    {
                        "action": "merge_duplicate_employee_contacts",
                        "canonical_contact_id": canon.get("id"),
                        "merge_from_contact_ids": [x.get("id") for x in losers],
                        "invite_keys": invite_keys,
                    }
                )

            # --- Assignments: missing employee_contact_id ---
            missing = _fetchall_dicts(
                conn,
                "SELECT id, case_id, employee_identifier FROM case_assignments "
                "WHERE (employee_contact_id IS NULL OR TRIM(COALESCE(employee_contact_id, '')) = '') "
                "AND employee_identifier IS NOT NULL AND TRIM(employee_identifier) != ''",
            )
            counts["assignment_missing_employee_contact_id"] = len(missing)
            for m in missing[:200]:
                report.auto_fixes.append(
                    {
                        "action": "backfill_employee_contact_id",
                        "assignment_id": m.get("id"),
                        "case_id": m.get("case_id"),
                        "employee_identifier": m.get("employee_identifier"),
                    }
                )
            if len(missing) > 200:
                report.manual_review.append(
                    {
                        "type": "assignment_missing_contact_truncated",
                        "note": f"{len(missing)} rows; only first 200 queued for auto backfill listing",
                    }
                )

            # --- Orphan employee_contact_id on assignment ---
            orphan_asg = _fetchall_dicts(
                conn,
                "SELECT a.id AS assignment_id, a.employee_contact_id "
                "FROM case_assignments a "
                "LEFT JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                "WHERE a.employee_contact_id IS NOT NULL AND TRIM(COALESCE(a.employee_contact_id, '')) != '' "
                "AND ec.id IS NULL",
            )
            counts["assignment_orphan_employee_contact_id"] = len(orphan_asg)
            for o in orphan_asg[:100]:
                report.manual_review.append(
                    {
                        "type": "assignment_orphan_employee_contact",
                        "assignment_id": o.get("assignment_id"),
                        "employee_contact_id": o.get("employee_contact_id"),
                    }
                )

            # --- Contact company vs case company ---
            mismatch_sql = (
                "SELECT a.id AS assignment_id, a.employee_contact_id, "
                "ec.company_id AS contact_company_id, rc.company_id AS case_company_id "
                "FROM case_assignments a "
                "INNER JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                f"LEFT JOIN relocation_cases rc ON {join_on} "
                "WHERE ec.company_id IS NOT NULL AND TRIM(COALESCE(ec.company_id, '')) != '' "
                "AND rc.company_id IS NOT NULL AND TRIM(COALESCE(rc.company_id, '')) != '' "
                "AND CAST(ec.company_id AS TEXT) != CAST(rc.company_id AS TEXT)"
            )
            try:
                mism = _fetchall_dicts(conn, mismatch_sql)
            except Exception as exc:
                mism = []
                report.errors.append(f"assignment_contact_company_mismatch query: {exc}")
            counts["assignment_contact_company_mismatch"] = len(mism)
            for row in mism[:100]:
                report.manual_review.append({"type": "assignment_contact_company_mismatch", **row})

            # --- Contacts that can link to existing auth user (single match) ---
            linkable = _fetchall_dicts(
                conn,
                "SELECT ec.id AS contact_id, ec.company_id, ec.email_normalized, u.id AS user_id "
                "FROM employee_contacts ec "
                "INNER JOIN users u ON LOWER(TRIM(COALESCE(u.email, ''))) = LOWER(TRIM(COALESCE(ec.email_normalized, ''))) "
                "WHERE ec.email_normalized IS NOT NULL AND TRIM(ec.email_normalized) != '' "
                "AND (ec.linked_auth_user_id IS NULL OR TRIM(COALESCE(ec.linked_auth_user_id, '')) = '') "
                "AND u.email IS NOT NULL AND TRIM(u.email) != ''",
            )
            counts["contact_linkable_to_user"] = len(linkable)
            for row in linkable:
                report.auto_fixes.append(
                    {
                        "action": "link_employee_contact_to_auth_user",
                        "contact_id": row.get("contact_id"),
                        "user_id": row.get("user_id"),
                        "email_normalized": row.get("email_normalized"),
                    }
                )

            # --- linked_auth_user_id points to missing users row ---
            orphan_link = _fetchall_dicts(
                conn,
                "SELECT ec.id AS contact_id, ec.linked_auth_user_id "
                "FROM employee_contacts ec "
                "LEFT JOIN users u ON u.id = ec.linked_auth_user_id "
                "WHERE ec.linked_auth_user_id IS NOT NULL AND TRIM(COALESCE(ec.linked_auth_user_id, '')) != '' "
                "AND u.id IS NULL",
            )
            counts["contact_linked_auth_user_missing"] = len(orphan_link)
            for row in orphan_link[:100]:
                report.manual_review.append({"type": "contact_linked_auth_user_missing", **row})

            # --- Claim invite pending but assignment already has employee ---
            pending_assigned = _fetchall_dicts(
                conn,
                "SELECT aci.id AS invite_id, aci.assignment_id, a.employee_user_id "
                "FROM assignment_claim_invites aci "
                "INNER JOIN case_assignments a ON a.id = aci.assignment_id "
                "WHERE LOWER(TRIM(aci.status)) = 'pending' "
                "AND a.employee_user_id IS NOT NULL AND TRIM(COALESCE(a.employee_user_id, '')) != ''",
            )
            counts["claim_invite_pending_but_assignment_assigned"] = len(pending_assigned)
            for row in pending_assigned:
                report.auto_fixes.append(
                    {
                        "action": "sync_claim_invite_to_assigned_employee",
                        "invite_id": row.get("invite_id"),
                        "assignment_id": row.get("assignment_id"),
                        "employee_user_id": row.get("employee_user_id"),
                    }
                )

            # --- Claimed invite user != assignment employee ---
            claimed_mismatch = _fetchall_dicts(
                conn,
                "SELECT aci.id AS invite_id, aci.assignment_id, aci.claimed_by_user_id, a.employee_user_id "
                "FROM assignment_claim_invites aci "
                "INNER JOIN case_assignments a ON a.id = aci.assignment_id "
                "WHERE LOWER(TRIM(aci.status)) = 'claimed' "
                "AND aci.claimed_by_user_id IS NOT NULL AND TRIM(COALESCE(aci.claimed_by_user_id, '')) != '' "
                "AND a.employee_user_id IS NOT NULL AND TRIM(COALESCE(a.employee_user_id, '')) != '' "
                "AND CAST(aci.claimed_by_user_id AS TEXT) != CAST(a.employee_user_id AS TEXT)",
            )
            counts["claim_invite_claimed_user_mismatch"] = len(claimed_mismatch)
            for row in claimed_mismatch[:100]:
                report.manual_review.append({"type": "claim_invite_claimed_user_mismatch", **row})

            # --- Multiple pending claim invites per assignment ---
            multi_pend = _fetchall_dicts(
                conn,
                "SELECT assignment_id, COUNT(*) AS n FROM assignment_claim_invites "
                "WHERE LOWER(TRIM(status)) = 'pending' "
                "GROUP BY assignment_id HAVING COUNT(*) > 1",
            )
            counts["claim_invite_multiple_pending_per_assignment"] = len(multi_pend)
            for row in multi_pend[:100]:
                report.manual_review.append(
                    {"type": "claim_invite_multiple_pending", "assignment_id": row.get("assignment_id"), "count": row.get("n")}
                )

            # --- Legacy assignment_invites still ACTIVE but assignment claimed ---
            try:
                legacy = _fetchall_dicts(
                    conn,
                    "SELECT ai.id AS invite_id, ai.case_id, ai.employee_identifier "
                    "FROM assignment_invites ai "
                    "WHERE UPPER(TRIM(COALESCE(ai.status, ''))) = 'ACTIVE' "
                    "AND EXISTS ("
                    "  SELECT 1 FROM case_assignments a "
                    "  WHERE a.case_id = ai.case_id "
                    "  AND LOWER(TRIM(COALESCE(a.employee_identifier, ''))) = LOWER(TRIM(COALESCE(ai.employee_identifier, ''))) "
                    "  AND a.employee_user_id IS NOT NULL AND TRIM(COALESCE(a.employee_user_id, '')) != ''"
                    ")",
                )
            except Exception as exc:
                legacy = []
                report.errors.append(f"legacy_invite_active query: {exc}")
            counts["legacy_invite_active_but_assigned"] = len(legacy)
            for row in legacy:
                report.auto_fixes.append(
                    {
                        "action": "mark_legacy_invite_claimed",
                        "invite_id": row.get("invite_id"),
                        "case_id": row.get("case_id"),
                        "employee_identifier": row.get("employee_identifier"),
                    }
                )

            # --- employee_user_id on assignment points to missing user ---
            orphan_emp = _fetchall_dicts(
                conn,
                "SELECT a.id AS assignment_id, a.employee_user_id "
                "FROM case_assignments a "
                "LEFT JOIN users u ON u.id = a.employee_user_id "
                "WHERE a.employee_user_id IS NOT NULL AND TRIM(COALESCE(a.employee_user_id, '')) != '' "
                "AND u.id IS NULL",
            )
            counts["employee_user_id_orphan"] = len(orphan_emp)
            for row in orphan_emp[:100]:
                report.manual_review.append({"type": "employee_user_id_orphan", **row})

            # --- Heuristic: EMPLOYEE users with no password (possible abandoned pre-auth row) ---
            try:
                no_pwd = _fetchall_dicts(
                    conn,
                    "SELECT id, email, username, role FROM users "
                    "WHERE UPPER(TRIM(COALESCE(role, ''))) IN ('EMPLOYEE', 'EMPLOYEE_USER') "
                    "AND (password_hash IS NULL OR TRIM(COALESCE(password_hash, '')) = '')",
                )
            except Exception as exc:
                no_pwd = []
                report.errors.append(f"suspicious_employee_user_no_password query: {exc}")
            counts["suspicious_employee_user_no_password"] = len(no_pwd)
            for row in no_pwd[:50]:
                report.manual_review.append({"type": "suspicious_employee_user_no_password", **row})

    except Exception as exc:
        report.errors.append(f"audit_identity_data: {exc}")
        log.exception("identity data audit failed")

    report.counts = counts
    return report


_FIX_ORDER = {
    "merge_duplicate_employee_contacts": 0,
    "backfill_employee_contact_id": 1,
    "link_employee_contact_to_auth_user": 2,
    "sync_claim_invite_to_assigned_employee": 3,
    "mark_legacy_invite_claimed": 4,
}


def _sort_fixes(fix_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(fix_list, key=lambda x: _FIX_ORDER.get(str(x.get("action") or ""), 99))


def _execute_identity_fixes(conn: Any, fix_list: List[Dict[str, Any]], applied: Dict[str, int]) -> None:
    """Run all auto-fixes on an open connection (same transaction)."""
    for fix in _sort_fixes(fix_list):
        action = fix.get("action")
        if action == "merge_duplicate_employee_contacts":
            canon = (fix.get("canonical_contact_id") or "").strip()
            losers = fix.get("merge_from_contact_ids") or []
            if not canon or not losers:
                continue
            now = _now_iso()
            for lid in losers:
                lid = (lid or "").strip()
                if not lid or lid == canon:
                    continue
                conn.execute(
                    text(
                        "UPDATE case_assignments SET employee_contact_id = :c, updated_at = :ua "
                        "WHERE employee_contact_id = :l"
                    ),
                    {"c": canon, "l": lid, "ua": now},
                )
                conn.execute(
                    text(
                        "UPDATE assignment_claim_invites SET employee_contact_id = :c "
                        "WHERE employee_contact_id = :l"
                    ),
                    {"c": canon, "l": lid},
                )
                conn.execute(text("DELETE FROM employee_contacts WHERE id = :l"), {"l": lid})
            applied["merge_duplicate_employee_contacts"] += 1

        elif action == "backfill_employee_contact_id":
            aid = (fix.get("assignment_id") or "").strip()
            ident = fix.get("employee_identifier") or ""
            if not aid:
                continue
            now = _now_iso()
            join_on = dbmod._relocation_cases_join_on("a", "standard")
            rc_row = conn.execute(
                text(
                    f"SELECT rc.company_id AS company_id FROM case_assignments a "
                    f"LEFT JOIN relocation_cases rc ON {join_on} "
                    f"WHERE a.id = :aid LIMIT 1"
                ),
                {"aid": aid},
            ).fetchone()
            if not rc_row:
                continue
            company_id = (dict(rc_row._mapping).get("company_id") or "").strip()
            if not company_id:
                continue
            ik = normalize_invite_key(str(ident))
            if not ik:
                continue
            en = email_normalized_from_identifier(str(ident))
            canonical_ik = en if en else ik
            ec_row = None
            if en:
                ec_row = conn.execute(
                    text(
                        "SELECT id FROM employee_contacts WHERE company_id = :c AND email_normalized = :en LIMIT 1"
                    ),
                    {"c": company_id, "en": en},
                ).fetchone()
            if not ec_row:
                ec_row = conn.execute(
                    text(
                        "SELECT id FROM employee_contacts WHERE company_id = :c AND invite_key = :ik LIMIT 1"
                    ),
                    {"c": company_id, "ik": canonical_ik},
                ).fetchone()
            if not ec_row:
                ec_row = conn.execute(
                    text(
                        "SELECT id FROM employee_contacts WHERE company_id = :c AND invite_key = :ik2 LIMIT 1"
                    ),
                    {"c": company_id, "ik2": ik},
                ).fetchone()
            if not ec_row:
                eid = str(uuid.uuid4())
                conn.execute(
                    text(
                        "INSERT INTO employee_contacts "
                        "(id, company_id, invite_key, email_normalized, first_name, last_name, "
                        "linked_auth_user_id, created_at, updated_at) "
                        "VALUES (:id, :c, :ik, :en, NULL, NULL, NULL, :ca, :ua)"
                    ),
                    {
                        "id": eid,
                        "c": company_id,
                        "ik": canonical_ik,
                        "en": en,
                        "ca": now,
                        "ua": now,
                    },
                )
                ecid = eid
            else:
                ecid = str(dict(ec_row._mapping)["id"])
            res = conn.execute(
                text(
                    "UPDATE case_assignments SET employee_contact_id = :ec, updated_at = :ua "
                    "WHERE id = :aid AND (employee_contact_id IS NULL OR TRIM(COALESCE(employee_contact_id,'')) = '')"
                ),
                {"ec": ecid, "ua": _now_iso(), "aid": aid},
            )
            if res.rowcount and res.rowcount > 0:
                applied["backfill_employee_contact_id"] += 1

        elif action == "link_employee_contact_to_auth_user":
            cid = (fix.get("contact_id") or "").strip()
            uid = (fix.get("user_id") or "").strip()
            if not cid or not uid:
                continue
            res = conn.execute(
                text(
                    "UPDATE employee_contacts SET linked_auth_user_id = :uid, updated_at = :ua "
                    "WHERE id = :ecid AND (linked_auth_user_id IS NULL OR linked_auth_user_id = :uid)"
                ),
                {"uid": uid, "ua": _now_iso(), "ecid": cid},
            )
            if res.rowcount and res.rowcount > 0:
                applied["link_employee_contact_to_auth_user"] += 1

        elif action == "sync_claim_invite_to_assigned_employee":
            iid = (fix.get("invite_id") or "").strip()
            uid = (fix.get("employee_user_id") or "").strip()
            if not iid or not uid:
                continue
            res = conn.execute(
                text(
                    "UPDATE assignment_claim_invites "
                    "SET status = 'claimed', claimed_by_user_id = :uid, claimed_at = :ca "
                    "WHERE id = :iid AND LOWER(TRIM(status)) = 'pending'"
                ),
                {"uid": uid, "ca": _now_iso(), "iid": iid},
            )
            if res.rowcount and res.rowcount > 0:
                applied["sync_claim_invite_to_assigned_employee"] += 1

        elif action == "mark_legacy_invite_claimed":
            iid = (fix.get("invite_id") or "").strip()
            if not iid:
                continue
            conn.execute(
                text(
                    "UPDATE assignment_invites SET status = 'CLAIMED' "
                    "WHERE id = :iid AND UPPER(TRIM(status)) = 'ACTIVE'"
                ),
                {"iid": iid},
            )
            applied["mark_legacy_invite_claimed"] += 1


def apply_safe_fixes(engine, report: IdentityDataReport, *, dry_run: bool = True) -> Dict[str, int]:
    """
    Execute only auto_fixes from a prior audit. Returns counters of applied (or simulated) actions.
    When dry_run=True, runs the same statements then rolls back the transaction.
    """
    applied = {
        "merge_duplicate_employee_contacts": 0,
        "backfill_employee_contact_id": 0,
        "link_employee_contact_to_auth_user": 0,
        "sync_claim_invite_to_assigned_employee": 0,
        "mark_legacy_invite_claimed": 0,
    }
    fix_list = list(report.auto_fixes)
    if not fix_list:
        return applied

    if dry_run:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                _execute_identity_fixes(conn, fix_list, applied)
            finally:
                trans.rollback()
        return applied

    with engine.begin() as conn:
        _execute_identity_fixes(conn, fix_list, applied)
    return applied
