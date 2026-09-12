"""[AIQ-1788] Read a harvest CSV into `vendor_harvester.Candidate` objects.

The harvester (`backend/app/services/vendor_harvester.py`) validates, dedupes, classifies and
shapes rows for `vendor_candidates`. It was merged with no way to feed it anything — no reader,
no caller. This is the reader.

Two decisions live here rather than in the harvester, because both are properties of *this
file format*, not of the staging model:

**The registry is identified by the evidence URL's domain, not by `source_name`.**
`source_name` is free text an agent wrote ("BaFin institute database / regulatory
self-classification", "Firm Impressum (RAK Berlin stated)"), and a row that cites the
provider's own Impressum can describe itself using a chamber's name. The domain cannot lie
about who published the page. So `db.com` maps to the tier-3 self-declared source and gets
rejected, whatever its `source_name` claims.

**A bare-year expiry is coerced to 1 January, never 31 December.**
Both are guesses. Only one fails safe: December would claim up to twelve months of validity we
cannot evidence, on precisely the field a buyer's security review checks. See `coerce_expiry`.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlsplit

from backend.app.services.registry_sources import SOURCES, RegistrySource
from backend.app.services.requirements_country_key import to_iso_alpha2
from backend.app.services.vendor_harvester import Candidate

#: The nine columns Card C's harvest actually produced.
EXPECTED_HEADER = [
    "corridor", "service_category", "company_name", "website_url", "source_name",
    "source_url", "accreditation_body", "accreditation_number", "accreditation_expiry",
]

_BY_NAME: Dict[str, RegistrySource] = {s.name: s for s in SOURCES}

SELF_DECLARED = "Self-declared (provider site / non-registry reference)"

#: Evidence domain -> registry source name. Suffix-matched, longest first, so a subdomain like
#: `kontenvergleich.bafin.de` resolves without listing every host.
_DOMAIN_TO_SOURCE: Tuple[Tuple[str, str], ...] = (
    ("fidi.org",              "FIDI FAIM member directory"),
    ("iamovers.org",          "IAM member directory"),
    ("finanstilsynet.no",     "Finanstilsynet — estate agency register (NO)"),
    ("bafin.de",              "BaFin institute register (DE)"),
    ("advokatforeningen.no",  "Advokatforeningen + Brønnøysund register (NO)"),
    ("brreg.no",              "Brønnøysund Enhetsregisteret (NO)"),
    ("eura-relocation.com",   "EuRA member directory"),
    # NOTE: blkr-berlin.de was listed here as the "Rechtsanwaltskammer (RAK)" until 2026-08-12.
    # It is the LAW FIRM'S OWN WEBSITE (BLKR Rechtsanwält*innen, Berlin — verified by fetching
    # it), so the one row citing it passed as tier-1 registry evidence on the strength of its
    # own homepage. Its source_name in the harvest CSV is literally
    # "Firm Impressum (RAK Berlin stated)" — the exact shape the docstring above says must not
    # be trusted. Do not re-add a provider domain here; that is what SELF_DECLARED is for.
    ("rechtsanwaltsregister.org", "Rechtsanwaltskammer (RAK) + Partnerschaftsregister (DE)"),
    ("bstbk.de",              "Bundessteuerberaterkammer / regional StBK (DE)"),
    ("hamburg.de",            "Official public business register (DE)"),
    # Ireland (ES-IE / Dublin) — statutory registers with no per-entity URL, admitted as
    # PUBLIC_REGISTER (tier 2, staged `claimed`). `centralbank.ie` suffix also catches
    # `registers.centralbank.ie`, which is where the bank rows actually cite.
    ("lawsociety.ie",         "Law Society of Ireland — Find a Solicitor"),
    ("cpaireland.ie",         "CPA Ireland — firm directory"),
    ("centralbank.ie",        "Central Bank of Ireland — Register of Authorised Firms"),
    ("tusla.ie",              "Tusla — Register of Independent Schools"),
    ("psr.ie",                "PSRA — Register of Licensed Property Services Providers"),
    # [ANDREA-P1] Dublin settle-in registers (journey-completion batches 2026-09-10).
    ("discoverireland.ie",    "Fáilte Ireland — Discover Ireland approved accommodation"),
    ("failteireland.ie",      "Fáilte Ireland — Discover Ireland approved accommodation"),
    ("hse.ie",                "HSE — Find a GP"),
    ("trustedireland.ie",     "TrustEd Ireland — QQI-authorised English language providers"),
    ("qqi.ie",                "TrustEd Ireland — QQI-authorised English language providers"),
    # France / Paris (NO-FR) — most expose per-entity pages; Barreau is PUBLIC_REGISTER.
    ("regafi.fr",                     "REGAFI — registre des agents financiers (ACPR / Banque de France)"),
    ("annuaire-education.fr",         "Annuaire de l'Éducation nationale (annuaire-education.fr)"),
    ("annuaire.experts-comptables.org", "Ordre des Experts-Comptables — annuaire"),
    ("fnaim.fr",                      "FNAIM — annuaire des adhérents (Paris)"),
    ("csdemenagement.fr",             "Chambre Syndicale du Déménagement (CSD) — annuaire adhérents"),
    ("avocatparis.org",               "Barreau de Paris — annuaire des avocats"),
    # Singapore (FR-SG) — MAS exposes per-entity pages; the rest are PUBLIC_REGISTER SPAs.
    ("mas.gov.sg",                    "MAS Financial Institutions Directory"),
    ("cea.gov.sg",                    "CEA Public Register (ACEAS)"),
    ("lawsociety.org.sg",             "Law Society of Singapore — Find a Lawyer"),
    ("acra.gov.sg",                   "ACRA Company Register"),
    ("moe.gov.sg",                    "MOE International Schools List"),
    # Ecuador (US-EC) — CAINEC exposes per-entity ficha.php records; other EC registers are blocked.
    ("cainec.com",                    "CAINEC — Great Place Inmobiliario"),
    # United Kingdom (XX-GB / London) — statutory/professional registers with per-entity URLs.
    # movers stay on fidi.org above. `find.icaew.com`, `register.fca.org.uk` and
    # `get-information-schools.service.gov.uk` are matched by suffix.
    ("sra.org.uk",                    "SRA — Solicitors Regulation Authority register"),
    ("icaew.com",                     "ICAEW — Find a Chartered Accountant"),
    ("fca.org.uk",                    "FCA Financial Services Register"),
    ("get-information-schools.service.gov.uk", "GIAS — Get Information About Schools (DfE)"),
    ("propertymark.co.uk",            "ARLA Propertymark — member directory"),
    # Canada (XX-CA / Toronto) — movers stay on fidi.org; the rest are search-form/flat registers
    # (PUBLIC_REGISTER). `data.ontario.ca` and `reco.on.ca` are matched by suffix.
    ("lso.ca",                        "LSO — Law Society of Ontario directory"),
    ("cpaontario.ca",                 "CPA Ontario — firm directory"),
    ("cdic.ca",                       "CDIC — member institutions list"),
    ("data.ontario.ca",              "Ontario Ministry of Education — Private School Location List"),
    ("reco.on.ca",                    "RECO — Real Estate Council of Ontario registrant search"),
    # Australia (XX-AU / Sydney) — movers stay on fidi.org; the rest are search-form/flat registers.
    # `verify.licence.nsw.gov.au` is listed BEFORE `nsw.gov.au` and wins by longest-suffix match, so
    # NSW property-agent URLs resolve to Fair Trading and the NESA schools page to NESA.
    ("mara.gov.au",                   "OMARA — Register of Migration Agents"),
    ("tpb.gov.au",                    "TPB — Tax Practitioners Board register"),
    ("apra.gov.au",                   "APRA — Register of authorised ADIs"),
    ("verify.licence.nsw.gov.au",     "NSW Fair Trading — property agents register"),
    ("nsw.gov.au",                    "NESA — Approved NSW school providers (CRICOS)"),
    # Amsterdam (XX-NL) + Dubai (XX-AE) + shared IB schools — Otto batch 2026-08-31. Only the real
    # statutory/professional registers are mapped; law-firm sites, the Spanish tax agency (mis-cited
    # for banks), Dubai Land Dept (mis-cited for tax) and aggregator sites stay unmapped -> rejected.
    ("dnb.nl",                        "DNB — De Nederlandsche Bank register"),
    ("advocatenorde.nl",              "NOvA — Dutch Bar find-a-lawyer register"),
    ("afm.nl",                        "AFM — Autoriteit Financiële Markten register"),
    ("mva.nl",                        "MVA — Makelaarsvereniging Amsterdam members"),
    ("centralbank.ae",               "CBUAE — Central Bank of the UAE register"),
    ("khda.gov.ae",                   "KHDA — Dubai schools directory"),
    ("ibo.org",                       "IBO — IB World Schools directory"),
    # Zurich (XX-CH) — Otto batch 2026-08-31 (movers reuse fidi.org; SE schools reuse ibo.org).
    ("finma.ch",                      "FINMA — Swiss financial-market authority register"),
    ("sgischools.com",               "SGIS — Swiss Group of International Schools members"),
    # Brussels (XX-BE) + Vienna (XX-AT) + Copenhagen (XX-DK) — Otto/subagent batch 2026-08-31.
    ("nbb.be",                        "NBB — National Bank of Belgium credit-institutions list"),
    ("biv.be",                        "BIV/IPI — Belgian real-estate agents register"),
    ("fma.gv.at",                     "FMA — Austrian Financial Market Authority company database"),
    ("wko.at",                        "WKO — Austrian real-estate agents register"),
    ("finanstilsynet.dk",            "Finanstilsynet — Danish FSA company register"),
    ("de.dk",                         "MDE — Dansk Ejendomsmæglerforening members"),
    ("advokatnoeglen.dk",            "Advokatsamfundet — Advokatnøglen (Danish bar)"),
    ("fsr.dk",                        "FSR — danske revisorer member directory"),
    # Tier-3 hub cities: Riyadh (XX-SA) + Helsinki (XX-FI) + Lisbon (XX-PT), subagent batch 2026-08-31.
    ("sama.gov.sa",                  "SAMA — Saudi Central Bank licensed local banks"),
    ("sba.gov.sa",                   "Saudi Bar Association — legal firms directory"),
    ("bankingsupervision.europa.eu", "ECB Banking Supervision — supervised entities (SSM)"),
    ("prh.fi",                        "PRH — Finnish auditor register (Tilintarkastajahaku)"),
    ("findanattorney.fi",            "Finnish Bar Association — Find an Attorney"),
    ("eba.europa.eu",                "EBA Credit Institutions Register (Portugal)"),
    ("impic.pt",                      "IMPIC — Portuguese estate-agent (AMI) register"),
    ("oroc.pt",                       "OROC — Portuguese statutory auditors (SROC) register"),
    # Tokyo (XX-JP) — subagent batch 2026-08-31.
    ("fsa.go.jp",                     "FSA — Japan licensed financial institutions list"),
    ("mlit.go.jp",                    "MLIT — Japan real-estate broker (Takken) licence search"),
    ("zeirishikensaku.jp",           "Nichizeiren — Japan certified tax accountant (zeirishi) register"),
    # Hong Kong (XX-HK) — subagent batch 2026-08-31.
    ("hkma.gov.hk",                   "HKMA — register of authorized institutions (Hong Kong)"),
    ("hklawsoc.org.hk",              "Law Society of Hong Kong — The Law List"),
    # Warsaw (XX-PL) — subagent batch 2026-08-31.
    ("knf.gov.pl",                    "KNF — Polish Financial Supervision Authority entity register"),
    ("pana.gov.pl",                   "PANA — Polish audit-firm register (Lista firm audytorskich)"),
    ("rejestradwokatow.pl",          "Krajowy Rejestr Adwokatów — Polish Bar register"),
    # Auckland (XX-NZ) — subagent batch 2026-08-31.
    ("rbnz.govt.nz",                  "RBNZ — Registered banks in New Zealand"),
    ("rea.govt.nz",                   "REA — New Zealand real-estate licensee public register"),
    # Doha (XX-QA) — subagent batch 2026-08-31.
    ("qfc.qa",                        "QFC — Qatar Financial Centre public register"),
    # Kuwait City (XX-KW) — subagent batch 2026-08-31.
    ("cbk.gov.kw",                    "CBK — Central Bank of Kuwait regulated banks"),
    # Seoul (XX-KR) — subagent batch 2026-08-31.
    ("kfb.or.kr",                     "KFB — Korea Federation of Banks member list"),
    # Tel Aviv (XX-IL) + Luxembourg City (XX-LU) — subagent batch 2026-08-31.
    ("boi.org.il",                    "Bank of Israel — supervised banking corporations"),
    ("cssf.lu",                       "CSSF — Luxembourg supervised entities & audit register"),
    ("chambre-immobiliere.lu",       "CIGDL — Chambre Immobilière du Grand-Duché member directory"),
    # Athens (XX-GR) + Mexico City (XX-MX) — subagent batch 2026-08-31.
    ("elte.org.gr",                   "ELTE/HAASOB — Greek public register of audit firms"),
    ("condusef.gob.mx",              "CONDUSEF SIPRES — Mexican supervised financial entities"),
    # Prague (XX-CZ) — subagent batch 2026-08-31.
    ("cnb.cz",                        "ČNB — Czech National Bank JERRS register"),
    ("cak.cz",                        "ČAK — Czech Bar Association advocate register"),
    ("kacr.cz",                       "KAČR — Czech Chamber of Auditors register"),
    ("ares.gov.cz",                   "ARES/RŽP — Czech Trade Register (real-estate brokerage)"),
    # São Paulo (XX-BR) — subagent batch 2026-08-31.
    ("bcb.gov.br",                    "BCB — Banco Central do Brasil financial-institution register"),
    ("oabsp.org.br",                 "OAB-SP — São Paulo Bar law-firm register"),
    # Shanghai (XX-CN) — subagent batch 2026-08-31.
    ("pbc.gov.cn",                    "PBOC/NFRA — systemically important banks list (China)"),
    # Bengaluru (XX-IN) + Istanbul (XX-TR) — subagent batch 2026-08-31.
    ("rbi.org.in",                    "RBI — Reserve Bank of India scheduled banks"),
    ("bddk.org.tr",                   "BDDK — Turkish banking regulator licensed banks"),
    # Bangkok (XX-TH) — subagent batch 2026-08-31.
    ("bot.or.th",                     "BoT — Bank of Thailand financial-institutions list"),
    # Muscat (XX-OM) — subagent batch 2026-08-31.
    ("cbo.gov.om",                    "CBO — Central Bank of Oman licensed banks"),
    # Kuala Lumpur (XX-MY) — subagent batch 2026-08-31.
    ("bnm.gov.my",                    "BNM — Bank Negara Malaysia licensed banks"),
    # Manama (XX-BH) — subagent batch 2026-08-31.
    ("cbb.gov.bh",                    "CBB — Central Bank of Bahrain licensing register"),
    # Johannesburg (XX-ZA) — subagent batch 2026-08-31.
    ("resbank.co.za",                 "SARB — South African Reserve Bank registered banks"),
    ("irba.co.za",                    "IRBA — SA registered audit firms"),
    ("theppra.org.za",               "PPRA — SA property practitioners register"),
    # Bucharest (XX-RO) — subagent batch 2026-08-31.
    ("bnr.ro",                        "BNR — National Bank of Romania credit-institutions register"),
    # Buenos Aires (XX-AR) — subagent batch 2026-08-31.
    ("bcra.gob.ar",                   "BCRA — Banco Central Argentina financial-entities directory"),
    ("colegioinmobiliario.org.ar",   "CUCICBA — Buenos Aires real-estate brokers register"),
    # Santiago (XX-CL) — subagent batch 2026-08-31.
    ("cmfchile.cl",                   "CMF — Chile supervised-banks register"),
    # Budapest (XX-HU) — subagent batch 2026-08-31.
    ("mnb.hu",                        "MNB — Magyar Nemzeti Bank institution register"),
    ("mkvk.hu",                       "MKVK — Hungarian Chamber of Auditors register"),
    # Tallinn (XX-EE) + Reykjavik (XX-IS) — subagent batch 2026-08-31.
    ("advokatuur.ee",                 "Eesti Advokatuur — Estonian Bar law-offices register"),
    ("audiitorkogu.ee",              "Audiitorkogu — Estonian audit-firms register"),
    ("cb.is",                         "Central Bank of Iceland — supervised commercial banks"),
    ("endurskodendarad.is",          "Endurskoðendaráð — Iceland audit-firms register"),
    ("island.is",                     "Ísland.is — Iceland licensed real-estate agents register"),
    # Nicosia (XX-CY) + Valletta (XX-MT) — subagent batch 2026-08-31.
    ("centralbank.cy",               "Central Bank of Cyprus — register of credit institutions"),
    ("cyprusbar.org",                "Cyprus Bar Association — lawyers' companies registry"),
    ("icpac.org.cy",                 "ICPAC — Cyprus statutory audit-firms register"),
    ("ktimatomesites.com",           "Cyprus Real Estate Agents Registration Council register"),
    ("mfsa.mt",                       "MFSA Financial Services Register (Malta)"),
    ("avukati.org",                  "Malta Chamber of Advocates — Find a Lawyer directory"),
    # Wave 9 (XX-TW/VN/ID/PH) — central-bank registers; movers/schools reuse fidi/iam/ibo above.
    ("cbc.gov.tw",                    "CBC — Central Bank of the Republic of China (Taiwan) domestic-bank list"),
    ("sbv.gov.vn",                    "SBV — State Bank of Vietnam foreign-bank-branch register"),
    ("bsp.gov.ph",                    "BSP — Bangko Sentral ng Pilipinas directory of banks"),
    # Wave 10 (XX-CO/PE/UY/CR/PA) — bank supervisor registers; movers/schools reuse fidi/iam/ibo.
    ("superfinanciera.gov.co",        "Superintendencia Financiera de Colombia — bank register"),
    ("sbs.gob.pe",                    "SBS — Superintendencia de Banca, Seguros y AFP (Peru) bank directory"),
    ("bcu.gub.uy",                    "BCU — Banco Central del Uruguay authorised-bank register"),
    ("sugef.fi.cr",                   "SUGEF — Superintendencia General de Entidades Financieras (Costa Rica) bank register"),
    ("superbancos.gob.pa",           "Superintendencia de Bancos de Panamá — general-licence bank register"),
    # Wave 11 (XX-HR/SI/SK/LT/LV) — national central-bank / bank-supervisor registers.
    ("hnb.hr",                        "HNB — Hrvatska narodna banka credit-institutions list"),
    ("bsi.si",                        "Banka Slovenije — register of supervised banks"),
    ("nbs.sk",                        "NBS — Národná banka Slovenska supervised-entities register"),
    ("lb.lt",                         "Lietuvos bankas — financial-market-participants register"),
    ("bank.lv",                       "Latvijas Banka — licensed credit-institutions register"),
    # Registry-gap wiring 2026-09-09 — NO/DE schools, ES/SE/FI/IT non-movers. Each register was
    # probed live; names below match the RegistrySource entries exactly (source_for_url keys on name).
    ("nsr.udir.no",                   "NSR — Nasjonalt skoleregister (Udir, NO)"),
    ("bildung.berlin.de",             "Schulverzeichnis Berlin (Senatsverwaltung für Bildung)"),
    ("bildung.hessen.de",             "Hessische Schuldatenbank (Hessisches Kultusministerium)"),
    ("comunidad.madrid",              "RAIN — Registro de Agentes Inmobiliarios de la Comunidad de Madrid"),
    ("abogacia.es",                   "Censo General de Letrados (Consejo General de la Abogacía Española)"),
    ("icac.gob.es",                   "ROAC — Registro Oficial de Auditores de Cuentas (ICAC)"),
    ("bde.es",                        "Registro de Entidades del Banco de España"),
    ("fmi.se",                        "Fastighetsmäklarinspektionen (FMI) — register of estate agents (SE)"),
    ("advokatsamfundet.se",           "Sveriges advokatsamfund — Swedish Bar member register"),
    ("revisorsinspektionen.se",       "Revisorsinspektionen — Swedish statutory auditor register"),
    ("fi.se",                         "Finansinspektionen (FI) — company register (SE)"),
    ("lvv.fi",                        "Välitysliikerekisteri — FI real-estate & letting agency register (Luova)"),
    ("registroimprese.it",            "Registro Imprese / REA — Camere di Commercio (IT)"),
    ("consiglionazionaleforense.it",  "Albo Unico Nazionale degli Avvocati (Consiglio Nazionale Forense)"),
    ("commercialisti.it",             "Albo Unico Nazionale dei Dottori Commercialisti (CNDCEC)"),
    ("bancaditalia.it",               "Albo delle banche — Banca d'Italia (GIAVA)"),
)


class RowError(ValueError):
    """A row that cannot be turned into a Candidate at all (bad shape, not bad sourcing)."""


def _domain(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "//" not in raw:
        raw = "//" + raw
    return (urlsplit(raw).hostname or "").lower().lstrip(".")


def source_for_url(source_url: str) -> RegistrySource:
    """Map an evidence URL to the registry that published it.

    Anything unrecognised is SELF_DECLARED (tier 3) rather than a guess. That is the safe
    default: `validate()` then rejects it and it lands on the re-sourcing worklist, which is
    strictly better than staging it as though a registry vouched for it.
    """
    host = _domain(source_url)
    best: Optional[Tuple[int, str]] = None
    for suffix, name in _DOMAIN_TO_SOURCE:
        if host == suffix or host.endswith("." + suffix):
            if best is None or len(suffix) > best[0]:
                best = (len(suffix), name)
    return _BY_NAME[best[1]] if best else _BY_NAME[SELF_DECLARED]


def coerce_expiry(value: Optional[str]) -> Optional[str]:
    """Normalise an accreditation expiry to an ISO date, or None.

    `vendor_candidates.accreditation_expiry` is typed `date`, but registries commonly publish
    only a year and that is all the harvest captured ('2028').

    A bare year becomes **YYYY-01-01**, the earliest date consistent with the evidence.
    YYYY-12-31 would be the natural-looking choice and is the wrong one: it asserts up to
    twelve months of validity nobody verified, and this is the exact field a customer's
    procurement review re-checks. Under-claiming is recoverable; over-claiming is a finding.

        >>> coerce_expiry("2028")
        '2028-01-01'
        >>> coerce_expiry("2027-06-30")
        '2027-06-30'
        >>> coerce_expiry("") is None
        True
    """
    raw = (value or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    raise RowError(
        f"accreditation_expiry {raw!r} is neither a bare year nor an ISO date — "
        "refusing to guess a date for an accreditation claim"
    )


def _note_for(row: Dict[str, str], expiry_raw: str, source: RegistrySource) -> Optional[str]:
    """Record every inference, so a reviewer can see what was derived rather than read."""
    notes: List[str] = []
    if re.fullmatch(r"\d{4}", (expiry_raw or "").strip()):
        notes.append(
            f"expiry coerced from bare year {expiry_raw.strip()} to 1 Jan (earliest "
            "consistent date; the register published no day/month)"
        )
    if not (row.get("website_url") or "").strip():
        notes.append("no supplier domain in the harvest — deduped by name+corridor, so a "
                     "near-name match must be checked by hand before approval")
    if source.name == SELF_DECLARED:
        notes.append(f"evidence URL is not a registry ({_domain(row.get('source_url', ''))})")
    claimed = (row.get("source_name") or "").strip()
    if claimed and claimed != source.name:
        notes.append(f"harvest called this source {claimed!r}")
    return " · ".join(notes) or None


def read_csv(path: Path) -> Iterator[Candidate]:
    """Yield one Candidate per data row. Raises RowError on a malformed file or row."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        if header != EXPECTED_HEADER:
            raise RowError(
                f"unexpected header.\n  expected: {EXPECTED_HEADER}\n  got:      {header}"
            )
        for lineno, row in enumerate(reader, start=2):
            try:
                yield _to_candidate(row)
            except RowError as exc:
                raise RowError(f"line {lineno}: {exc}") from exc


def _dest_iso_from_corridor(corridor: str) -> Optional[str]:
    """Destination ISO alpha-2 for a corridor code like 'FR-DE' / 'ES-IE' / 'US-EC'.

    A vendor's supplier capability is scoped to the DESTINATION country, and the batch's
    `corridor` column is ORIGIN-DEST in ISO alpha-2, so the destination is the second token.
    This was a two-entry dict (``{"FR-DE": "DE", "FR-NO": "NO"}``) that returned ``None`` for
    every other corridor — so ES-IE, NO-FR, FR-SG and US-EC promoted supplier capabilities
    with no ``country_code`` at all. Deriving it covers every corridor, and ``to_iso_alpha2``
    rejects a malformed token (returns ``None``) rather than storing junk.
    """
    if not corridor:
        return None
    for sep in ("->", "→", "-", "_"):  # check "->" / "→" before bare "-"
        if sep in corridor:
            _, _, tail = corridor.partition(sep)
            return to_iso_alpha2(tail.strip())
    return None


def _to_candidate(row: Dict[str, str]) -> Candidate:
    def get(k: str) -> str:
        return (row.get(k) or "").strip()

    source_url = get("source_url")
    source = source_for_url(source_url)
    expiry_raw = get("accreditation_expiry")

    return Candidate(
        name=get("company_name"),
        website_url=get("website_url"),
        corridor=get("corridor"),
        service_category=get("service_category"),
        source=source,
        source_url=source_url or None,
        accreditation_body=get("accreditation_body") or None,
        accreditation_number=get("accreditation_number") or None,
        accreditation_expiry=coerce_expiry(expiry_raw),
        country_code=_dest_iso_from_corridor(get("corridor")),
        notes=_note_for(row, expiry_raw, source),
    )
