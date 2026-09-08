# backend/app/services/vendor_discovery/accreditation_checker.py
"""
Accreditation checker for vendor candidates (VEN-07).
Domain-based lookup against a curated dict of known accredited companies, with a
fuzzy name-match fallback. Grow KNOWN_ACCREDITED_MOVERS over time from:
  https://www.fidi.org/members/find-a-member
  https://www.iamovers.org/members/
No external calls — a missing accreditation is a false negative (safe), never a
false positive.
"""
import logging
from urllib.parse import urlparse

from ...config.vendor_discovery import ACCREDITATION_BY_CATEGORY

logger = logging.getLogger(__name__)

# domain (without www.) → list of accreditation tags
# FIDI = Fédération Internationale des Déménageurs Internationaux (global)
# IAM = International Association of Movers (global); BAR = British Association of Removers (UK)
KNOWN_ACCREDITED_MOVERS = {
    "crownrelo.com": ["FIDI", "IAM"],
    "graebel.com": ["FIDI", "IAM"],
    "agsglobal.com": ["FIDI", "IAM"],
    "interdean.com": ["FIDI"],
    "santaferelo.com": ["FIDI", "IAM"],
    "allied.com": ["IAM"],
    "arpin.com": ["IAM", "FIDI"],
    "bishopsmovers.co.uk": ["BAR", "FIDI"],
    "rainbowint.co.uk": ["BAR"],
    "brunel-expat.com": ["FIDI"],
    "demeco.fr": ["FIDI"],
    "bedaux.fr": ["FIDI"],
    "rhenus-relocation.de": ["FIDI"],
    "vdm-movers.com": ["FIDI"],
    "eggers-umzuege.de": ["FIDI"],
}


def _extract_domain(url: str) -> str:
    """Extract root domain from URL, stripping www."""
    if not url:
        return ""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def check_accreditation(vendor: dict, service_category: str) -> list:
    """Return the accreditation tags for this vendor, e.g. ['FIDI','IAM'], or []
    when the category has no accreditation bodies or the vendor isn't found."""
    if service_category not in ACCREDITATION_BY_CATEGORY:
        return []
    if service_category == "movers":
        lookup = KNOWN_ACCREDITED_MOVERS
    else:
        return []  # Future: housing accreditation lookup (ARLA, RICS, ...)

    # 1. Exact domain match
    domain = _extract_domain(vendor.get("website", ""))
    if domain and domain in lookup:
        tags = lookup[domain]
        logger.info("Accreditation (domain match): %s → %s", vendor.get("name"), tags)
        return tags

    # 2. Fuzzy name match (catches subdomain variants)
    vendor_name = (vendor.get("name") or "").lower()
    for known_domain, tags in lookup.items():
        known_name = known_domain.split(".")[0]
        if len(known_name) > 3 and (known_name in vendor_name or vendor_name.startswith(known_name)):
            logger.info("Accreditation (name match): %s ~ %s → %s", vendor.get("name"), known_domain, tags)
            return tags
    return []


def enrich_with_accreditation(vendors: list, service_category: str) -> list:
    """Add an accreditation_tags key to each vendor dict. Mutates in place."""
    for v in vendors:
        v["accreditation_tags"] = check_accreditation(v, service_category)
    return vendors
