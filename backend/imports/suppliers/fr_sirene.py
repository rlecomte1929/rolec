"""[AIQ-1827] Harvest Paris supplier candidates from the French open company register.

WHY THIS SOURCE AND NOT THE ONES THE BRIEF NAMED
------------------------------------------------
FR-NO's origin half had zero suppliers because all four anchors in the original brief are
unusable, measured 2026-08-12:

    CCI fichier national (carte T)          HTTP 403
    FIDI find-mover                         HTTP 404
    CNB annuaire des avocats de France      200, JS-only, no listable index
    Ordre des Experts-Comptables tableau    200, JS-only, no listable index

`recherche-entreprises.api.gouv.fr` (INSEE SIRENE + RNE) is free, unauthenticated, and
genuinely enumerable by NAF activity code and postcode. It answered for all four categories.

WHAT THIS EVIDENCE IS WORTH — READ BEFORE EXTENDING
---------------------------------------------------
**Tier 2. Entity confirmation, not professional accreditation.** SIRENE proves a company is
registered and what activity it *self-declared* at registration. It does NOT evidence bar
membership, a carte T, or a place on the Ordre's tableau.

Treating a NAF code as an accreditation would repeat the defect found in the Den Norske
Advokatforening rows, where a Brønnøysund organisation number sat under a bar's name and
looked like a confirmation. So rows from here:

  * carry `body = "INSEE SIRENE / recherche-entreprises (FR)"` — the register that actually
    answered, never a professional body's name;
  * land `status='claimed'` (enforced downstream by `executor._INSERT_ACCREDITATION`);
  * can never be auto-verified — `accreditation_hardening.BODY_POLICIES` has no entry for
    this body, so `decide()` keeps it `claimed` and says why.

WHY NO CITY IS WRITTEN
----------------------
A Paris postcode says where a firm is REGISTERED, not what it SERVES; a Paris-registered
mover may cover all of France. `city` is therefore left None and the capability lands
`coverage_scope_type='country'` with a NULL `city_name`, which is what that pair means
everywhere else in the table. The postcode is a *selection filter*, not a coverage claim.

Writing `city_name='Paris'` here would also manufacture the country-scope-with-a-city
inconsistency that already affects 4 NO rows — the same over-claim as the `city_name='Oslo'`
step this work declined.

SELECTION
---------
With >10,000 avocats in Paris, "the first three" is not curation. Candidates are filtered to
active establishments in Paris postcodes, deduped by SIREN, and ranked by INSEE headcount
band then number of open establishments — so the pool is substantial firms rather than
one-person shells. It is a POOL FOR HUMAN VETTING, not a recommendation: every capability
lands `pending` and an admin decides.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.app.services.registry_sources import RegistrySource, sources_for
from backend.app.services.vendor_harvester import Candidate

log = logging.getLogger(__name__)

API = "https://recherche-entreprises.api.gouv.fr/search"
ENTRY_URL = "https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"
SOURCE_NAME = "INSEE SIRENE / recherche-entreprises (FR)"
CORRIDOR = "FR-NO"

#: NAF (activité principale) codes, dotted — the API rejects the undotted form with a 400
#: listing every valid value.
NAF_BY_CATEGORY: Dict[str, str] = {
    "legal_admin": "69.10Z",      # Activités juridiques
    "movers": "49.42Z",           # Services de déménagement
    "housing_agencies": "68.31Z",  # Agences immobilières
    "tax_finance": "69.20Z",      # Activités comptables
}

#: Paris proper. Deliberately not `departement=75`: that parameter returned firms registered
#: in Courbevoie (92), Mitry-Mory (77) and Montbonnot-Saint-Martin (38).
PARIS_POSTCODES: Tuple[str, ...] = tuple(f"750{n:02d}" for n in range(1, 21))

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 25


def source_for(category: str) -> RegistrySource:
    """The catalogue entry for this harvest, so `validate()` sees the real tier."""
    for src in sources_for(CORRIDOR, category):
        if src.name == SOURCE_NAME:
            return src
    raise LookupError(
        f"{SOURCE_NAME} is not declared for ({CORRIDOR}, {category}) in registry_sources.py"
    )


def _fetch(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — fixed https API
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def search(
    category: str,
    postcode: str,
    *,
    per_page: int = 25,
    fetcher: Callable[[str], Dict[str, Any]] = _fetch,
) -> List[Dict[str, Any]]:
    """One page of active companies for a category in one Paris postcode.

    Network failure yields [] and a log line rather than an exception: one dead postcode
    must not abort a harvest that has already collected nineteen others.
    """
    params = urllib.parse.urlencode(
        {
            "activite_principale": NAF_BY_CATEGORY[category],
            "code_postal": postcode,
            "etat_administratif": "A",
            "per_page": per_page,
        }
    )
    try:
        payload = fetcher(f"{API}?{params}")
    except Exception as exc:
        log.warning("sirene: %s/%s failed: %s", category, postcode, exc)
        return []
    return list(payload.get("results") or [])


def _effectif_rank(value: Optional[str]) -> int:
    """INSEE headcount band as a sortable int. 'NN' (unknown) sorts last."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return -1


def _clean_name(result: Dict[str, Any]) -> str:
    return (result.get("nom_complet") or result.get("nom_raison_sociale") or "").strip()


def to_candidate(result: Dict[str, Any], category: str) -> Optional[Candidate]:
    """One API result -> a Candidate, or None when it lacks what a row needs."""
    siren = (result.get("siren") or "").strip()
    name = _clean_name(result)
    if not siren or not siren.isdigit() or len(siren) != 9 or not name:
        return None

    siege = result.get("siege") or {}
    return Candidate(
        name=name,
        website_url="",  # SIRENE publishes no website; dedupe falls back to the name key
        corridor=CORRIDOR,
        service_category=category,
        source=source_for(category),
        accreditation_body=SOURCE_NAME,
        accreditation_number=siren,
        source_url=ENTRY_URL.format(siren=siren),
        legal_name=(result.get("nom_raison_sociale") or "").strip() or None,
        country_code="FR",
        # Deliberately None — see the module docstring. A registration postcode is not a
        # coverage claim, and a city on a country-scoped capability contradicts itself.
        city=None,
        notes=(
            f"INSEE SIRENE: SIREN {siren}, NAF {result.get('activite_principale')}, "
            f"registered {siege.get('libelle_commune') or '?'} "
            f"{siege.get('code_postal') or ''}. Entity registration + self-declared "
            f"activity only — NOT a professional accreditation."
        ),
    )


def harvest(
    categories: Sequence[str],
    *,
    per_category: int = 5,
    postcodes: Iterable[str] = PARIS_POSTCODES,
    fetcher: Callable[[str], Dict[str, Any]] = _fetch,
) -> Dict[str, List[Candidate]]:
    """Candidates per category, deduped by SIREN and ranked so the pool is substantial firms.

    Returns a dict so the run report can state a count per category — including a category
    that yielded nothing, which is a finding rather than an empty line.
    """
    out: Dict[str, List[Candidate]] = {}
    for category in categories:
        by_siren: Dict[str, Dict[str, Any]] = {}
        for postcode in postcodes:
            for result in search(category, postcode, fetcher=fetcher):
                siren = (result.get("siren") or "").strip()
                if siren:
                    by_siren.setdefault(siren, result)

        ranked = sorted(
            by_siren.values(),
            key=lambda r: (
                _effectif_rank(r.get("tranche_effectif_salarie")),
                r.get("nombre_etablissements_ouverts") or 0,
                _clean_name(r),
            ),
            reverse=True,
        )
        cands = [c for c in (to_candidate(r, category) for r in ranked) if c is not None]
        out[category] = cands[:per_category]
    return out
