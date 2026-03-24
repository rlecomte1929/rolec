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
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..database import Database
from ..schemas_compensation_allowance import (
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


def compute_targeting_signature(assignment_types: Sequence[str], family_statuses: Sequence[str]) -> str:
    a = sorted({str(x).strip() for x in assignment_types if str(x).strip()})
    f = sorted({str(x).strip() for x in family_statuses if str(x).strip()})
    if not a and not f:
        return "global"
    payload = json.dumps({"assignment_types": a, "family_statuses": f}, separators=(",", ":"), sort_keys=True)
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
        sig = compute_targeting_signature(d["assignment_types"], d["family_statuses"])
        rows.append(
            {
                "policy_config_version_id": version_id,
                "benefit_key": bk,
                "benefit_label": label,
                "category": cat.value,
                "targeting_signature": sig,
                "display_order": order,
                **d,
            }
        )
    return rows


def _normalize_cap_rule(cap: Any) -> Dict[str, Any]:
    if isinstance(cap, dict):
        return cap
    if isinstance(cap, str) and cap.strip():
        try:
            return json.loads(cap)
        except Exception:
            return {}
    return {}


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
    ) -> List[Dict[str, Any]]:
        targeting = assignment_type is not None or family_status is not None
        if not targeting and not effective_rows_only:
            return benefits
        out: List[Dict[str, Any]] = []
        for b in benefits:
            if effective_rows_only:
                if not b.get("is_active", True) or not b.get("covered"):
                    continue
            if targeting:
                if not row_matches_targeting(
                    b, assignment_type, family_status, strict_context=strict_context
                ):
                    continue
            out.append(b)
        return out

    def _config(self, company_id: str) -> Dict[str, Any]:
        return self._db.ensure_policy_config(str(company_id), CONFIG_KEY)

    def _collect_supported_lists(self, benefits: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        at_set: set = set()
        fs_set: set = set()
        for b in benefits:
            for x in b.get("assignment_types") or []:
                if str(x).strip():
                    at_set.add(str(x).strip())
            for x in b.get("family_statuses") or []:
                if str(x).strip():
                    fs_set.add(str(x).strip())
        return sorted(at_set), sorted(fs_set)

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
            at, fs = self._collect_supported_lists(benefits)
            return {
                "policy_version": None,
                "version_number": None,
                "effective_date": today,
                "status": "empty_scaffold",
                "editable": editable,
                "source": source,
                "assignment_types_supported": at,
                "family_statuses_supported": fs,
            }
        at, fs = self._collect_supported_lists(benefits)
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
        }

    def _benefits_to_api(self, rows: List[Dict[str, Any]], *, include_internal: bool) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for b in rows:
            cap = _normalize_cap_rule(b.get("cap_rule_json"))
            item = {
                "category": b.get("category"),
                "benefit_key": b.get("benefit_key"),
                "benefit_label": b.get("benefit_label"),
                "covered": bool(b.get("covered")),
                "value_type": b.get("value_type") or "none",
                "amount_value": b.get("amount_value"),
                "currency_code": b.get("currency_code"),
                "percentage_value": b.get("percentage_value"),
                "unit_frequency": b.get("unit_frequency") or "one_time",
                "notes": b.get("notes"),
                "conditions_json": b.get("conditions_json") if isinstance(b.get("conditions_json"), dict) else {},
                "assignment_types": list(b.get("assignment_types") or []),
                "family_statuses": list(b.get("family_statuses") or []),
                "display_order": int(b.get("display_order") or 0),
                "allowance_cap": allowance_cap_from_row(b),
                "cap_rule_json": cap,
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
        effective_rows_only: bool = False,
        targeting_strict: bool = False,
    ) -> Dict[str, Any]:
        benefits_view = self._filter_benefits_matrix_query(
            benefits,
            assignment_type=assignment_type,
            family_status=family_status,
            effective_rows_only=effective_rows_only,
            strict_context=targeting_strict,
        )
        meta = self._version_to_metadata(version, benefits, editable=editable, source=source)
        bapi = self._benefits_to_api(benefits_view, include_internal=True)
        return {
            **meta,
            "categories": self._group_categories(bapi),
            "preview_context": {
                "assignment_type": assignment_type,
                "family_status": family_status,
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
            effective_rows_only=effective_rows_only,
            targeting_strict=False,
        )

    def get_published_payload(
        self,
        company_id: str,
        *,
        assignment_type: Optional[str] = None,
        family_status: Optional[str] = None,
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
                "categories": [],
                "preview_context": {
                    "assignment_type": assignment_type,
                    "family_status": family_status,
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
                    row.get("assignment_types") or [], row.get("family_statuses") or []
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

    def put_draft(self, company_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
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
        self._db.delete_policy_config_benefits_for_version(vid)
        for m in flat_writes:
            sig = compute_targeting_signature(
                [t.value for t in m.assignment_types],
                [t.value for t in m.family_statuses],
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
                "targeting_signature": sig,
                "is_active": m.is_active,
                "display_order": m.display_order,
            }
            self._db.insert_policy_config_benefit_row(row)
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
        return self.build_payload(company_id, version=pub, benefits=benefits, editable=False, source="published")

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
    ) -> Dict[str, Any]:
        at_norm = normalize_assignment_type(assignment_type)
        fs_norm = normalize_family_status(family_status)
        pub = self._db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if not pub:
            return {
                "has_policy_config": False,
                "effective_date": None,
                "policy_version": None,
                "version_number": None,
                "assignment_context": {"assignment_type": at_norm, "family_status": fs_norm},
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
            if not row_matches_targeting(b, at_norm, fs_norm, strict_context=True):
                continue
            filtered.append(b)
        bapi = self._benefits_to_api(filtered, include_internal=False)
        for it, src in zip(bapi, filtered):
            it["maximum_budget_explanation"] = maximum_budget_explanation(src)
        return {
            "has_policy_config": True,
            "effective_date": _iso_date(pub.get("effective_date")),
            "policy_version": str(pub.get("id")),
            "version_number": int(pub.get("version_number") or 0),
            "assignment_context": {"assignment_type": at_norm, "family_status": fs_norm},
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
