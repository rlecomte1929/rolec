"""Single source of truth for country/corridor key resolution across the two
requirements engines (AIQ-1473b).

Background: the two requirements paths keyed countries differently, which let a
case silently miss all its requirements (AIQ-1349):

  * Path A — immigration_requirement_service — keys immigration_requirements by
    ISO corridor codes ("FR", "DE").
  * Path B — requirements_builder — keys requirement_items by the catalog's FULL
    UPPERCASE country name ("GERMANY"), resolved from a case's ISO destination.

AIQ-1473a chose **ISO alpha-2 UPPERCASE** as the single canonical internal key.
This module owns that mapping so neither path carries its own private copy.

`to_iso` returns ``None`` for an unrecognised value on purpose: it lets callers
fail closed (surface "not covered") instead of querying with a bad key and
getting an empty result that reads as "nothing required" — the 1473c follow-up.

Two functions, two different questions — do not conflate them:

  * ``to_iso``        — "do we have requirement CATALOG data for this country?"
                        Narrow by design. ``to_iso("Japan") is None`` is asserted by
                        test_requirements_country_key.py, and requirements_builder.py:152
                        uses it as a coverage gate. Widening it would make an uncovered
                        destination silently claim coverage.
  * ``to_iso_alpha2`` — "what is this country's ISO 3166-1 alpha-2 code?"
                        Broad. Says nothing about catalog coverage. Use this when the job
                        is to STORE a canonical country code.

[AIQ-1778] ``to_iso_alpha2`` exists because `public.cases.origin_country_code` accumulated
full country names — 22 rows of 'France', plus 'Germany', 'India' and one empty string. The
column is plain `text` with no CHECK, and the readers are unforgiving: trigger_engine's EEA
gate is exact ISO-2 set membership, so a case reading 'France' resolves visa_type
'skilled_worker' instead of 'eea_registration' and is handed EU Blue Card paperwork.
"""
from __future__ import annotations

from typing import Dict, Optional

# Canonical ISO alpha-2 (UPPERCASE) → requirement catalog country_code
# (FULL UPPERCASE name). The one place this mapping lives.
_ISO_TO_CATALOG_NAME = {
    "DE": "GERMANY",
    "NO": "NORWAY",
    "SG": "SINGAPORE",
    "GB": "UNITED KINGDOM",
    "US": "UNITED STATES",
    "FR": "FRANCE",
    "NL": "NETHERLANDS",
    "IE": "IRELAND",
    # Destinations of committed corridor profiles. Each was missing while its corridor
    # existed, and a missing entry is silent: `resolve_catalog_country` falls back to the
    # raw ISO code, which matches no `requirement_items` row and serves nobody.
    #
    # ES cost the IE→ES batch exactly that — 25 source-verified records applied to
    # production, reachable by no case, because destinations are stored as ISO alpha-2 and
    # "ES" never became "SPAIN". FR_ES targets it too.
    "ES": "SPAIN",
    # CH is a destination of FR_CH. `nationality_class` already models Swiss free movement
    # under the EU–Swiss AFMP, so the codebase treated CH as first-class everywhere but here.
    "CH": "SWITZERLAND",
    # DK is not a corridor profile yet, but the B3 batch stages six Denmark-destination
    # facts and `mappings.resolve()` refuses an entity whose destination has no coverage.
    "DK": "DENMARK",
    # EC is the destination of US_EC (Seattle→Quito, Abraham). Ecuador is a brand-new
    # destination: without this entry US→EC facts stage but `mappings.resolve()` refuses
    # to promote them (no catalog coverage), so they would reach no case. Ships together
    # with corridors/US_EC/corridor.yaml — `test_every_corridor_destination_resolves`
    # fails the moment the profile lands without this row.
    "EC": "ECUADOR",
    # CA is a Destination Coverage Master destination (rank 5, Toronto hub). No corridor
    # profile — authored as a destination like GB above. Without this entry Canada facts stage
    # but `mappings.resolve()` refuses to promote them (no catalog coverage), reaching no case.
    "CA": "CANADA",
    # AU — Destination Coverage Master rank 6 (Sydney hub). Destination-only, like GB/CA.
    "AU": "AUSTRALIA",
    # AE — Destination Coverage Master rank 8 (Dubai hub). Destination-only; non-EEA.
    "AE": "UNITED ARAB EMIRATES",
    # IT — Destination Coverage Master rank 11 (Milan hub). EEA destination, dual-audience facts.
    "IT": "ITALY",
    # SE — Destination Coverage Master rank 14 (Stockholm hub). EEA destination.
    "SE": "SWEDEN",
    # BE — rank 15 (Brussels hub). EEA destination. AT — rank 16 (Vienna hub). EEA destination.
    "BE": "BELGIUM",
    "AT": "AUSTRIA",
    # Tier-3 Destination Coverage Master destinations (no prior corridor data). Destination-only,
    # authored like GB/CA above; all served on the third-country-national (non-EEA) professional
    # relocation pathway. SA rank 12 (Riyadh), JP rank 18 (Tokyo), PT rank 24 (Lisbon; EEA dest,
    # non-EEA audience), FI rank 26 (Helsinki; EEA dest, non-EEA audience).
    "SA": "SAUDI ARABIA",
    "JP": "JAPAN",
    "PT": "PORTUGAL",
    "FI": "FINLAND",
    # Tier-3 wave 2 — HK rank 21 (Hong Kong), NZ rank 22 (Auckland), QA rank 23 (Doha),
    # PL rank 25 (Warsaw). Destination-only, third-country-national pathway.
    "HK": "HONG KONG",
    "NZ": "NEW ZEALAND",
    "QA": "QATAR",
    "PL": "POLAND",
    # Tier-3 wave 3 — KR rank 27 (Seoul), IL rank 28 (Tel Aviv), KW rank 29 (Kuwait City),
    # LU rank 30 (Luxembourg City). Destination-only, third-country-national pathway.
    "KR": "SOUTH KOREA",
    "IL": "ISRAEL",
    "KW": "KUWAIT",
    "LU": "LUXEMBOURG",
    # Tier-3 wave 4 — CZ rank 31 (Prague), GR rank 32 (Athens), MX rank 33 (Mexico City),
    # BR rank 34 (São Paulo). Destination-only, third-country-national pathway.
    "CZ": "CZECH REPUBLIC",
    "GR": "GREECE",
    "MX": "MEXICO",
    "BR": "BRAZIL",
    # Tier-3 wave 5 — BH rank 35 (Manama), OM rank 36 (Muscat), ZA rank 37 (Johannesburg),
    # MY rank 38 (Kuala Lumpur). Destination-only, third-country-national pathway.
    "BH": "BAHRAIN",
    "OM": "OMAN",
    "ZA": "SOUTH AFRICA",
    "MY": "MALAYSIA",
    # Tier-3 wave 6 — TH rank 39 (Bangkok), CN rank 40 (Shanghai), IN rank 41 (Bengaluru),
    # TR rank 42 (Istanbul). Destination-only, third-country-national pathway.
    "TH": "THAILAND",
    "CN": "CHINA",
    "IN": "INDIA",
    "TR": "TURKEY",
    # Tier-3 wave 7 — HU rank 43 (Budapest), RO rank 44 (Bucharest), AR rank 45 (Buenos Aires),
    # CL rank 46 (Santiago). Destination-only, third-country-national pathway.
    "HU": "HUNGARY",
    "RO": "ROMANIA",
    "AR": "ARGENTINA",
    "CL": "CHILE",
    # Tier-3 wave 8 — EE rank 47 (Tallinn), CY rank 48 (Nicosia), IS rank 49 (Reykjavik),
    # MT rank 50 (Valletta). Destination-only, third-country-national pathway.
    "EE": "ESTONIA",
    "CY": "CYPRUS",
    "IS": "ICELAND",
    "MT": "MALTA",
    # Tier-3 wave 9 — Asia-Pacific tail, coverage-master ranks 53-56 (Taipei, Ho Chi Minh
    # City, Jakarta, Manila). Ranks 51-52 (Russia, Ukraine) deliberately skipped: sanctions /
    # active conflict make corporate relocation there a non-starter for the customer base.
    "TW": "TAIWAN",
    "VN": "VIETNAM",
    "ID": "INDONESIA",
    "PH": "PHILIPPINES",
    # Tier-3 wave 10 — Latin America cluster, coverage-master ranks 57-61 (Bogotá, Lima,
    # Montevideo, San José, Panama City). Third-country-national pathway.
    "CO": "COLOMBIA",
    "PE": "PERU",
    "UY": "URUGUAY",
    "CR": "COSTA RICA",
    "PA": "PANAMA",
}

# Non-standard inputs seen in the data that map onto a canonical ISO code.
_ISO_ALIASES = {
    "UK": "GB",
    "USA": "US",
}

# Reverse lookup: catalog full name → ISO. Derived so there is no second map to
# keep in sync.
_CATALOG_NAME_TO_ISO = {name: iso for iso, name in _ISO_TO_CATALOG_NAME.items()}


def to_iso(raw: Optional[str]) -> Optional[str]:
    """Resolve a country value to the canonical ISO alpha-2 UPPERCASE key.

    Accepts an ISO code ("SG"), a known alias ("UK", "USA"), or a full country
    name in any case ("Singapore"). Returns ``None`` when the value is empty or
    unrecognised, so callers can fail closed rather than look up a bad key.
    """
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s in _ISO_ALIASES:
        return _ISO_ALIASES[s]
    if s in _ISO_TO_CATALOG_NAME:
        return s
    if s in _CATALOG_NAME_TO_ISO:
        return _CATALOG_NAME_TO_ISO[s]
    return None


def iso_to_catalog_name(iso: Optional[str]) -> Optional[str]:
    """ISO alpha-2 → the requirement_items.country_code FULL-NAME convention.

    Returns ``None`` for an unknown/empty ISO code.
    """
    if not iso:
        return None
    return _ISO_TO_CATALOG_NAME.get(iso.strip().upper())


def resolve_catalog_country(dest: Optional[str]) -> str:
    """Resolve a case destination (ISO code or name) to the requirement catalog's
    country_code naming (FULL UPPERCASE name).

    Behaviour-preserving replacement for the former private
    ``requirements_builder._resolve_catalog_country``: a value we have catalog
    data for resolves to its full name; anything else falls back to the raw value
    upper-cased (no catalog rows exist for it yet anyway); empty → ``"UNKNOWN"``.
    """
    iso = to_iso(dest)
    if iso:
        name = iso_to_catalog_name(iso)
        if name:
            return name
    if not dest or not dest.strip():
        return "UNKNOWN"
    return dest.strip().upper()


def normalize_corridor_code(raw: Optional[str]) -> str:
    """Normalise a corridor code to the canonical UPPERCASE form used to key
    immigration_requirements (Path A). Single seam for corridor keying."""
    if not raw:
        return ""
    return raw.strip().upper()


# ─────────────────────────────────────────────────────────────────────────────
# [AIQ-1778] General country-name → ISO 3166-1 alpha-2 resolution.
#
# Deliberately NOT merged into _ISO_TO_CATALOG_NAME above: that map answers
# "have we got catalog data?" and must stay narrow. This one answers "what is the
# ISO code?" and wants to be broad.
#
# Lifted from ops_analytics_service._COUNTRY_NAME_TO_ISO2, which had the widest
# coverage of the five country maps already in the tree. That copy still exists;
# collapsing the remaining four onto this one is follow-up work, not this fix.
# ─────────────────────────────────────────────────────────────────────────────

_NAME_TO_ISO2: Dict[str, str] = {
    # Europe
    "norway": "NO", "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB",
    "ireland": "IE", "belgium": "BE", "luxembourg": "LU",
    "switzerland": "CH", "austria": "AT", "denmark": "DK", "sweden": "SE",
    "finland": "FI", "iceland": "IS", "poland": "PL", "portugal": "PT",
    "greece": "GR", "czech republic": "CZ", "czechia": "CZ", "slovakia": "SK",
    "hungary": "HU", "romania": "RO", "bulgaria": "BG", "croatia": "HR",
    "slovenia": "SI", "estonia": "EE", "latvia": "LV", "lithuania": "LT",
    "ukraine": "UA", "turkey": "TR", "türkiye": "TR", "russia": "RU",
    "cyprus": "CY", "malta": "MT", "serbia": "RS", "liechtenstein": "LI",
    "monaco": "MC",
    # Localised spellings of the corridors we actually run — an HR user typing in
    # their own language is exactly how 'France' got into the column.
    "frankreich": "FR", "allemagne": "DE", "deutschland": "DE",
    "norwegen": "NO", "norvège": "NO", "norge": "NO",
    "pays-bas": "NL", "espagne": "ES", "italie": "IT", "autriche": "AT",
    "belgique": "BE", "suisse": "CH", "danemark": "DK", "suède": "SE",
    "royaume-uni": "GB", "irlande": "IE",
    # Americas
    "united states": "US", "united states of america": "US", "usa": "US",
    "u.s.": "US", "u.s.a.": "US", "america": "US", "états-unis": "US",
    "canada": "CA", "mexico": "MX", "brazil": "BR", "brésil": "BR",
    "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE",
    "uruguay": "UY", "costa rica": "CR", "panama": "PA", "ecuador": "EC",
    # Asia / Pacific
    "japan": "JP", "china": "CN", "south korea": "KR", "korea": "KR",
    "republic of korea": "KR", "north korea": "KP", "india": "IN", "inde": "IN",
    "pakistan": "PK", "bangladesh": "BD", "sri lanka": "LK", "singapore": "SG",
    "singapour": "SG", "malaysia": "MY", "indonesia": "ID", "thailand": "TH",
    "vietnam": "VN", "philippines": "PH", "hong kong": "HK", "taiwan": "TW",
    "australia": "AU", "new zealand": "NZ", "israel": "IL",
    "saudi arabia": "SA", "uae": "AE", "united arab emirates": "AE",
    "qatar": "QA", "kuwait": "KW", "bahrain": "BH", "oman": "OM",
    "jordan": "JO", "lebanon": "LB", "egypt": "EG",
    # Africa
    "south africa": "ZA", "morocco": "MA", "maroc": "MA", "tunisia": "TN",
    "tunisie": "TN", "kenya": "KE", "nigeria": "NG", "ghana": "GH",
    "ethiopia": "ET",
}

# Alpha-3 → alpha-2 for the codes we actually see. Not the full ISO table.
_ALPHA3_TO_ISO2: Dict[str, str] = {
    "deu": "DE", "fra": "FR", "esp": "ES", "ita": "IT", "gbr": "GB",
    "usa": "US", "can": "CA", "mex": "MX", "bra": "BR", "ecu": "EC", "nor": "NO",
    "swe": "SE", "fin": "FI", "dnk": "DK", "nld": "NL", "che": "CH",
    "aut": "AT", "bel": "BE", "irl": "IE", "prt": "PT", "pol": "PL",
    "jpn": "JP", "chn": "CN", "kor": "KR", "ind": "IN", "sgp": "SG",
    "aus": "AU", "nzl": "NZ", "are": "AE", "sau": "SA", "zaf": "ZA",
}


def to_iso_alpha2(raw: Optional[str]) -> Optional[str]:
    """Coerce any country spelling to an ISO 3166-1 alpha-2 code, or ``None``.

    Accepts a 2-letter code in any case, a full name in any case or a known
    localisation, or a common alpha-3 code. Returns ``None`` only when the value is
    empty or genuinely unresolvable.

    A well-formed 2-letter code passes straight through, uppercased, even if it is
    not a country we know — 'MC' must not be rejected just because our name map is
    incomplete, and the DB CHECK this feeds is a SHAPE check (``^[A-Z]{2}$``), not a
    membership check. ``None`` is reserved for input that is not a country code at
    all, which is the case worth failing closed on: storing 'Frankreich' is the bug.

    This says NOTHING about whether we hold requirement data for the country —
    that is ``to_iso``.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    lower = s.lower()
    # Name/alias map FIRST, before the 2-letter passthrough. Order matters: 'UK' is a
    # 2-letter alpha string but is NOT an ISO 3166-1 alpha-2 code — GB is. Passing it
    # through on shape alone would store an invalid code that satisfies a `^[A-Z]{2}$`
    # CHECK while matching nothing. (ops_analytics_service._normalize_country_to_iso2
    # checks length first and so still has this bug; it renders 'UK' to flagcdn.)
    if lower in _NAME_TO_ISO2:
        return _NAME_TO_ISO2[lower]
    if len(s) == 2 and s.isalpha():
        return s.upper()
    if len(s) == 3 and lower in _ALPHA3_TO_ISO2:
        return _ALPHA3_TO_ISO2[lower]
    return None
