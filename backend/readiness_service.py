"""
Case Readiness Core — resolve destination/route from canonical assignment context.
Templates are global/reusable; case state is per assignment_id only.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

# Normalize free-text / common country names to stable template keys (ISO2 where known).
_COUNTRY_ALIASES: Dict[str, str] = {
    "singapore": "SG",
    "sg": "SG",
    "france": "FR",
    "fr": "FR",
    "germany": "DE",
    "de": "DE",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "gb": "GB",
    "netherlands": "NL",
    "nl": "NL",
    "the netherlands": "NL",
    "spain": "ES",
    "es": "ES",
    "italy": "IT",
    "it": "IT",
    "japan": "JP",
    "jp": "JP",
    "australia": "AU",
    "au": "AU",
    "canada": "CA",
    "ca": "CA",
    "switzerland": "CH",
    "ch": "CH",
    "ireland": "IE",
    "ie": "IE",
}


def normalize_destination_key(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if re.fullmatch(r"[A-Za-z]{2}", s):
        return s.upper()
    key = _COUNTRY_ALIASES.get(s.lower())
    if key:
        return key
    # Title Case country name e.g. "Singapore"
    key2 = _COUNTRY_ALIASES.get(s.lower().strip())
    if key2:
        return key2
    return None


def extract_destination_from_profile(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    if not profile or not isinstance(profile, dict):
        return None
    mp = profile.get("movePlan") or {}
    if isinstance(mp, dict) and mp.get("destination"):
        return str(mp["destination"]).strip() or None
    rb = profile.get("relocationBasics") or {}
    if isinstance(rb, dict) and rb.get("destCountry"):
        return str(rb["destCountry"]).strip() or None
    return None


def extract_destination_from_case_profile(case_profile_json: Optional[str]) -> Optional[str]:
    if not case_profile_json:
        return None
    try:
        data = json.loads(case_profile_json) if isinstance(case_profile_json, str) else case_profile_json
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return extract_destination_from_profile(data)


DEFAULT_ROUTE_KEY = "employment"


def resolve_readiness_route_key(_assignment: Dict[str, Any], _profile: Optional[Dict[str, Any]]) -> str:
    """v1: single route bucket until platform stores permit route explicitly."""
    return DEFAULT_ROUTE_KEY
