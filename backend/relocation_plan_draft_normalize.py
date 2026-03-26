"""
Map employee intake wizard ``draft_json`` into the profile shape expected by
``relocation_plan_status_derivation`` (``primaryApplicant``, ``movePlan``, top-level family).

Stored drafts use: relocationBasics, employeeProfile, assignmentContext, familyMembers.
Derivation historically expected: primaryApplicant, movePlan, maritalStatus, spouse, dependents.
"""
from __future__ import annotations

from typing import Any, Dict


def _nz(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (dict, list)):
        return bool(val)
    s = str(val).strip()
    return bool(s and s.lower() != "unknown")


def profile_for_plan_derivation(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy of ``raw`` with synthetic keys merged in so derivation rules see
    wizard data. Existing ``primaryApplicant`` / ``movePlan`` values are preserved unless
    wizard sections provide stronger fills.
    """
    if not raw or not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = dict(raw)

    ep = raw.get("employeeProfile") if isinstance(raw.get("employeeProfile"), dict) else {}
    ac = raw.get("assignmentContext") if isinstance(raw.get("assignmentContext"), dict) else {}
    rb = raw.get("relocationBasics") if isinstance(raw.get("relocationBasics"), dict) else {}
    fm = raw.get("familyMembers") if isinstance(raw.get("familyMembers"), dict) else {}

    pa: Dict[str, Any] = {}
    existing_pa = out.get("primaryApplicant")
    if isinstance(existing_pa, dict):
        pa = dict(existing_pa)

    if _nz(ep.get("fullName")):
        pa["fullName"] = ep.get("fullName")
    if _nz(ep.get("nationality")):
        pa["nationality"] = ep.get("nationality")

    emp: Dict[str, Any] = {}
    existing_emp = pa.get("employer")
    if isinstance(existing_emp, dict):
        emp = dict(existing_emp)
    if _nz(ac.get("jobTitle")):
        emp["roleTitle"] = ac.get("jobTitle")
    # Wizard step 4 requires salaryBand; seniorityBand is optional — map either into jobLevel for derivation.
    if _nz(ac.get("seniorityBand")):
        emp["jobLevel"] = ac.get("seniorityBand")
    elif _nz(ac.get("salaryBand")):
        emp["jobLevel"] = ac.get("salaryBand")
    if emp:
        pa["employer"] = emp

    if pa:
        out["primaryApplicant"] = pa

    mp: Dict[str, Any] = {}
    existing_mp = out.get("movePlan")
    if isinstance(existing_mp, dict):
        mp = dict(existing_mp)
    og = ", ".join(x for x in [rb.get("originCity"), rb.get("originCountry")] if _nz(x))
    ds = ", ".join(x for x in [rb.get("destCity"), rb.get("destCountry")] if _nz(x))
    if og:
        mp["origin"] = og
    if ds:
        mp["destination"] = ds
    if mp:
        out["movePlan"] = mp

    if _nz(fm.get("maritalStatus")):
        out["maritalStatus"] = fm.get("maritalStatus")
    sp = fm.get("spouse")
    if isinstance(sp, dict) and _nz(sp.get("fullName")):
        out["spouse"] = sp
    children = fm.get("children")
    if isinstance(children, list) and children:
        deps = []
        for c in children:
            if not isinstance(c, dict):
                continue
            fn = str(c.get("fullName") or "").strip()
            first = str(c.get("firstName") or "").strip()
            if not first and fn:
                first = fn.split()[0] if fn.split() else ""
            if first:
                row = dict(c)
                row["firstName"] = first
                deps.append(row)
        if deps:
            out["dependents"] = deps

    return out
