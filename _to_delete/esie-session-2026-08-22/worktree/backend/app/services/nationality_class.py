"""Nationality class for a (nationality, destination) pair.

The requirements engine had no nationality dimension, so a case's destination
alone selected the requirement set. `requirement_items` for FRANCE is the
non-EEA salaried route (VLS-TS / ANEF / DGEF) — its own seed file says so:
"EEA/EU nationals have free movement and need none of this." Without a way to
express that, the engine served a French citizen relocating home the full French
work-visa track. This module supplies the missing dimension.

Three classes:

  OWN_NATIONAL  — a national of the destination returning/moving home.
  EU_EEA        — free movement into the destination applies.
  THIRD_COUNTRY — no free movement; the visa/permit track applies.

`classify` returns ``None`` when either side is unrecognised. That is deliberate
and asymmetric: we suppress a requirement only when we POSITIVELY know free
movement applies. An unknown nationality keeps the full requirement list and
makes no claim in either direction — the failure mode we must never have is a
fabricated "nothing required".
"""
from __future__ import annotations

from typing import Optional, Sequence

from .requirements_country_key import to_iso

OWN_NATIONAL = "OWN_NATIONAL"
EU_EEA = "EU_EEA"
THIRD_COUNTRY = "THIRD_COUNTRY"

# EU-27.
_EU = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}

# EEA = EU + Iceland, Liechtenstein, Norway. Norway being EEA-but-NOT-EU is the
# trap this codebase keeps hitting (customs union, corridor content) — it is
# spelled out here rather than inferred.
_EEA = _EU | {"IS", "LI", "NO"}

# Switzerland is neither EU nor EEA, but Swiss nationals hold equivalent free
# movement under the EU–Swiss Agreement on the Free Movement of Persons (AFMP).
# Classifying CH as THIRD_COUNTRY would reproduce the exact bug this module
# exists to fix, so it is included in the free-movement set — by a different
# legal instrument, hence the separate constant.
_FREE_MOVEMENT = _EEA | {"CH"}

# Officially assigned ISO 3166-1 alpha-2 codes. This exists so that a two-letter
# input is only treated as a country when it IS one — see _nationality_to_iso.
_ISO_ALPHA2 = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM
BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX
CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG
GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR
IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV
LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE
NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO
RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF
TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF
WS YE YT ZA ZM ZW
""".split())

# Nationality is stored free-text and is often adjectival. `to_iso` already
# handles ISO codes, aliases and full country names; these cover the rest.
_ADJECTIVAL = {
    "FRENCH": "FR",
    "NORWEGIAN": "NO",
    "SWEDISH": "SE",
    "GERMAN": "DE",
    "DUTCH": "NL",
    "BRITISH": "GB",
    "AMERICAN": "US",
    "INDIAN": "IN",
    "SINGAPOREAN": "SG",
    "SWISS": "CH",
    # The EU/EEA set had only 6 free-movement adjectives, so an Austrian, Italian
    # or Irish citizen — every bit as entitled to free movement as a French one —
    # fell through to None and was served the full French work-visa track. That
    # fails safe (it over-shows), but it made the headline claim "EU citizens skip
    # the visa track" true for about a fifth of the EU.
    "AUSTRIAN": "AT", "BELGIAN": "BE", "BULGARIAN": "BG", "CROATIAN": "HR",
    "CYPRIOT": "CY", "CZECH": "CZ", "DANISH": "DK", "ESTONIAN": "EE",
    "FINNISH": "FI", "GREEK": "GR", "HUNGARIAN": "HU", "ICELANDIC": "IS",
    "IRISH": "IE", "ITALIAN": "IT", "LATVIAN": "LV", "LIECHTENSTEINER": "LI",
    "LITHUANIAN": "LT", "LUXEMBOURGISH": "LU", "MALTESE": "MT", "POLISH": "PL",
    "PORTUGUESE": "PT", "ROMANIAN": "RO", "SLOVAK": "SK", "SLOVENIAN": "SI",
    "SPANISH": "ES",
    # Kept in step with the country-name table above — every country needs both
    # forms, because production stores whichever the person typed.
    "HONG KONGER": "HK", "VENEZUELAN": "VE",
}

# Full country names for the free-movement set. `to_iso` only knows the seven
# seeded DESTINATIONS, so "Italy" or "Austria" resolved to None while the bare
# code "IT"/"AT" resolved fine — the gate worked or didn't depending on how the
# employee happened to type it.
_COUNTRY_NAME = {
    "AUSTRIA": "AT", "BELGIUM": "BE", "BULGARIA": "BG", "CROATIA": "HR",
    "CYPRUS": "CY", "CZECHIA": "CZ", "CZECH REPUBLIC": "CZ", "DENMARK": "DK",
    "ESTONIA": "EE", "FINLAND": "FI", "GREECE": "GR", "HUNGARY": "HU",
    "ICELAND": "IS", "IRELAND": "IE", "ITALY": "IT", "LATVIA": "LV",
    "LIECHTENSTEIN": "LI", "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MALTA": "MT",
    "POLAND": "PL", "PORTUGAL": "PT", "ROMANIA": "RO", "SLOVAKIA": "SK",
    "SLOVENIA": "SI", "SPAIN": "ES", "SWEDEN": "SE", "SWITZERLAND": "CH",
    # Non-EU/EEA names. This table began as the free-movement set, so every
    # country in it was a member state — and the adjectival table meanwhile grew
    # non-EU entries (INDIAN, AMERICAN, SINGAPOREAN, BRITISH). The two fell out of
    # step, and the gap was invisible because `to_iso` resolves seeded
    # DESTINATIONS by name: "Germany" and "France" worked as destinations while
    # "India" and "Hong Kong" — real nationalities we do not sell relocations TO —
    # returned None. Nationality ranges over every country; the destination
    # catalog does not, so it cannot be the fallback for this lookup.
    "GERMANY": "DE", "FRANCE": "FR", "NETHERLANDS": "NL", "NORWAY": "NO",
    "UNITED KINGDOM": "GB", "GREAT BRITAIN": "GB", "UK": "GB",
    "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US", "USA": "US",
    "INDIA": "IN", "SINGAPORE": "SG", "HONG KONG": "HK",
    # Named on AIQ-1993: Andrea, the first real ES->IE case, is Venezuelan.
    "VENEZUELA": "VE",
}


def _nationality_to_iso(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s in _ADJECTIVAL:
        return _ADJECTIVAL[s]
    if s in _COUNTRY_NAME:
        return _COUNTRY_NAME[s]
    iso = to_iso(s)
    if iso:
        return iso
    # `to_iso` only knows the seeded DESTINATIONS, but nationality ranges over
    # every country, so we accept a bare alpha-2 code — but ONLY a real one.
    #
    # This used to be `if len(s) == 2 and s.isalpha(): return s`, i.e. any two
    # letters became a country. `nationality` is an unvalidated free-text field
    # (production already holds 'f', 'gh', 'de', 'asdas', '1212'), and the
    # free-movement set contains 31 two-letter codes — so a single stray
    # keystroke landing on 'it', 'ie', 'pl', 'se', 'at', 'cz', 'fi' or 'dk'
    # resolved to an EU member and told the person "no visa or residence permit
    # required". A typo could fabricate a right of free movement. Now an
    # unrecognised code returns None, and None makes no claim.
    if s in _ISO_ALPHA2:
        return s
    return None


def classify(nationality: Optional[str], dest_country: Optional[str]) -> Optional[str]:
    """Classify a nationality against a destination.

    Returns OWN_NATIONAL, EU_EEA, THIRD_COUNTRY, or None when either side is
    unrecognised (caller must then not filter and not claim).
    """
    nat = _nationality_to_iso(nationality)
    dest = to_iso(dest_country)
    if not nat or not dest:
        return None
    if nat == dest:
        return OWN_NATIONAL
    # Free movement only buys you something when the destination is itself inside
    # the free-movement area. An EU passport is worth nothing at the US border.
    if dest in _EEA and nat in _FREE_MOVEMENT:
        return EU_EEA
    return THIRD_COUNTRY


#: Best-to-worst. A dual national holds the UNION of their rights, so when two
#: nationalities disagree the more favourable class is the true one.
_CLASS_RANK = {OWN_NATIONAL: 0, EU_EEA: 1, THIRD_COUNTRY: 2}


def classify_best(
    nationalities: Sequence[Optional[str]], dest_country: Optional[str]
) -> Optional[str]:
    """The most favourable class across every nationality a person holds.

    A dual national does not have to choose which passport to be judged by: rights
    are cumulative. A Venezuelan/Italian citizen moving to Ireland exercises Italian
    free movement, and classifying them on the Venezuelan nationality alone produces
    the exact opposite answer — a permit track they must not apply for, plus a
    "not enough lead time" verdict that is false because the 104-day permit chain
    does not apply to them at all.

    That is not hypothetical. Intake ASKS for a second nationality
    (`q_has_second_nationality` → `second_nationality`), stores it, and exports it
    under GDPR — and nothing consulted it at the gate, so whichever nationality
    happened to be captured first decided the whole journey.

    Returns ``None`` only when NO nationality could be recognised, preserving
    `classify`'s rule: suppress a requirement only when we positively know free
    movement applies. One unrecognised nationality alongside one recognised one
    yields the recognised answer rather than discarding it.
    """
    best: Optional[str] = None
    for nat in nationalities:
        got = classify(nat, dest_country)
        if got is None:
            continue
        if best is None or _CLASS_RANK[got] < _CLASS_RANK[best]:
            best = got
    return best


def is_free_movement_national(nationality: Optional[str]) -> bool:
    """True when this nationality is from the EU/EEA/CH free-movement area.

    Destination-independent on purpose: callers pair it with their own
    destination check (`immigration_regime._is_eu_destination`). Use `classify`
    when you need the full three-way answer for a (nationality, destination) pair.

    This exists so there is exactly ONE answer to "does this person have free
    movement?" in the product. `immigration_regime` and `family_propagation` each
    grew their own EU set built from country names and ISO codes ("france", "fr")
    with no adjectival forms — and adjectival is what production actually stores.
    So `classify("French", "FRANCE")` said OWN_NATIONAL (no visa required) while
    their `_is_eu_national("French")` said False (build a permit journey). The same
    citizen was told two different things by two different screens. Delegating to
    this function also buys those callers the ISO-3166 whitelist (junk cannot
    become a country), the adjectival/country-name tables, and Swiss AFMP handling.
    """
    iso = _nationality_to_iso(nationality)
    return bool(iso and iso in _FREE_MOVEMENT)
