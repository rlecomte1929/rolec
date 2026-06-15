"""
Compensation & Allowance — structured policy matrix (policy_configs / versions / benefits).

Architecture (brief):
- Document pipeline policies (company_policies / policy_versions) stay separate; this matrix is
  manual-entry first, with rows later hydratable from extracted HR policy text.
- Draft versions are editable; publish archives the prior published row and freezes the draft row.
  Row shape is validated on PUT draft (Pydantic); publish enforces effective_date and version match only.
- targeting_signature hashes normalized assignment_types + family_statuses so DB uniqueness holds
  per (version, benefit_key, targeting).
- Service modules can map benefit_key sets to caps via policy_config_caps (API) without joining here.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...database import Database
from ...schemas_compensation_allowance import (
    PolicyConfigBenefitWrite,
    PolicyConfigCategory,
)
from .policy_config_targeting import (
    normalize_assignment_type,
    normalize_family_status,
    row_matches_targeting,
)

log = logging.getLogger(__name__)

CONFIG_KEY = "compensation_allowance"

# Downstream service-module hints (extend as product adds modules).
SERVICE_MODULE_BENEFIT_KEYS: Dict[str, List[str]] = {
    "immigration": ["visa_work_permit_assistance", "medical_exam_reimbursement"],
    "relocation": [
        "relocation_allowance_assignee_partner",
        "relocation_allowance_dependent",
        "removal_expenses",
        "shipment_of_goods",
        "storage",
        "temporary_living",
        "settling_in_services",
    ],
    "compensation": [
        "mobility_premium",
        "location_allowance",
        "living_allowance",
        "cola",
        "host_housing_cap",
        "host_transportation",
    ],
    "family": ["spouse_partner_assistance", "child_education_support", "dual_career_support"],
    "repatriation": [
        "home_leave_trips",
        "extra_holiday_days",
        "repatriation_allowance_assignee_partner",
        "repatriation_allowance_dependent",
        "return_shipment_travel",
    ],
    "tax_payroll": [
        "tax_equalisation",
        "payroll_structure",
        "banking_assistance",
        "tax_return_preparation",
    ],
}

CATEGORY_LABELS: Dict[str, str] = {
    "pre_assignment_support": "Pre-assignment support",
    "relocation_assistance": "Relocation assistance",
    "compensation_allowances": "Compensation & allowances",
    "family_support_education": "Family support & education",
    "leave_repatriation": "Leave & repatriation",
    "tax_payroll": "Tax & payroll",
}

_CANONICAL_KEYS: List[Tuple[str, str, PolicyConfigCategory]] = [
    ("visa_work_permit_assistance", "Visa / work permit assistance", PolicyConfigCategory.pre_assignment_support),
    ("medical_exam_reimbursement", "Medical exam reimbursement", PolicyConfigCategory.pre_assignment_support),
    ("pre_assignment_visit", "Pre-assignment visit", PolicyConfigCategory.pre_assignment_support),
    ("cultural_training", "Cultural training", PolicyConfigCategory.pre_assignment_support),
    ("language_training", "Language training", PolicyConfigCategory.pre_assignment_support),
    ("relocation_allowance_assignee_partner", "Relocation allowance (assignee / partner)", PolicyConfigCategory.relocation_assistance),
    ("relocation_allowance_dependent", "Relocation allowance (dependent)", PolicyConfigCategory.relocation_assistance),
    ("removal_expenses", "Removal expenses", PolicyConfigCategory.relocation_assistance),
    ("shipment_of_goods", "Shipment of goods", PolicyConfigCategory.relocation_assistance),
    ("storage", "Storage", PolicyConfigCategory.relocation_assistance),
    ("temporary_living", "Temporary living", PolicyConfigCategory.relocation_assistance),
    ("settling_in_services", "Settling-in services", PolicyConfigCategory.relocation_assistance),
    ("mobility_premium", "Mobility premium", PolicyConfigCategory.compensation_allowances),
    ("location_allowance", "Location allowance", PolicyConfigCategory.compensation_allowances),
    ("living_allowance", "Living allowance", PolicyConfigCategory.compensation_allowances),
    ("cola", "COLA", PolicyConfigCategory.compensation_allowances),
    ("host_housing_cap", "Host housing cap", PolicyConfigCategory.compensation_allowances),
    ("host_transportation", "Host transportation", PolicyConfigCategory.compensation_allowances),
    ("driving_test_reimbursement", "Driving test reimbursement", PolicyConfigCategory.compensation_allowances),
    ("dual_career_support", "Dual career support", PolicyConfigCategory.compensation_allowances),
    ("spouse_partner_assistance", "Spouse / partner assistance", PolicyConfigCategory.family_support_education),
    ("child_education_support", "Child education support", PolicyConfigCategory.family_support_education),
    ("home_leave_trips", "Home leave trips", PolicyConfigCategory.leave_repatriation),
    ("extra_holiday_days", "Extra holiday days", PolicyConfigCategory.leave_repatriation),
    ("repatriation_allowance_assignee_partner", "Repatriation allowance (assignee / partner)", PolicyConfigCategory.leave_repatriation),
    ("repatriation_allowance_dependent", "Repatriation allowance (dependent)", PolicyConfigCategory.leave_repatriation),
    ("return_shipment_travel", "Return shipment / travel", PolicyConfigCategory.leave_repatriation),
    ("tax_equalisation", "Tax equalisation", PolicyConfigCategory.tax_payroll),
    ("payroll_structure", "Payroll structure", PolicyConfigCategory.tax_payroll),
    ("banking_assistance", "Banking assistance", PolicyConfigCategory.tax_payroll),
    ("tax_return_preparation", "Tax return preparation", PolicyConfigCategory.tax_payroll),
]


_AUDIT_VALUE_KEYS = (
    "covered",
    "value_type",
    "amount_value",
    "currency_code",
    "percentage_value",
    "unit_frequency",
    "cap_rule_json",
    "notes",
)


def _benefit_audit_value(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Curated value snapshot of a benefit row for the audit trail (old/new_value)."""
    if not row:
        return None
    return {k: row.get(k) for k in _AUDIT_VALUE_KEYS}


def compute_targeting_signature(
    assignment_types: Sequence[str],
    family_statuses: Sequence[str],
    employee_levels: Optional[Sequence[str]] = None,
) -> str:
    """
    Hash the normalized targeting triple. ``employee_levels`` is optional for
    back-compat: existing rows hashed on 2 axes preserve their "global" or
    2-axis signature, so the uniqueness constraint
    (policy_config_version_id, benefit_key, targeting_signature) keeps working.
    When a caller passes an empty or None sequence, the new axis is omitted
    from the payload exactly like empty assignment_types / family_statuses.
    """
    a = sorted({str(x).strip() for x in assignment_types if str(x).strip()})
    f = sorted({str(x).strip() for x in family_statuses if str(x).strip()})
    e = sorted({str(x).strip() for x in (employee_levels or []) if str(x).strip()})
    if not a and not f and not e:
        return "global"
    payload_obj: Dict[str, List[str]] = {"assignment_types": a, "family_statuses": f}
    if e:
        payload_obj["employee_levels"] = e
    payload = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso_date(d: Any) -> str:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, datetime):
        return d.date().isoformat()
    if d is None:
        return date.today().isoformat()
    s = str(d).strip()
    return s[:10] if s else date.today().isoformat()


def _benefit_row_defaults(benefit_key: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "covered": False,
        "value_type": "none",
        "amount_value": None,
        "currency_code": None,
        "percentage_value": None,
        "unit_frequency": "one_time",
        "cap_rule_json": {},
        "notes": None,
        "conditions_json": {},
        "assignment_types": [],
        "family_statuses": [],
        "employee_levels": [],
        "is_active": True,
    }
    if benefit_key in ("relocation_allowance_assignee_partner", "repatriation_allowance_assignee_partner"):
        base.update(
            {
                "covered": True,
                "value_type": "currency",
                "amount_value": 5000.0,
                "currency_code": "EUR",
                "unit_frequency": "one_time",
            }
        )
    elif benefit_key in ("relocation_allowance_dependent", "repatriation_allowance_dependent"):
        base.update(
            {
                "covered": True,
                "value_type": "currency",
                "amount_value": 1000.0,
                "currency_code": "EUR",
                "unit_frequency": "one_time",
            }
        )
        base["cap_rule_json"] = {"per": "dependent"}
    elif benefit_key == "spouse_partner_assistance":
        base.update(
            {
                "covered": True,
                "value_type": "currency",
                "amount_value": 5000.0,
                "currency_code": "EUR",
                "unit_frequency": "custom",
                "cap_rule_json": {"cap_amount": 5000.0, "currency": "EUR", "basis": "total_assistance_cap"},
            }
        )
    return base


def _canonical_seed_rows(version_id: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    order = 0
    for bk, label, cat in _CANONICAL_KEYS:
        order += 10
        d = _benefit_row_defaults(bk)
        if bk in ("relocation_allowance_dependent", "repatriation_allowance_dependent"):
            d["unit_frequency"] = "per_dependent"
        sig = compute_targeting_signature(
            d["assignment_types"], d["family_statuses"], d.get("employee_levels") or []
        )
        rows.append(
            {
                "policy_config_version_id": version_id,
                "benefit_key": bk,
                "benefit_label": label,
                "category": cat.value,
                "targeting_signature": sig,
                "display_order": order,
                **d,
                # AIQ-854: scaffold rows for a fresh draft with no published baseline.
                "source": "seeded",
                "auto_generated": True,
            }
        )
    return rows


# AIQ-873: extraction (policy_benefits) → config-matrix (policy_config_benefits)
# benefit-key bridge. The two subsystems use different vocabularies (~13 extraction
# keys vs the 28 canonical matrix keys) with almost no overlap, so a translation
# layer is mandatory. Only unambiguous 1:1 mappings are listed; the deliberately
# OMITTED extraction keys (rental_deposit, travel_host, tax_assistance, repatriation,
# home_sale_purchase) have no single clean matrix target and are reported as
# "unmapped" for HR manual entry rather than guessed. Extend as vocabularies converge.
EXTRACTION_TO_MATRIX_BENEFIT_KEY: Dict[str, str] = {
    "temporary_housing": "temporary_living",
    "shipment": "shipment_of_goods",
    "visa_support": "visa_work_permit_assistance",
    "settling_in_allowance": "settling_in_services",
    "spousal_support": "spouse_partner_assistance",
    "language_training": "language_training",
    "education_support": "child_education_support",
    "scouting_trip": "pre_assignment_visit",
}

# matrix benefit_key -> (label, category string) from the canonical registry.
_MATRIX_KEY_META: Dict[str, Tuple[str, str]] = {
    bk: (label, cat.value) for bk, label, cat in _CANONICAL_KEYS
}


def resolve_extraction_company_id(db: Any, policy_id: str) -> Optional[str]:
    """Resolve the owning company_id for an extraction-lineage id.

    E1b (AIQ-929): ``policy_documents`` is the canonical extraction lineage, so try
    the document table first; fall back to the legacy ``company_policies`` lineage
    so the older ``POST /api/policies/{id}/extract`` path keeps working. The two
    tables share no ids in practice (independent uuid PKs), so the order is a
    preference, not a correctness constraint. Returns None when the id matches
    neither table (caller raises 404 / KeyError).
    """
    try:
        doc = db.get_policy_document(policy_id)
    except Exception:  # noqa: BLE001 — fall through to the legacy lineage
        doc = None
    if doc and doc.get("company_id"):
        return str(doc["company_id"])
    pol = db.get_company_policy(policy_id)
    if pol and pol.get("company_id"):
        return str(pol["company_id"])
    return None


def _normalize_cap_rule(cap: Any) -> Dict[str, Any]:
    if isinstance(cap, dict):
        return cap
    if isinstance(cap, str) and cap.strip():
        try:
            return json.loads(cap)
        except Exception:
            return {}
    return {}


def _serialize_overrides(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Section C: shape an override DB row for the API. Drops bookkeeping
    columns the UI doesn't need and normalizes jurisdiction_countries
    from either Postgres text[] or the SQLite JSON-string mirror into a
    plain Python list. Order is whatever the bulk-fetch returned (already
    sorted by display_order, created_at).
    """
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        raw_countries = r.get("jurisdiction_countries")
        if isinstance(raw_countries, list):
            countries = [str(c) for c in raw_countries]
        elif isinstance(raw_countries, str):
            s = raw_countries.strip()
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    countries = [str(c) for c in parsed] if isinstance(parsed, list) else []
                except Exception:
                    countries = []
            elif s.startswith("{") and s.endswith("}"):
                countries = [c.strip() for c in s[1:-1].split(",") if c.strip()]
            elif s:
                countries = [s]
            else:
                countries = []
        else:
            countries = []
        cap = r.get("cap_rule_json")
        if isinstance(cap, str):
            try:
                cap = json.loads(cap)
            except Exception:
                cap = {}
        elif cap is None:
            cap = {}
        out.append(
            {
                "id": str(r.get("id")) if r.get("id") is not None else None,
                "jurisdiction_countries": countries,
                "employee_level": r.get("employee_level"),
                "assignment_type": r.get("assignment_type"),
                "amount_value": r.get("amount_value"),
                "currency_code": r.get("currency_code"),
                "cap_rule_json": cap,
                "reimbursement_md": r.get("reimbursement_md"),
                "repayment_md": r.get("repayment_md"),
                "display_order": int(r.get("display_order") or 0),
            }
        )
    return out


def allowance_cap_from_row(b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalized cap object for UI / comparison engines."""
    cr = _normalize_cap_rule(b.get("cap_rule_json"))
    out: Dict[str, Any] = {}
    if b.get("value_type") == "currency" and b.get("amount_value") is not None:
        out["amount"] = float(b["amount_value"])
        out["currency"] = (b.get("currency_code") or "EUR").upper()
        out["unit_frequency"] = b.get("unit_frequency")
    if cr.get("cap_amount") is not None:
        out["cap_amount"] = float(cr["cap_amount"])
        out["cap_currency"] = (cr.get("currency") or out.get("currency") or "EUR").upper()
    if cr.get("per"):
        out["per"] = cr["per"]
    return out or None


def maximum_budget_explanation(b: Dict[str, Any]) -> str:
    vt = b.get("value_type")
    freq = str(b.get("unit_frequency") or "one_time").replace("_", " ")
    cap = _normalize_cap_rule(b.get("cap_rule_json"))
    if vt == "currency" and b.get("amount_value") is not None:
        cur = b.get("currency_code") or "EUR"
        parts = [
            f"Policy allowance up to {b['amount_value']} {cur} ({freq}).",
        ]
        if cap.get("cap_amount") is not None:
            parts.append(
                f"Company maximum budget cap: {cap['cap_amount']} {cap.get('currency') or cur}."
            )
        elif cap.get("basis") == "total_assistance_cap":
            parts.append("Maximum budget is defined as a total assistance cap (see amount).")
        return " ".join(parts)
    if vt == "percentage" and b.get("percentage_value") is not None:
        return f"Percentage-based benefit: {b['percentage_value']}% ({freq})."
    if vt == "text":
        return "Allowance is described in text; refer to notes and conditions."
    if b.get("covered"):
        return "Listed as covered; monetary cap not specified in structured fields — see notes."
    return "Not covered under this policy configuration."


def _extraction_draft_note(b: Dict[str, Any]) -> str:
    """Build the draft `notes` for an imported extracted benefit (AIQ-938-FU).

    Combines the extracted free-text eligibility/limits with the extraction
    citation (``source_quote``). policy_config_benefits has no dedicated
    citation column, so the source quote rides in notes as a ``Source: "…"``
    line — that is what lets the HR review UI show *what text* the value came
    from alongside the confidence + N11 low-confidence marker.
    """
    parts = [
        str(s).strip()
        for s in (b.get("eligibility"), b.get("limits"))
        if s and str(s).strip()
    ]
    quote = str(b.get("source_quote") or "").strip()
    if quote:
        if len(quote) > 300:
            quote = quote[:297].rstrip() + "…"
        parts.append(f'Source: "{quote}"')
    return " — ".join(parts).strip()


class PolicyConfigMatrixService:
    def __init__(self, database: Database) -> None:
        self._db = database

    def _filter_benefits_matrix_query(
        self,
        benefits: List[Dict[str, Any]],
        *,
        assignment_type: Optional[str],
        family_status: Optional[str],
        effective_rows_only: bool,
        strict_context: bool,
        employee_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        targeting = (
            assignment_type is not None
            or family_status is not None
            or employee_level is not None
        )
        if not targeting and not effective_rows_only:
            return benefits
        out: List[Dict[str, Any]] = []
        for b in benefits:
            if effective_rows_only:
                if not b.get("is_active", True) or not b.get("covered"):
                    continue
            if targeting:
                if not row_matches_targeting(
                    b,
                    assignment_type,
                    family_status,
                    strict_context=strict_context,
                    employee_level=employee_level,
                ):
                    continue
            out.append(b)
        return out

    def _config(self, company_id: str) -> Dict[str, Any]:
        return self._db.ensure_policy_config(str(company_id), CONFIG_KEY)

    def _collect_supported_lists(
        self, benefits: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], List[str]]:
        at_set: set = set()
        fs_set: set = set()
        el_set: set = set()
        for b in benefits:
            for x in b.get("assignment_types") or []:
                if str(x).strip():
                    at_set.add(str(x).strip())
            for x in b.get("family_statuses") or []:
                if str(x).strip():
                    fs_set.add(str(x).strip())
            for x in b.get("employee_levels") or []:
                if str(x).strip():
                    el_set.add(str(x).strip())
        return sorted(at_set), sorted(fs_set), sorted(el_set)

    def _version_to_metadata(
        self,
        v: Optional[Dict[str, Any]],
        benefits: List[Dict[str, Any]],
        *,
        editable: bool,
        source: str,
    ) -> Dict[str, Any]:
        if not v:
            today = date.today().isoformat()
            at, fs, el = self._collect_supported_lists(benefits)
            return {
                "policy_version": None,
                "version_number": None,
                "effective_date": today,
                "status": "empty_scaffold",
                "editable": editable,
                "source": source,
                "assignment_types_supported": at,
                "family_statuses_supported": fs,
                "employee_levels_supported": el,
            }
        at, fs, el = self._collect_supported_lists(benefits)
        st = str(v.get("status") or "")
        raw_id = v.get("id")
        pv = str(raw_id) if raw_id not in (None, "") else None
        return {
            "policy_version": pv,
            "version_number": int(v.get("version_number") or 0),
            "effective_date": _iso_date(v.get("effective_date")),
            "status": st,
            "published_at": v.get("published_at"),
            "created_at": v.get("created_at"),
            "updated_at": v.get("updated_at"),
            "editable": editable and st == "draft",
            "source": source,
            "assignment_types_supported": at,
            "family_statuses_supported": fs,
            "employee_levels_supported": el,
        }

    def _benefits_to_api(
        self,
        rows: List[Dict[str, Any]],
        *,
        include_internal: bool,
        overrides_by_benefit_id: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for b in rows:
            cap = _normalize_cap_rule(b.get("cap_rule_json"))
            item = {
                "category": b.get("category"),
                "benefit_key": b.get("benefit_key"),
                "benefit_label": b.get("benefit_label"),
                "covered": bool(b.get("covered")),
                # Provenance + per-field extraction confidence so the builder can
                # badge AI-extracted rows (source='extracted_llm') with a
                # confidence indicator. See AIQ-991.
                "source": b.get("source"),
                "field_confidence": b.get("field_confidence"),
                "value_type": b.get("value_type") or "none",
                "amount_value": b.get("amount_value"),
                "currency_code": b.get("currency_code"),
                "percentage_value": b.get("percentage_value"),
                "unit_frequency": b.get("unit_frequency") or "one_time",
                "notes": b.get("notes"),
                "conditions_json": b.get("conditions_json") if isinstance(b.get("conditions_json"), dict) else {},
                "assignment_types": list(b.get("assignment_types") or []),
                "family_statuses": list(b.get("family_statuses") or []),
                "employee_levels": list(b.get("employee_levels") or []),
                "display_order": int(b.get("display_order") or 0),
                "allowance_cap": allowance_cap_from_row(b),
                "cap_rule_json": cap,
                # Section C overrides serialize alongside the base row. Empty
                # list when this benefit has no jurisdiction-aware overrides
                # (the common case). Frontend renders nothing for an empty
                # array; the override-edit drawer reads/writes this field.
                "jurisdiction_overrides": _serialize_overrides(
                    overrides_by_benefit_id.get(str(b.get("id")), [])
                    if overrides_by_benefit_id and b.get("id")
                    else []
                ),
            }
            if include_internal:
                item["id"] = str(b.get("id")) if b.get("id") else None
                item["is_active"] = bool(b.get("is_active", True))
                item["targeting_signature"] = b.get("targeting_signature")
            out.append(item)
        return out

    def _group_categories(self, benefit_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[Dict[str, Any]]] = {c.value: [] for c in PolicyConfigCategory}
        for it in benefit_items:
            cat = it.get("category")
            if not cat or str(cat) not in CATEGORY_LABELS:
                ck = str(it.get("benefit_key") or "")
                cat = PolicyConfigCategory.compensation_allowances.value
                for bk, _lbl, c in _CANONICAL_KEYS:
                    if bk == ck:
                        cat = c.value
                        break
            cat = str(cat)
            buckets.setdefault(cat, []).append(it)
        ordered = [c.value for c in PolicyConfigCategory]
        blocks: List[Dict[str, Any]] = []
        for key in ordered:
            items = sorted(buckets.get(key, []), key=lambda x: (x.get("display_order") or 0, x.get("benefit_key") or ""))
            if not items:
                continue
            blocks.append(
                {
                    "category_key": key,
                    "category_label": CATEGORY_LABELS.get(key, key),
                    "benefits": items,
                }
            )
        return blocks

    def build_payload(
        self,
        company_id: str,
        *,
        version: Optional[Dict[str, Any]],
        benefits: List[Dict[str, Any]],
        editable: bool,
        source: str,
        assignment_type: Optional[str] = None,
        family_status: Optional[str] = None,
        employee_level: Optional[str] = None,
        effective_rows_only: bool = False,
        targeting_strict: bool = False,
    ) -> Dict[str, Any]:
        benefits_view = self._filter_benefits_matrix_query(
            benefits,
            assignment_type=assignment_type,
            family_status=family_status,
            employee_level=employee_level,
            effective_rows_only=effective_rows_only,
            strict_context=targeting_strict,
        )
        meta = self._version_to_metadata(version, benefits, editable=editable, source=source)
        # Section C: bulk fetch overrides for these benefit rows. Single
        # query, grouped server-side. Empty dict for rows without an id
        # (e.g. virtual scaffold rows in the empty_scaffold path) so the
        # serializer just emits empty jurisdiction_overrides arrays.
        # `getattr` keeps the service tolerant of older test fakes that
        # haven't grown the override-aware helpers yet — the override
        # tests use their own fake which does implement them.
        benefit_ids = [str(b.get("id")) for b in benefits_view if b.get("id")]
        _list_ovs = getattr(
            self._db,
            "list_jurisdiction_overrides_for_benefit_rows",
            lambda _ids: {},
        )
        overrides_by_id = _list_ovs(benefit_ids) if benefit_ids else {}
        bapi = self._benefits_to_api(
            benefits_view,
            include_internal=True,
            overrides_by_benefit_id=overrides_by_id,
        )
        return {
            **meta,
            "categories": self._group_categories(bapi),
            "preview_context": {
                "assignment_type": assignment_type,
                "family_status": family_status,
                "employee_level": employee_level,
                "effective_rows_only": effective_rows_only,
                "note": "Selectors filter this response only; the underlying policy is unchanged.",
            },
        }

    def get_working_payload(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str] = None,
        family_status: Optional[str] = None,
        employee_level: Optional[str] = None,
        effective_rows_only: bool = False,
    ) -> Dict[str, Any]:
        cfg = self._config(company_id)
        pid = str(cfg["id"])
        draft = self._db.get_policy_config_draft_for_config(pid)
        if draft:
            benefits = self._db.list_policy_config_benefits(str(draft["id"]))
            return self.build_payload(
                company_id,
                version=draft,
                benefits=benefits,
                editable=True,
                source="draft",
                assignment_type=assignment_type,
                family_status=family_status,
                employee_level=employee_level,
                effective_rows_only=effective_rows_only,
                targeting_strict=False,
            )
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if pub:
            benefits = self._db.list_policy_config_benefits(str(pub["id"]))
            return self.build_payload(
                company_id,
                version=pub,
                benefits=benefits,
                editable=False,
                source="published_clone",
                assignment_type=assignment_type,
                family_status=family_status,
                employee_level=employee_level,
                effective_rows_only=effective_rows_only,
                targeting_strict=False,
            )
        benefits_dicts = _canonical_seed_rows("virtual")
        virtual = {"id": None, "status": "empty_scaffold", "effective_date": date.today().isoformat(), "version_number": 0}
        return self.build_payload(
            company_id,
            version=virtual,
            benefits=benefits_dicts,
            editable=True,
            source="empty_scaffold",
            assignment_type=assignment_type,
            family_status=family_status,
            employee_level=employee_level,
            effective_rows_only=effective_rows_only,
            targeting_strict=False,
        )

    def empty_onboarding_payload(
        self,
        *,
        assignment_type: Optional[str] = None,
        family_status: Optional[str] = None,
        employee_level: Optional[str] = None,
        effective_rows_only: bool = False,
    ) -> Dict[str, Any]:
        """Company-independent empty scaffold for an HR not yet linked to a company.

        Mirrors the ``empty_scaffold`` branch of :meth:`get_working_payload` but
        takes no ``company_id``, so a not-yet-onboarded HR gets a graceful
        read-only scaffold instead of a 400. ``editable=False`` because nothing
        can be saved until the company exists; ``company_setup_required`` signals
        the UI to prompt company setup. See SKILL.md (relopass-e2e-test) Phase 0.5:
        a missing precondition must degrade gracefully, never hard-fail.
        """
        benefits_dicts = _canonical_seed_rows("virtual")
        virtual = {"id": None, "status": "empty_scaffold", "effective_date": date.today().isoformat(), "version_number": 0}
        payload = self.build_payload(
            "",
            version=virtual,
            benefits=benefits_dicts,
            editable=False,
            source="empty_scaffold",
            assignment_type=assignment_type,
            family_status=family_status,
            employee_level=employee_level,
            effective_rows_only=effective_rows_only,
            targeting_strict=False,
        )
        payload["company_setup_required"] = True
        return payload

    def empty_diff(self) -> Dict[str, Any]:
        """Company-independent empty Draft-vs-Live diff for a not-yet-onboarded HR.

        Same shape as :meth:`compute_diff` with no draft and no published version,
        so the UI's "Draft vs Live" section renders empty instead of 400ing.
        """
        return {
            "live": {"version": None, "rows": []},
            "draft": {"version": None, "rows": []},
            "diff": {
                "added": [],
                "removed": [],
                "changed": [],
                "unchanged_count": 0,
                "summary": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
            },
            "company_setup_required": True,
        }

    def get_published_payload(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str] = None,
        family_status: Optional[str] = None,
        employee_level: Optional[str] = None,
        effective_rows_only: bool = False,
    ) -> Dict[str, Any]:
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if not pub:
            return {
                "policy_version": None,
                "version_number": None,
                "effective_date": None,
                "status": "none",
                "published_at": None,
                "editable": False,
                "source": "none",
                "assignment_types_supported": [],
                "family_statuses_supported": [],
                "employee_levels_supported": [],
                "categories": [],
                "preview_context": {
                    "assignment_type": assignment_type,
                    "family_status": family_status,
                    "employee_level": employee_level,
                    "effective_rows_only": effective_rows_only,
                    "note": "Selectors filter this response only; the underlying policy is unchanged.",
                },
            }
        benefits = self._db.list_policy_config_benefits(str(pub["id"]))
        return self.build_payload(
            company_id,
            version=pub,
            benefits=benefits,
            editable=False,
            source="published",
            assignment_type=assignment_type,
            family_status=family_status,
            employee_level=employee_level,
            effective_rows_only=effective_rows_only,
            targeting_strict=False,
        )

    def ensure_draft(self, company_id: str, *, created_by: Optional[str]) -> Dict[str, Any]:
        cfg = self._config(company_id)
        pid = str(cfg["id"])
        existing = self._db.get_policy_config_draft_for_config(pid)
        if existing:
            benefits = self._db.list_policy_config_benefits(str(existing["id"]))
            return self.build_payload(company_id, version=existing, benefits=benefits, editable=True, source="draft")
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        next_n = self._db.max_policy_config_version_number(pid) + 1
        eff = date.today().isoformat()
        if pub:
            eff = _iso_date(pub.get("effective_date"))
        vid = self._db.insert_policy_config_version(
            pid, next_n, "draft", eff, created_by=created_by
        )
        if pub:
            prev = self._db.list_policy_config_benefits(str(pub["id"]))
            for b in prev:
                row = {k: v for k, v in b.items() if k != "id"}
                row["policy_config_version_id"] = vid
                row["targeting_signature"] = compute_targeting_signature(
                    row.get("assignment_types") or [],
                    row.get("family_statuses") or [],
                    row.get("employee_levels") or [],
                )
                self._db.insert_policy_config_benefit_row(row)
        else:
            for row in _canonical_seed_rows(vid):
                self._db.insert_policy_config_benefit_row(row)
        vrow = self._db.get_policy_config_version_row(vid)
        benefits = self._db.list_policy_config_benefits(vid)
        return self.build_payload(company_id, version=vrow, benefits=benefits, editable=True, source="draft_created")

    def validate_put_body(self, body: Dict[str, Any]) -> None:
        errs: List[Dict[str, Any]] = []
        pv = body.get("policy_version")
        if not pv or not str(pv).strip():
            errs.append({"field": "policy_version", "message": "Draft version id is required"})
        ed = body.get("effective_date")
        if not ed:
            errs.append({"field": "effective_date", "message": "effective_date is required"})
        cats = body.get("categories")
        if not isinstance(cats, list) or not cats:
            errs.append({"field": "categories", "message": "categories[] is required"})
        if errs:
            raise ValueError(json.dumps({"code": "validation_error", "errors": errs}))
        seen: set = set()
        flat: List[Dict[str, Any]] = []
        for ci, c in enumerate(cats):
            if not isinstance(c, dict):
                errs.append({"field": f"categories[{ci}]", "message": "Each category must be an object"})
                continue
            ck = c.get("category_key")
            if ck and ck not in CATEGORY_LABELS and ck not in [x.value for x in PolicyConfigCategory]:
                errs.append({"field": f"categories[{ci}].category_key", "message": f"Invalid category {ck!r}"})
            for bi, ben in enumerate(c.get("benefits") or []):
                if not isinstance(ben, dict):
                    errs.append({"field": f"categories[{ci}].benefits[{bi}]", "message": "Invalid benefit row"})
                    continue
                merged = dict(ben)
                if ck and not merged.get("category"):
                    merged["category"] = ck
                flat.append(merged)
        if errs:
            raise ValueError(json.dumps({"code": "validation_error", "errors": errs}))
        for i, ben in enumerate(flat):
            try:
                m = PolicyConfigBenefitWrite.model_validate(
                    {
                        "benefit_key": ben.get("benefit_key"),
                        "benefit_label": ben.get("benefit_label"),
                        "category": ben.get("category") or PolicyConfigCategory.compensation_allowances.value,
                        "covered": ben.get("covered", False),
                        "value_type": ben.get("value_type", "none"),
                        "amount_value": ben.get("amount_value"),
                        "currency_code": ben.get("currency_code"),
                        "percentage_value": ben.get("percentage_value"),
                        "unit_frequency": ben.get("unit_frequency", "one_time"),
                        "cap_rule_json": ben.get("cap_rule_json") if isinstance(ben.get("cap_rule_json"), dict) else {},
                        "notes": ben.get("notes"),
                        "conditions_json": ben.get("conditions_json")
                        if isinstance(ben.get("conditions_json"), dict)
                        else {},
                        "assignment_types": ben.get("assignment_types") or [],
                        "family_statuses": ben.get("family_statuses") or [],
                        "employee_levels": ben.get("employee_levels") or [],
                        "is_active": ben.get("is_active", True),
                        "display_order": ben.get("display_order", 0),
                    }
                )
            except Exception as ex:
                errs.append({"field": f"benefits[{i}]", "message": str(ex)})
                continue
            sig = compute_targeting_signature(
                [t.value for t in m.assignment_types],
                [t.value for t in m.family_statuses],
                [t.value for t in m.employee_levels],
            )
            dup_k = (m.benefit_key, sig)
            if dup_k in seen:
                errs.append(
                    {
                        "field": "benefits",
                        "message": f"Duplicate benefit_key + targeting for {m.benefit_key!r}",
                    }
                )
            seen.add(dup_k)
            vt = m.value_type.value if hasattr(m.value_type, "value") else str(m.value_type)
            if vt == "currency" and m.amount_value is not None and not (m.currency_code or "").strip():
                errs.append(
                    {
                        "field": f"benefit.{m.benefit_key}",
                        "message": "currency_code is required when amount_value is set",
                    }
                )
        if errs:
            raise ValueError(json.dumps({"code": "validation_error", "errors": errs}))

    def put_draft(
        self, company_id: str, body: Dict[str, Any], changed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        self.validate_put_body(body)
        vid = str(body["policy_version"])
        vmeta = self._db.get_policy_config_version_with_config(vid)
        if not vmeta or str(vmeta.get("_company_id")) != str(company_id):
            raise KeyError("draft_not_found")
        if str(vmeta.get("status")) != "draft":
            raise PermissionError("version_not_draft")
        cats = body.get("categories") or []
        flat_writes: List[PolicyConfigBenefitWrite] = []
        for c in cats:
            ck = c.get("category_key")
            for ben in c.get("benefits") or []:
                d = dict(ben)
                if ck and "category" not in d:
                    d["category"] = ck
                flat_writes.append(PolicyConfigBenefitWrite.model_validate(d))

        # Section C: validate override payloads BEFORE we destroy the old
        # rows. Cross-row collision check (UNIQUE on the DB enforces this
        # too; doing it in Python first lets us 422 with a useful message
        # instead of a 500 IntegrityError).
        from .policy_section_c_validation import (
            detect_override_collisions,
            normalize_country_codes,
            validate_jurisdiction_override,
        )
        for m in flat_writes:
            ov_dicts = [
                ov.model_dump() if hasattr(ov, "model_dump") else dict(ov)
                for ov in (m.jurisdiction_overrides or [])
            ]
            for ov in ov_dicts:
                # Normalize countries before validating so SG and "sg" are
                # the same and we reject only genuinely unknown codes.
                ov["jurisdiction_countries"] = normalize_country_codes(
                    list(ov.get("jurisdiction_countries") or [])
                )
                # Pydantic enums on optional axes need to flatten to .value
                # for downstream Python comparison (resolver uses strings).
                ovl = ov.get("employee_level")
                ov["employee_level"] = ovl.value if hasattr(ovl, "value") else ovl
                ova = ov.get("assignment_type")
                ov["assignment_type"] = ova.value if hasattr(ova, "value") else ova
                validate_jurisdiction_override(ov)
            collision = detect_override_collisions(ov_dicts)
            if collision:
                import json as _json
                raise ValueError(
                    _json.dumps(
                        {"code": "validation_error", "errors": [collision]}
                    )
                )

        # AIQ-839: snapshot existing rows (keyed by benefit_key + targeting) BEFORE
        # the destructive delete so the audit trail can record old→new per benefit.
        prior_by_key = {
            (str(b.get("benefit_key")), str(b.get("targeting_signature") or "global")): b
            for b in (self._db.list_policy_config_benefits(vid) or [])
        }
        _write_audit = getattr(self._db, "insert_policy_config_benefit_audit_row", None)
        _replace_ovs = getattr(
            self._db, "replace_jurisdiction_overrides_for_benefit", lambda _bid, _ovs: None
        )

        # AIQ-1070: collect every row, then write them in ONE atomic batched call.
        # The old code deleted then inserted benefit + audit + override rows one at
        # a time — hundreds of sequential round-trips (~33s for a full matrix), and a
        # mid-loop failure left the draft partial/empty (the destructive delete had
        # already committed).
        benefit_rows: List[Dict[str, Any]] = []
        audit_rows: List[Dict[str, Any]] = []
        override_writes: List[Tuple[str, List[Dict[str, Any]]]] = []
        for m in flat_writes:
            sig = compute_targeting_signature(
                [t.value for t in m.assignment_types],
                [t.value for t in m.family_statuses],
                [t.value for t in m.employee_levels],
            )
            row = {
                "policy_config_version_id": vid,
                "benefit_key": m.benefit_key,
                "benefit_label": m.benefit_label,
                "category": m.category.value if hasattr(m.category, "value") else str(m.category),
                "covered": m.covered,
                "value_type": m.value_type.value if hasattr(m.value_type, "value") else str(m.value_type),
                "amount_value": m.amount_value,
                "currency_code": m.currency_code,
                "percentage_value": m.percentage_value,
                "unit_frequency": m.unit_frequency.value
                if hasattr(m.unit_frequency, "value")
                else str(m.unit_frequency),
                "cap_rule_json": m.cap_rule_json,
                "notes": m.notes,
                "conditions_json": m.conditions_json,
                "assignment_types": [t.value for t in m.assignment_types],
                "family_statuses": [t.value for t in m.family_statuses],
                "employee_levels": [t.value for t in m.employee_levels],
                "targeting_signature": sig,
                "is_active": m.is_active,
                "display_order": m.display_order,
                # AIQ-839: this PUT path is the only one where HR enters values
                # by hand, so every row written here is a manual HR entry.
                "source": "manual_hr",
                "auto_generated": False,
            }
            # AIQ-1070: pre-generate the id so the audit row can reference it
            # without a per-row insert round-trip.
            inserted_id = str(uuid.uuid4())
            row["id"] = inserted_id
            benefit_rows.append(row)
            # AIQ-839: append a field-level audit row (old→new) for this benefit.
            if callable(_write_audit):
                prior = prior_by_key.get((str(m.benefit_key), str(sig)))
                audit_rows.append(
                    {
                        "benefit_id": inserted_id,
                        "policy_config_version_id": vid,
                        "benefit_key": m.benefit_key,
                        "action": "update" if prior else "insert",
                        "old_value": _benefit_audit_value(prior) if prior else None,
                        "new_value": _benefit_audit_value(row),
                        "source": "manual_hr",
                        "changed_by": changed_by,
                    }
                )
            # Section C: persist overrides for this benefit row. Empty list
            # means "no overrides" — the helper deletes prior rows and
            # inserts nothing, which is the correct shape after the parent
            # row was just freshly inserted.
            ov_payloads = [
                ov.model_dump() if hasattr(ov, "model_dump") else dict(ov)
                for ov in (m.jurisdiction_overrides or [])
            ]
            for ov in ov_payloads:
                ov["jurisdiction_countries"] = normalize_country_codes(
                    list(ov.get("jurisdiction_countries") or [])
                )
                ovl = ov.get("employee_level")
                ov["employee_level"] = ovl.value if hasattr(ovl, "value") else ovl
                ova = ov.get("assignment_type")
                ov["assignment_type"] = ova.value if hasattr(ova, "value") else ova
            override_writes.append((inserted_id, ov_payloads))

        # AIQ-1070: one atomic batched write (delete + benefit inserts + audit
        # inserts, single transaction). Fall back to the legacy per-row path for
        # older DB stubs that lack the batched method.
        _replace = getattr(self._db, "replace_policy_config_benefits", None)
        if callable(_replace):
            _replace(vid, benefit_rows, audit_rows)
        else:
            self._db.delete_policy_config_benefits_for_version(vid)
            for _r in benefit_rows:
                self._db.insert_policy_config_benefit_row(_r)
            if callable(_write_audit):
                for _a in audit_rows:
                    _write_audit(_a)
        # Overrides are written after the benefit rows exist (they FK to them).
        for _bid, _ovs in override_writes:
            _replace_ovs(_bid, _ovs)
        ed = str(body.get("effective_date"))[:10]
        self._db.update_policy_config_version_effective_date(vid, ed, only_if_draft=True)
        vrow = self._db.get_policy_config_version_row(vid)
        benefits = self._db.list_policy_config_benefits(vid)
        return self.build_payload(company_id, version=vrow, benefits=benefits, editable=True, source="draft")

    def get_version_readonly_payload(self, company_id: str, version_id: str) -> Dict[str, Any]:
        """Load a published or archived version for read-only review (history)."""
        vm = self._db.get_policy_config_version_with_config(str(version_id))
        if not vm or str(vm.get("_company_id")) != str(company_id):
            raise KeyError("version_not_found")
        if str(vm.get("_config_key") or "") != CONFIG_KEY:
            raise KeyError("version_not_found")
        st = str(vm.get("status") or "")
        if st not in ("published", "archived"):
            raise PermissionError("version_not_readable")
        benefits = self._db.list_policy_config_benefits(str(version_id))
        vrow = self._db.get_policy_config_version_row(str(version_id))
        src = "archived" if st == "archived" else "published_snapshot"
        return self.build_payload(
            company_id,
            version=vrow,
            benefits=benefits,
            editable=False,
            source=src,
        )

    def publish_draft(
        self,
        company_id: str,
        *,
        policy_version_id: Optional[str],
        created_by: Optional[str],
    ) -> Dict[str, Any]:
        cfg = self._config(company_id)
        pid = str(cfg["id"])
        draft = self._db.get_policy_config_draft_for_config(pid)
        if not draft:
            raise KeyError("no_draft")
        vid = str(policy_version_id).strip() if policy_version_id else str(draft["id"])
        if vid != str(draft["id"]):
            raise PermissionError("draft_mismatch")
        vmeta = self._db.get_policy_config_version_with_config(vid)
        if not vmeta or str(vmeta.get("_company_id")) != str(company_id):
            raise KeyError("draft_not_found")
        raw_ed = vmeta.get("effective_date")
        if raw_ed is None or not str(raw_ed).strip():
            raise ValueError(
                json.dumps(
                    {
                        "code": "validation_error",
                        "errors": [
                            {
                                "field": "effective_date",
                                "message": "Set an effective date on the draft before publishing.",
                            }
                        ],
                    }
                )
            )
        self._db.publish_policy_config_version_atomic(vid)
        pub = self._db.get_policy_config_version_row(vid)
        benefits = self._db.list_policy_config_benefits(vid)
        # Sprint A: rebuild Policy Assistant RAG index for this company
        # so the assistant answers from the just-published version. Best-
        # effort: never let an indexer failure block the publish (HR did
        # the work; the assistant is downstream).
        try:
            from .policy_chunk_indexer import index_company_policy
            index_company_policy(str(company_id))
        except Exception:
            log.exception(
                "policy_assistant index rebuild failed after publish company=%s vid=%s",
                company_id, vid,
            )
        return self.build_payload(company_id, version=pub, benefits=benefits, editable=False, source="published")

    # ------------------------------------------------------------------
    # Draft vs Live diff
    # ------------------------------------------------------------------
    # Fields compared field-by-field for "changed" rows. targeting is
    # part of the row identity (targeting_signature), so it is not listed
    # here — a change in targeting becomes a remove+add, not a field
    # change on the same row.
    _DIFF_COMPARE_FIELDS: Tuple[str, ...] = (
        "benefit_label",
        "category",
        "covered",
        "value_type",
        "amount_value",
        "currency_code",
        "percentage_value",
        "unit_frequency",
        "cap_rule_json",
        "conditions_json",
        "notes",
        "is_active",
        "display_order",
    )

    def _row_diff_key(self, row: Dict[str, Any]) -> Tuple[str, str]:
        """Identity for pairing live vs draft rows in the diff."""
        return (
            str(row.get("benefit_key") or ""),
            str(row.get("targeting_signature") or "global"),
        )

    def _row_field_changes(
        self, live: Dict[str, Any], draft: Dict[str, Any]
    ) -> List[str]:
        changed: List[str] = []
        for f in self._DIFF_COMPARE_FIELDS:
            lv = live.get(f)
            dv = draft.get(f)
            # Normalise dicts → stable JSON string so dict key order
            # doesn't show up as a false "changed". Same for missing vs
            # null — treat them the same.
            if isinstance(lv, dict) or isinstance(dv, dict):
                ls = json.dumps(lv or {}, sort_keys=True)
                ds = json.dumps(dv or {}, sort_keys=True)
                if ls != ds:
                    changed.append(f)
                continue
            if (lv or None) != (dv or None):
                changed.append(f)
        return changed

    def compute_diff(self, company_id: str) -> Dict[str, Any]:
        """
        Snapshot of {live, draft, diff} for the HR "Draft vs Live" view.

        Semantics:
          - live.rows   — the currently-published matrix, or empty if none
          - draft.rows  — the active draft, or empty if none
          - diff.added     — rows keyed in draft but not in live
          - diff.removed   — rows keyed in live but not in draft
          - diff.changed   — same (benefit_key, targeting_signature) in
                             both but at least one compared field differs;
                             each entry includes `changed_fields` so the
                             UI can highlight the exact cells that moved
          - diff.unchanged — paired rows with no field-level changes

        Pairs are stable: adding a new targeting variant creates an
        `added` entry; removing one creates a `removed` entry.
        """
        cfg = self._config(company_id)
        pid = str(cfg["id"])
        draft = self._db.get_policy_config_draft_for_config(pid)
        live = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)

        draft_rows = (
            self._db.list_policy_config_benefits(str(draft["id"])) if draft else []
        )
        live_rows = (
            self._db.list_policy_config_benefits(str(live["id"])) if live else []
        )

        draft_index = {self._row_diff_key(r): r for r in draft_rows}
        live_index = {self._row_diff_key(r): r for r in live_rows}
        all_keys = set(draft_index) | set(live_index)

        added: List[Dict[str, Any]] = []
        removed: List[Dict[str, Any]] = []
        changed: List[Dict[str, Any]] = []
        unchanged: List[Dict[str, Any]] = []

        for k in sorted(all_keys, key=lambda x: (x[0], x[1])):
            lv = live_index.get(k)
            dv = draft_index.get(k)
            if lv is None and dv is not None:
                added.append(dv)
            elif dv is None and lv is not None:
                removed.append(lv)
            elif lv is not None and dv is not None:
                diffs = self._row_field_changes(lv, dv)
                if diffs:
                    changed.append({"before": lv, "after": dv, "changed_fields": diffs})
                else:
                    unchanged.append(dv)

        def _version_meta(v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not v:
                return None
            return {
                "id": str(v.get("id")) if v.get("id") else None,
                "version_number": int(v.get("version_number") or 0),
                "status": str(v.get("status") or ""),
                "effective_date": _iso_date(v.get("effective_date")),
                "published_at": v.get("published_at"),
                "updated_at": v.get("updated_at"),
            }

        return {
            "live": {
                "version": _version_meta(live),
                "rows": self._benefits_to_api(live_rows, include_internal=True),
            },
            "draft": {
                "version": _version_meta(draft),
                "rows": self._benefits_to_api(draft_rows, include_internal=True),
            },
            "diff": {
                "added": self._benefits_to_api(added, include_internal=True),
                "removed": self._benefits_to_api(removed, include_internal=True),
                "changed": [
                    {
                        "before": self._benefits_to_api([c["before"]], include_internal=True)[0],
                        "after": self._benefits_to_api([c["after"]], include_internal=True)[0],
                        "changed_fields": c["changed_fields"],
                    }
                    for c in changed
                ],
                "unchanged_count": len(unchanged),
                "summary": {
                    "added": len(added),
                    "removed": len(removed),
                    "changed": len(changed),
                    "unchanged": len(unchanged),
                },
            },
        }

    def revert_row_to_live(
        self,
        company_id: str,
        *,
        benefit_key: str,
        targeting_signature: str,
    ) -> Dict[str, Any]:
        """
        Bring one row of the current draft back to whatever the live
        version has for that (benefit_key, targeting_signature).

        Three cases, mirroring the diff semantics:
          * row exists in both live + draft → draft row is overwritten
            with the live row's values (field-level revert).
          * row exists only in draft (user added it) → draft row is
            deleted.
          * row exists only in live (user removed it from draft) →
            live row is re-inserted into the draft.

        Idempotent: reverting a row that already matches live is a
        no-op and returns the fresh diff unchanged.
        """
        cfg = self._config(company_id)
        pid = str(cfg["id"])
        draft = self._db.get_policy_config_draft_for_config(pid)
        if not draft:
            raise KeyError("no_draft")
        live = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        draft_vid = str(draft["id"])
        draft_rows = self._db.list_policy_config_benefits(draft_vid)
        live_rows = (
            self._db.list_policy_config_benefits(str(live["id"])) if live else []
        )
        bk = str(benefit_key or "").strip()
        ts = str(targeting_signature or "global").strip()
        if not bk:
            raise ValueError(json.dumps({"code": "validation_error", "errors": [
                {"field": "benefit_key", "message": "benefit_key is required"}
            ]}))
        draft_row = next(
            (r for r in draft_rows if str(r.get("benefit_key")) == bk
             and str(r.get("targeting_signature") or "global") == ts),
            None,
        )
        live_row = next(
            (r for r in live_rows if str(r.get("benefit_key")) == bk
             and str(r.get("targeting_signature") or "global") == ts),
            None,
        )
        if draft_row is None and live_row is None:
            raise KeyError("row_not_found")
        if live_row is not None and draft_row is not None:
            # Overwrite draft row with live row's fields (preserving id + vid).
            self._db.delete_policy_config_benefit_by_key(
                draft_vid, benefit_key=bk, targeting_signature=ts
            )
            insert = dict(live_row)
            insert["policy_config_version_id"] = draft_vid
            insert.pop("id", None)
            insert.pop("created_at", None)
            insert.pop("updated_at", None)
            self._db.insert_policy_config_benefit_row(insert)
        elif draft_row is not None and live_row is None:
            # Row added in draft; revert = remove.
            self._db.delete_policy_config_benefit_by_key(
                draft_vid, benefit_key=bk, targeting_signature=ts
            )
        elif live_row is not None and draft_row is None:
            # Row removed in draft; revert = re-insert from live.
            insert = dict(live_row)
            insert["policy_config_version_id"] = draft_vid
            insert.pop("id", None)
            insert.pop("created_at", None)
            insert.pop("updated_at", None)
            self._db.insert_policy_config_benefit_row(insert)
        return self.compute_diff(company_id)

    # ------------------------------------------------------------------
    # Templates (Phase 3)
    # ------------------------------------------------------------------
    def apply_template_to_draft(
        self,
        company_id: str,
        *,
        template_key: str,
        replace_existing_draft: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Populate the company's draft from a starter template
        (Conservative / Standard / Premium). Live published version is
        untouched — employees keep seeing the current policy until HR
        publishes the replacement.

        Flow:
          1. Ensure a draft version exists. If one already has rows,
             refuse unless replace_existing_draft=True (product
             requested "flexibility" with a confirmation UX on the
             frontend — the flag is the confirmation).
          2. Delete any existing draft rows.
          3. Insert the expanded template rows (tiered rows expand
             into one row per employee level).
          4. Return the fresh working payload so the UI can re-render
             without a second GET.

        Raises:
          KeyError("unknown_template:<key>")  — bad template_key
          KeyError("draft_has_rows")          — draft exists with rows
                                                and replace_existing_draft=False
        """
        from .policy_config_templates import expand_template_rows, get_template

        tpl = get_template(template_key)
        if tpl is None:
            raise KeyError(f"unknown_template:{template_key}")

        cfg = self._config(company_id)
        pid = str(cfg["id"])
        draft = self._db.get_policy_config_draft_for_config(pid)
        if not draft:
            # Seed a fresh draft — start from published if one exists so
            # the template overwrites a known baseline cleanly.
            pub = self._db.get_latest_published_policy_config_version(
                str(company_id), CONFIG_KEY
            )
            if pub:
                next_n = int(pub.get("version_number") or 0) + 1
                eff = _iso_date(pub.get("effective_date"))
            else:
                next_n = 1
                eff = date.today().isoformat()
            vid = self._db.insert_policy_config_version(
                pid, next_n, "draft", eff, created_by=created_by
            )
        else:
            vid = str(draft["id"])
            existing_rows = self._db.list_policy_config_benefits(vid)
            if existing_rows and not replace_existing_draft:
                raise KeyError("draft_has_rows")

        # Wipe current draft rows and replace with template rows. Safe
        # for the "fresh draft" branch too — list_policy_config_benefits
        # on a brand-new draft returns [].
        self._db.delete_policy_config_benefits_for_version(vid)

        rows = expand_template_rows(template_key)
        for row in rows:
            sig = compute_targeting_signature(
                row.get("assignment_types") or [],
                row.get("family_statuses") or [],
                row.get("employee_levels") or [],
            )
            # benefit_label comes from the canonical registry rather than
            # the template — keeps HR-visible labels consistent with the
            # row drawer and the topic drill-down.
            label = next(
                (lbl for bk, lbl, _cat in _CANONICAL_KEYS if bk == row["benefit_key"]),
                row["benefit_key"],
            )
            row_payload = {
                "policy_config_version_id": vid,
                "benefit_label": label,
                "targeting_signature": sig,
                **row,
                # AIQ-854: starter-template rows are template-originated, not HR-typed.
                "source": "template_default",
                "auto_generated": True,
            }
            self._db.insert_policy_config_benefit_row(row_payload)

        vrow = self._db.get_policy_config_version_row(vid)
        benefits = self._db.list_policy_config_benefits(vid)
        return self.build_payload(
            company_id,
            version=vrow,
            benefits=benefits,
            editable=True,
            source="template_applied",
        )

    def import_extraction_to_draft(
        self,
        policy_id: str,
        *,
        changed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        AIQ-873: bridge extracted policy benefits (policy_extracted_benefits — the
        LLM value-extraction output, via db.list_policy_benefits) into the
        company's config-matrix draft. Per-field confidence + the source_quote
        citation ride through to the draft (AIQ-938-FU).

        For each extracted benefit whose key maps to a canonical matrix key
        (EXTRACTION_TO_MATRIX_BENEFIT_KEY), insert an `extracted_llm` row into the
        draft ONLY IF that matrix key is not already present — never clobbering a
        manual_hr / template_default / seeded row. Extracted free-text terms
        (eligibility / limits) land in `notes`; the per-field confidence lands in
        `field_confidence`. Structured amounts stay at defaults for HR to fill
        before publishing. The live published version is untouched.

        Returns {imported, skipped_existing, unmapped, version_id}.

        Raises KeyError("unknown_policy:<id>") when policy_id has no linked company.

        ``policy_id`` may be a policy_document id (the canonical E1b lineage) or a
        legacy company_policies id — see ``resolve_extraction_company_id``.
        """
        company_id = resolve_extraction_company_id(self._db, policy_id)
        if not company_id:
            raise KeyError(f"unknown_policy:{policy_id}")

        extracted = self._db.list_policy_benefits(policy_id)

        # Ensure a draft exists, then resolve its version id + current rows.
        self.ensure_draft(company_id, created_by=changed_by)
        cfg = self._config(company_id)
        draft = self._db.get_policy_config_draft_for_config(str(cfg["id"]))
        version_id = str(draft["id"])
        existing_rows = self._db.list_policy_config_benefits(version_id)
        # First row per benefit_key (the scaffold/real row we'd enrich or protect).
        by_key: Dict[str, Dict[str, Any]] = {}
        for r in existing_rows:
            by_key.setdefault(str(r["benefit_key"]), r)

        # A fresh draft is pre-seeded with all canonical keys as source='seeded'
        # scaffold rows; those ARE enrichable. Only HR-meaningful sources are
        # protected from clobbering.
        protected = {"manual_hr", "template_default", "extracted_llm"}

        imported: List[str] = []
        skipped_existing: List[str] = []
        unmapped: List[str] = []
        enrich: Dict[str, Dict[str, Any]] = {}  # matrix_key -> extracted benefit

        for b in extracted:
            ek = str(b.get("benefit_key") or "")
            mk = EXTRACTION_TO_MATRIX_BENEFIT_KEY.get(ek)
            if not mk:
                if ek:
                    unmapped.append(ek)
                continue
            ex = by_key.get(mk)
            if ex is not None and str(ex.get("source") or "") in protected:
                skipped_existing.append(mk)
                continue
            if mk in enrich:  # two extraction keys → one matrix key: first wins
                continue
            enrich[mk] = b
            imported.append(mk)

        if not enrich:
            return {
                "imported": imported,
                "skipped_existing": skipped_existing,
                "unmapped": unmapped,
                "version_id": version_id,
            }

        def _apply(row: Dict[str, Any], b: Dict[str, Any]) -> None:
            # AIQ-938-FU: notes now carry the extraction citation (source_quote)
            # in addition to eligibility/limits, so the HR review UI surfaces it.
            note = _extraction_draft_note(b)
            row["covered"] = True
            row["notes"] = note or row.get("notes")
            row["field_confidence"] = b.get("confidence")
            row["source"] = "extracted_llm"
            row["auto_generated"] = True

        # Rebuild the draft row set: enrich the seeded scaffold row for each mapped
        # key in place; append a fresh row for any mapped key with no existing row
        # (drafts cloned from a published baseline may omit some keys). Protected
        # rows pass through untouched. Mirrors the put_draft delete+reinsert pattern.
        seen: set = set()
        new_rows: List[Dict[str, Any]] = []
        for r in existing_rows:
            bk = str(r["benefit_key"])
            rr = {k: v for k, v in r.items() if k != "id"}
            rr["policy_config_version_id"] = version_id
            if bk in enrich and str(r.get("source") or "") not in protected:
                _apply(rr, enrich[bk])
                seen.add(bk)
            new_rows.append(rr)
        for mk, b in enrich.items():
            if mk in seen:
                continue
            label, category = _MATRIX_KEY_META[mk]
            rr = _benefit_row_defaults(mk)
            rr.update(
                {
                    "policy_config_version_id": version_id,
                    "benefit_key": mk,
                    "benefit_label": label,
                    "category": category,
                    "targeting_signature": compute_targeting_signature(
                        rr.get("assignment_types") or [],
                        rr.get("family_statuses") or [],
                        rr.get("employee_levels") or [],
                    ),
                }
            )
            _apply(rr, b)
            new_rows.append(rr)

        self._db.delete_policy_config_benefits_for_version(version_id)
        for rr in new_rows:
            self._db.insert_policy_config_benefit_row(rr)

        return {
            "imported": imported,
            "skipped_existing": skipped_existing,
            "unmapped": unmapped,
            "version_id": version_id,
        }

    def history(self, company_id: str) -> List[Dict[str, Any]]:
        cfg = self._config(company_id)
        rows = self._db.list_policy_config_versions_history(str(cfg["id"]))
        return [
            {
                "id": str(r.get("id")),
                "version_number": int(r.get("version_number") or 0),
                "status": r.get("status"),
                "effective_date": _iso_date(r.get("effective_date")),
                "created_at": r.get("created_at"),
                "published_at": r.get("published_at"),
                "created_by": r.get("created_by"),
            }
            for r in rows
        ]

    def employee_grouped_payload(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str],
        family_status: Optional[str],
        country: Optional[str] = None,
        employee_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the employee-resolved policy. Section C: when a destination
        country is supplied, jurisdiction overrides on each benefit row are
        applied via policy_section_c_resolver; the row's amount_value /
        currency_code / cap_rule_json / markdown clauses get folded with
        the most-specific override that matches.

        Without a country, overrides are returned alongside the base row
        (employee can still see "this benefit has SG-specific rules") but
        the resolver does not collapse them into a single effective row.
        """
        at_norm = normalize_assignment_type(assignment_type)
        fs_norm = normalize_family_status(family_status)
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if not pub:
            return {
                "has_policy_config": False,
                "effective_date": None,
                "policy_version": None,
                "version_number": None,
                "assignment_context": {
                    "assignment_type": at_norm,
                    "family_status": fs_norm,
                    "country": country,
                    "employee_level": employee_level,
                },
                "categories": [],
                "message": "No published compensation & allowance configuration for your employer.",
            }
        benefits = self._db.list_policy_config_benefits(str(pub["id"]))
        filtered: List[Dict[str, Any]] = []
        for b in benefits:
            if not b.get("is_active", True):
                continue
            if not b.get("covered"):
                continue
            # Forward employee_level: without it, strict_context drops every
            # level-gated row, so a fully level-gated published config (e.g. all
            # caps tagged manager/director) renders ZERO benefits to the employee.
            if not row_matches_targeting(
                b, at_norm, fs_norm, strict_context=True, employee_level=employee_level
            ):
                continue
            filtered.append(b)

        # Section C: bulk-load overrides for every surviving base row.
        # When the employee's country is known, fold the most-specific
        # match onto each row before serializing. This is where the
        # employee-side authority chain (Admin → HR → Employee) actually
        # produces a single effective number per benefit.
        benefit_ids = [str(b.get("id")) for b in filtered if b.get("id")]
        _list_ovs = getattr(
            self._db,
            "list_jurisdiction_overrides_for_benefit_rows",
            lambda _ids: {},
        )
        overrides_by_id = _list_ovs(benefit_ids) if benefit_ids else {}
        emp_ctx = {
            "country": country,
            "employee_level": employee_level,
            "assignment_type": at_norm,
        }
        if country:
            from .policy_section_c_resolver import resolve_effective_benefit
            resolved_rows: List[Dict[str, Any]] = []
            applied_override_ids: Dict[str, str] = {}
            for b in filtered:
                bid = str(b.get("id") or "")
                ovs = overrides_by_id.get(bid, [])
                effective, applied_id = resolve_effective_benefit(b, ovs, emp_ctx)
                resolved_rows.append(effective)
                if applied_id:
                    applied_override_ids[bid] = applied_id
            bapi = self._benefits_to_api(
                resolved_rows,
                include_internal=False,
                overrides_by_benefit_id=overrides_by_id,
            )
            # Surface which override (if any) was applied per row so the
            # employee UI can show "Singapore-specific cap" without having
            # to reapply the resolver client-side.
            for it, src in zip(bapi, resolved_rows):
                it["maximum_budget_explanation"] = maximum_budget_explanation(src)
                it["override_applied"] = bool(src.get("override_applied"))
                it["override_id"] = src.get("override_id")
        else:
            bapi = self._benefits_to_api(
                filtered,
                include_internal=False,
                overrides_by_benefit_id=overrides_by_id,
            )
            for it, src in zip(bapi, filtered):
                it["maximum_budget_explanation"] = maximum_budget_explanation(src)
                it["override_applied"] = False
                it["override_id"] = None
        return {
            "has_policy_config": True,
            "effective_date": _iso_date(pub.get("effective_date")),
            "policy_version": str(pub.get("id")),
            "version_number": int(pub.get("version_number") or 0),
            "assignment_context": {
                "assignment_type": at_norm,
                "family_status": fs_norm,
                "country": country,
                "employee_level": employee_level,
            },
            "categories": self._group_categories(bapi),
        }

    def caps_payload(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str],
        family_status: Optional[str],
        benefit_keys: Optional[Sequence[str]],
        service_module: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Published caps with normalized_cap_type / normalized_amount for estimate comparison."""
        from .policy_config_cap_compare import normalized_cap_record_from_benefit_row

        at_norm = normalize_assignment_type(assignment_type)
        fs_norm = normalize_family_status(family_status)
        filters: Dict[str, Any] = {
            "assignment_type": at_norm,
            "family_status": fs_norm,
            "benefit_keys": list(benefit_keys) if benefit_keys else None,
            "service_module": service_module,
        }
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if not pub:
            return {
                "metadata": {
                    "company_id": str(company_id),
                    "policy_version": None,
                    "effective_date": None,
                    "has_published_config": False,
                    "filters": filters,
                },
                "caps": [],
            }
        benefits = self._db.list_policy_config_benefits(str(pub["id"]))
        key_filter: Optional[set] = None
        if service_module and service_module in SERVICE_MODULE_BENEFIT_KEYS:
            key_filter = set(SERVICE_MODULE_BENEFIT_KEYS[service_module])
        if benefit_keys:
            bk = {str(x).strip() for x in benefit_keys if str(x).strip()}
            key_filter = key_filter.intersection(bk) if key_filter is not None else bk
        raw_rows: List[Dict[str, Any]] = []
        for b in benefits:
            if not b.get("is_active", True):
                continue
            if not b.get("covered"):
                continue
            bk = str(b.get("benefit_key") or "")
            if key_filter is not None and bk not in key_filter:
                continue
            if not row_matches_targeting(b, at_norm, fs_norm, strict_context=True):
                continue
            raw_rows.append(b)

        caps = [normalized_cap_record_from_benefit_row(b) for b in raw_rows]
        return {
            "metadata": {
                "company_id": str(company_id),
                "policy_version": str(pub.get("id")),
                "effective_date": _iso_date(pub.get("effective_date")),
                "has_published_config": True,
                "filters": filters,
            },
            "caps": caps,
        }

    def compare_provider_estimates_to_published_caps(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str],
        family_status: Optional[str],
        estimates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate monetary provider estimates against applicable published caps for the same context.
        """
        from .policy_config_cap_compare import evaluate_estimates_against_caps

        keys: set = set()
        for e in estimates:
            k = str(e.get("benefit_key") or "").strip()
            if k:
                keys.add(k)
        benefit_keys: Optional[List[str]] = sorted(keys) if keys else None

        bundle = self.caps_payload(
            company_id,
            assignment_type=assignment_type,
            family_status=family_status,
            benefit_keys=benefit_keys,
            service_module=None,
        )
        results = evaluate_estimates_against_caps(estimates, bundle["caps"])
        return {"metadata": bundle["metadata"], "results": results}
