"""[Stage 9 · Phase 0] Harvest FIDI affiliates for a country — real tier-1 origin supply.

WHY THIS EXISTS
---------------
Phase 0 asked for "≥3 FR-based movers approved with verified NO reach" and production had
**zero**. The four French movers in the directory came from the INSEE SIRENE import and are
tier 2 by construction — a SIREN plus NAF 49.42Z proves a company is registered in France, not
that it can move a household to Oslo. Addendum A line 34 says exactly this: *"a Paris mover
with no Nordic network cannot quote Paris→Oslo."*

FIDI is the right source, and it turned out to be enumerable after all. The earlier recon
recorded `fidi.org/find-mover` as 404 and marked the source MANUAL_EVIDENCED; that URL is dead,
but **`/find-fidi-affiliate?country=<id>`** is live and lists a country's affiliates with a
per-entity detail link each. France (`country=101`) returns 11.

WHAT A DETAIL PAGE GIVES US
---------------------------
Measured 2026-08-13 on `santa-fe-relocation-paris`:

  * the entity name in the page title — so the row is later machine-verifiable by the existing
    `scripts/harden_accreditations.py`, whose `fidi` policy matches on the body substring;
  * a postal address including the country — the only base-country signal available anywhere
    for these suppliers (`suppliers.incorporation_country` is 0 of 108 populated);
  * `FAIM Expiry date: <year>` — and `registry_sources.py` is explicit that FAIM expiry is
    meaningful because the certification is audited and renewed on a 3-year cycle.

WHAT THIS DOES NOT DO
---------------------
It stages `claimed` accreditations, like every other harvest. FIDI membership becomes
`verified` only when `harden_accreditations.py` fetches the affiliate page and finds the name —
a separate, evidenced step. Nothing here writes `verified`, and nothing here approves a
capability for employee display.
"""
from __future__ import annotations

import html
import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from backend.app.services.registry_sources import RegistrySource, sources_for
from backend.app.services.vendor_harvester import Candidate

log = logging.getLogger(__name__)

BASE = "https://www.fidi.org"
INDEX = BASE + "/find-fidi-affiliate?country={country_id}"
DETAIL = BASE + "/find-fidi-affiliate/{slug}"
SOURCE_NAME = "FIDI FAIM member directory"
CORRIDOR = "FR-NO"
CATEGORY = "movers"

#: FIDI's own country ids, read off the directory's country blocks. Only the ones we harvest
#: are listed — an id nobody has verified is worse than an absent one.
COUNTRY_IDS: Dict[str, int] = {"FR": 101}

#: Listing entries that are editorial, not affiliates.
_NOT_AFFILIATES = ("fraudulently", "top-performers")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 30


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — fixed https host
        return resp.read().decode("utf-8", errors="replace")


def _text(markup: str) -> str:
    x = re.sub(r"<script.*?</script>", " ", markup, flags=re.S)
    x = re.sub(r"<style.*?</style>", " ", x, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x)))


def list_slugs(country: str, *, fetcher: Callable[[str], str] = _fetch) -> List[str]:
    """Affiliate detail slugs for a country, in page order.

    Failure yields [] rather than raising: an empty list is reported as a finding by the
    caller, which is more useful than a traceback halfway through a run.
    """
    country_id = COUNTRY_IDS.get(country.upper())
    if country_id is None:
        raise LookupError(f"no verified FIDI country id for {country!r} — add one to COUNTRY_IDS")
    try:
        markup = fetcher(INDEX.format(country_id=country_id))
    except Exception as exc:
        log.warning("fidi: country listing %s failed: %s", country, exc)
        return []
    slugs = re.findall(r'href="/find-fidi-affiliate/([a-z0-9\-]+)"', markup)
    seen, out = set(), []
    for s in slugs:
        if s in seen or any(bad in s for bad in _NOT_AFFILIATES):
            continue
        seen.add(s)
        out.append(s)
    return out


@dataclass(frozen=True)
class Affiliate:
    slug: str
    name: str
    evidence_url: str
    faim_expiry: Optional[str] = None   # ISO date, 1 Jan of the published year
    address_country: Optional[str] = None
    faim_plus: bool = False


#: The page prints only a year ("FAIM Expiry date: 2029"). 1 Jan is the earliest date
#: consistent with it — the same coercion the 2026-08-11 harvest recorded in its notes.
_EXPIRY = re.compile(r"FAIM\s+Expiry\s+date:\s*(\d{4})", re.I)
_TITLE = re.compile(r"<title>([^<|]+)", re.I)


def parse_affiliate(slug: str, markup: str, *, country_hint: str = "") -> Optional[Affiliate]:
    """Pull the fields a Candidate needs out of one detail page."""
    title = _TITLE.search(markup)
    name = (title.group(1).strip() if title else "").strip()
    if not name:
        return None

    body = _text(markup)
    expiry = _EXPIRY.search(body)
    country = None
    if country_hint and re.search(rf"\b{re.escape(country_hint)}\b", body, re.I):
        country = country_hint

    return Affiliate(
        slug=slug,
        name=name,
        evidence_url=DETAIL.format(slug=slug),
        faim_expiry=f"{expiry.group(1)}-01-01" if expiry else None,
        address_country=country,
        # "FAIM Plus" is a distinct, higher certification. Only claim it when the page says so;
        # inventing it would overstate an audited credential.
        faim_plus=bool(re.search(r"FAIM\s*Plus", body, re.I)),
    )


def _source() -> RegistrySource:
    for src in sources_for(CORRIDOR, CATEGORY):
        if src.name == SOURCE_NAME:
            return src
    raise LookupError(f"{SOURCE_NAME} is not declared for ({CORRIDOR}, {CATEGORY})")


def body_for(aff: Affiliate) -> str:
    """Match the strings already in `supplier_accreditations` so dedupe on
    (supplier_id, body) recognises a supplier we already hold."""
    return (
        "FIDI Global Alliance / FAIM Plus (auditor: EY)"
        if aff.faim_plus
        else "FIDI Global Alliance / FAIM (auditor: EY)"
    )


def to_candidate(aff: Affiliate, *, country: str) -> Candidate:
    return Candidate(
        name=aff.name,
        website_url="",
        corridor=CORRIDOR,
        service_category=CATEGORY,
        source=_source(),
        accreditation_body=body_for(aff),
        accreditation_number=None,      # FIDI publishes no per-member number
        accreditation_expiry=aff.faim_expiry,
        source_url=aff.evidence_url,
        country_code=country.upper(),
        city=None,                      # a registered address is not a coverage claim
        notes=(
            f"FIDI affiliate directory, country listing {country.upper()}. "
            f"FAIM{' Plus' if aff.faim_plus else ''}"
            + (f", certificate expiry {aff.faim_expiry} (page publishes the year only; "
               f"coerced to 1 Jan)" if aff.faim_expiry else ", no expiry published")
            + ". Accreditation is CLAIMED until harden_accreditations.py confirms the name "
              "on this page."
        ),
    )


def harvest(
    country: str = "FR",
    *,
    limit: Optional[int] = None,
    fetcher: Callable[[str], str] = _fetch,
) -> Tuple[List[Candidate], List[str]]:
    """(candidates, problems) for one country's FIDI affiliates."""
    problems: List[str] = []
    slugs = list_slugs(country, fetcher=fetcher)
    if not slugs:
        problems.append(f"FIDI listed no affiliates for {country} — check the country id")
    cands: List[Candidate] = []
    for slug in slugs[: limit or len(slugs)]:
        try:
            markup = fetcher(DETAIL.format(slug=slug))
        except Exception as exc:
            problems.append(f"{slug}: fetch failed ({type(exc).__name__})")
            continue
        aff = parse_affiliate(slug, markup, country_hint=_COUNTRY_NAMES.get(country.upper(), ""))
        if aff is None:
            problems.append(f"{slug}: no name in the page title")
            continue
        cands.append(to_candidate(aff, country=country))
    return cands, problems


_COUNTRY_NAMES: Dict[str, str] = {"FR": "France"}
