"""[AIQ-1821] Destination-country normalisation — one table, two consumers.

Cases do not consistently store ISO-2. Measured on prod 2026-08-12, **426 of 1389
wizard_cases store a country name** ("Germany", "Norway", "France") rather than
"DE"/"NO"/"FR", and some store a city.

That matters because several lookups match `destination_country` EXACTLY —
`list_dossier_questions`, and `list_approved_requirement_facts` via its join on
`requirement_entities.destination_country`. An un-normalised "Norway" returns zero rows
from both, and the sufficiency endpoint then reports `compute_status: "ok"` with empty
results, which reads to the employee as "nothing is required of you".

This lived in backend/main.py, where `requirements_sufficiency` could only reach it by
importing the monolith at call time — which drags the whole app in (and breaks under the
test suite's mocked engine). It is a pure function with no dependencies, so it lives here
and `backend/main.py` re-exports it for its existing callers.
"""
from __future__ import annotations

from typing import Optional


def normalize_destination_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    if normalized in ("SG", "SINGAPORE"):
        return "SG"
    if normalized in ("US", "USA", "UNITED STATES", "NEW YORK", "NEW YORK CITY", "NYC"):
        return "US"
    if normalized in ("GB", "UK", "UNITED KINGDOM", "LONDON", "ENGLAND"):
        return "GB"
    if normalized in ("FR", "FRANCE", "PARIS"):
        return "FR"
    if normalized in ("DE", "GERMANY", "DEUTSCHLAND", "BERLIN", "MUNICH", "MÜNCHEN"):
        return "DE"
    if normalized in ("NO", "NORWAY", "NORGE", "OSLO"):
        return "NO"
    if normalized in ("BR", "BRAZIL", "BRASIL", "RIO DE JANEIRO", "RIO", "SÃO PAULO", "SAO PAULO"):
        return "BR"
    if normalized in ("IT", "ITALY", "ITALIA", "ROME", "ROMA", "MILAN", "MILANO"):
        return "IT"
    if normalized in ("ES", "SPAIN", "ESPAÑA", "ESPANA", "MADRID", "BARCELONA"):
        return "ES"
    if normalized in ("AU", "AUSTRALIA", "SYDNEY", "MELBOURNE", "BRISBANE", "PERTH",
                      "ADELAIDE", "CANBERRA", "GOLD COAST", "NEWCASTLE", "SUNSHINE COAST", "WOLLONGONG"):
        return "AU"
    if normalized in ("CA", "CANADA", "TORONTO", "VANCOUVER", "MONTREAL", "CALGARY",
                      "EDMONTON", "OTTAWA", "WINNIPEG", "HAMILTON", "KITCHENER", "QUEBEC CITY"):
        return "CA"
    if normalized in ("CH", "SWITZERLAND", "SCHWEIZ", "SUISSE", "ZURICH", "ZÜRICH",
                      "GENEVA", "GENÈVE", "GENEVE", "BERN", "BERNE", "BASEL", "BIEL",
                      "LAUSANNE", "LUCERNE", "LUGANO", "ST. GALLEN", "ST GALLEN", "WINTERTHUR"):
        return "CH"
    if normalized in ("HK", "HONG KONG", "KOWLOON", "NEW TERRITORIES"):
        return "HK"
    if normalized in ("JP", "JAPAN", "TOKYO", "OSAKA", "FUKUOKA", "NAGOYA", "SAPPORO",
                      "KAWASAKI", "KOBE", "KYOTO", "SAITAMA", "YOKOHAMA"):
        return "JP"
    if normalized in ("NL", "NETHERLANDS", "NEDERLAND", "AMSTERDAM", "ROTTERDAM",
                      "THE HAGUE", "DEN HAAG", "UTRECHT", "EINDHOVEN", "GRONINGEN",
                      "ALMERE", "BREDA", "NIJMEGEN", "TILBURG"):
        return "NL"
    if normalized in ("AE", "UAE", "UNITED ARAB EMIRATES", "DUBAI", "ABU DHABI",
                      "SHARJAH", "AJMAN", "FUJAIRAH", "RAS AL KHAIMAH", "UMM AL QUWAIN"):
        return "AE"
    if normalized in ("ZA", "SOUTH AFRICA", "JOHANNESBURG", "CAPE TOWN", "DURBAN",
                      "PRETORIA", "BLOEMFONTEIN", "PORT ELIZABETH", "EAST LONDON", "PIETERMARITZBURG"):
        return "ZA"
    return None

