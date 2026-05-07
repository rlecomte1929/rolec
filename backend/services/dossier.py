import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def get_profile_value(profile: Dict[str, Any], path: str) -> Any:
    current: Any = profile
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def evaluate_applies_if(rule: Optional[Dict[str, Any]], profile: Dict[str, Any]) -> bool:
    if not rule:
        return True
    if "and" in rule:
        return all(evaluate_applies_if(r, profile) for r in rule.get("and", []))
    if "or" in rule:
        return any(evaluate_applies_if(r, profile) for r in rule.get("or", []))
    if "not" in rule:
        return not evaluate_applies_if(rule.get("not"), profile)

    field = rule.get("field")
    op = rule.get("op")
    value = rule.get("value")
    field_value = get_profile_value(profile, field) if field else None

    if op == "exists":
        exists = field_value is not None and field_value != ""
        return exists if value is True else not exists
    if op == "==":
        return field_value == value
    if op == "!=":
        return field_value != value
    if op == "in":
        if isinstance(value, list):
            return field_value in value
        if isinstance(field_value, list):
            return value in field_value
        return False
    if op == "contains":
        if isinstance(field_value, list):
            return value in field_value
        if isinstance(field_value, str) and isinstance(value, str):
            return value.lower() in field_value.lower()
        return False
    return True


def validate_answer(answer: Any, answer_type: str, options: Optional[List[str]]) -> Optional[str]:
    if answer_type == "text":
        if not isinstance(answer, str):
            return "Expected text"
        return None
    if answer_type == "boolean":
        if not isinstance(answer, bool):
            return "Expected boolean"
        return None
    if answer_type == "date":
        if not isinstance(answer, str):
            return "Expected date string"
        return None
    if answer_type == "select":
        if not isinstance(answer, str):
            return "Expected select string"
        if options and answer not in options:
            return "Value not in options"
        return None
    if answer_type == "multiselect":
        if not isinstance(answer, list):
            return "Expected list"
        if options and any(a not in options for a in answer):
            return "One or more values not in options"
        return None
    return "Unsupported answer type"


def _allowed_domains_for_destination(dest: str) -> List[str]:
    dest_upper = dest.upper()
    if dest_upper in ("SG", "SINGAPORE"):
        return ["mom.gov.sg", "ica.gov.sg", "iras.gov.sg", "cpf.gov.sg", "gov.sg"]
    if dest_upper in ("US", "USA", "UNITED STATES"):
        return ["uscis.gov", "travel.state.gov", "cbp.gov", "irs.gov", "ssa.gov"]
    if dest_upper in ("FR", "FRANCE"):
        return ["service-public.fr", "interieur.gouv.fr", "ofii.fr", "diplomatie.gouv.fr", "gouv.fr"]
    if dest_upper in ("DE", "GERMANY"):
        return ["bamf.de", "make-it-in-germany.com", "auswaertiges-amt.de", "bundesregierung.de", "arbeitsagentur.de"]
    if dest_upper in ("NO", "NORWAY"):
        return ["udi.no", "nav.no", "skatteetaten.no", "norge.no", "politiet.no"]
    if dest_upper in ("BR", "BRAZIL"):
        return ["gov.br", "mre.gov.br", "pf.gov.br", "receita.fazenda.gov.br"]
    if dest_upper in ("IT", "ITALY"):
        return ["esteri.it", "interno.gov.it", "lavoro.gov.it", "stranieriinitalia.it", "governo.it"]
    if dest_upper in ("ES", "SPAIN"):
        return ["exteriores.gob.es", "interior.gob.es", "empleo.gob.es", "seg-social.es", "administracion.gob.es"]
    return []


def _build_search_queries(dest: str, profile: Dict[str, Any]) -> List[str]:
    purpose = get_profile_value(profile, "relocationBasics.purpose") or "relocation"
    dest_name = dest
    return [
        f"{dest_name} work visa requirements {purpose}",
        f"{dest_name} onboarding registration requirements",
        f"{dest_name} payroll basics employer responsibilities",
        f"{dest_name} housing basics for expats",
    ]


def _serpapi_search(query: str, allowed_domains: List[str]) -> List[Dict[str, str]]:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return []
    site_filter = " OR ".join([f"site:{d}" for d in allowed_domains]) if allowed_domains else ""
    full_query = f"{query} ({site_filter})" if site_filter else query
    params = {
        "engine": "google",
        "q": full_query,
        "api_key": api_key,
        "num": "5",
    }
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    results: List[Dict[str, str]] = []
    for item in payload.get("organic_results", [])[:5]:
        link = item.get("link")
        title = item.get("title")
        snippet = item.get("snippet")
        if not link or not title:
            continue
        domain = urllib.parse.urlparse(link).netloc
        if allowed_domains and not any(domain.endswith(d) for d in allowed_domains):
            continue
        results.append({"title": title, "url": link, "snippet": snippet or ""})
    return results


def fetch_search_results(dest: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    allowed_domains = _allowed_domains_for_destination(dest)
    if not allowed_domains:
        return {"queries": [], "results": []}
    queries = _build_search_queries(dest, profile)
    all_results: List[Dict[str, Any]] = []
    for q in queries:
        results = _serpapi_search(q, allowed_domains)
        for r in results:
            all_results.append({"query": q, **r})
    return {"queries": queries, "results": all_results}


def build_suggested_questions(dest: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dest_upper = dest.upper()
    suggested: List[Dict[str, Any]] = []

    templates = []
    if dest_upper in ("SG", "SINGAPORE"):
        templates = [
            ("Employment Pass", "Is your employer sponsoring an Employment Pass (EP)?"),
            ("S Pass", "Is your employer sponsoring an S Pass?"),
            ("Dependent", "Will dependents apply for Dependant’s Passes?"),
            ("ICA", "Will you need an entry visa or entry approval?"),
        ]
    if dest_upper in ("US", "USA", "UNITED STATES"):
        templates = [
            ("H-1B", "Is the intended visa category H-1B?"),
            ("L-1", "Is the intended visa category L-1?"),
            ("O-1", "Is the intended visa category O-1?"),
            ("SSN", "Will you need to apply for a Social Security Number (SSN)?"),
            ("I-9", "Will you need to complete I-9 employment verification?"),
        ]
    if dest_upper in ("GB", "UK", "UNITED KINGDOM"):
        templates = [
            ("Sponsor Licence", "Does your employer hold an active UK Sponsor Licence?"),
            ("Certificate of Sponsorship", "Has a Certificate of Sponsorship (CoS) been assigned to you?"),
            ("Skilled Worker", "Have the mandatory 70 points under the UK points-based system been confirmed?"),
            ("biometric", "Have you booked a biometric appointment at a UKVCAS service point?"),
            ("BRP", "Are you aware that your BRP card must be collected from a Post Office within 10 days of arrival?"),
        ]
    if dest_upper in ("FR", "FRANCE"):
        templates = [
            ("VLS-TS", "Has your long-stay visa (VLS-TS) application been submitted to the consulate?"),
            ("OFII", "Have you completed the OFII arrival declaration and medical visit?"),
            ("titre de séjour", "Has your titre de séjour prefecture appointment been scheduled?"),
            ("Passeport Talent", "Has your employer confirmed the work permit route (Salarié or Passeport Talent)?"),
            ("consulate", "Has your consulate appointment been booked for the visa application?"),
        ]
    if dest_upper in ("DE", "GERMANY"):
        templates = [
            ("Blue Card", "Has the work visa type been confirmed? (EU Blue Card or Skilled Worker Visa)"),
            ("Anmeldung", "Have you registered your address (Anmeldung) at the local Einwohnermeldeamt?"),
            ("Aufenthaltstitel", "Has your residence permit (Aufenthaltstitel) application been submitted to the Ausländerbehörde?"),
            ("Anerkennung", "Have your foreign qualifications been formally recognised by the relevant German authority?"),
            ("health insurance", "Do you have statutory or private health insurance in place for the residence permit?"),
        ]
    if dest_upper in ("NO", "NORWAY"):
        templates = [
            ("skilled worker", "Has the work permit type been confirmed? (Skilled Worker Permit or EU/EEA registration)"),
            ("UDI", "Has the work permit application been submitted to UDI (for non-EU/EEA nationals)?"),
            ("Skattekort", "Have you obtained your tax card (Skattekort) from Skatteetaten?"),
            ("D-number", "Have you obtained a Norwegian D-number or national identity number (fødselsnummer)?"),
            ("Folkeregisteret", "Have you registered your address with the Norwegian Population Register (Folkeregisteret)?"),
        ]
    if dest_upper in ("BR", "BRAZIL"):
        templates = [
            ("VITEM V", "Has the VITEM V work visa application been submitted at the consulate?"),
            ("CRNM", "Has the CRNM (Federal Police residence registration) been completed within 90 days of arrival?"),
            ("CPF", "Has your CPF (Cadastro de Pessoas Físicas) tax ID number been registered?"),
            ("CTPS", "Has your CTPS (employment card) been registered with your employer?"),
            ("MTE", "Has the employer obtained work authorization approval from the Ministry of Labour?"),
        ]
    if dest_upper in ("IT", "ITALY"):
        templates = [
            ("Nulla Osta", "Has the Nulla Osta (work authorization) been obtained from the Sportello Unico?"),
            ("Permesso di Soggiorno", "Has the Permesso di Soggiorno (residence permit) application been submitted to the Questura?"),
            ("Codice Fiscale", "Have you obtained your Italian tax code (Codice Fiscale)?"),
            ("Type D", "Has the National (Type D) visa application been submitted at the Italian consulate?"),
            ("ASL", "Have you enrolled in the Italian national healthcare system (SSN/ASL)?"),
        ]
    if dest_upper in ("ES", "SPAIN"):
        templates = [
            ("NIE", "Have you obtained your NIE (Número de Identidad de Extranjero)?"),
            ("autorización", "Has the combined work and residence authorization been applied for?"),
            ("Empadronamiento", "Have you completed the Empadronamiento (municipal address registration)?"),
            ("TIE", "Has the TIE (Tarjeta de Identidad de Extranjero) residence card application been submitted?"),
            ("Social Security", "Have you obtained your Spanish Social Security number?"),
        ]

    for t_key, t_question in templates:
        for r in results:
            blob = " ".join([r.get("title", ""), r.get("snippet", ""), r.get("url", "")]).lower()
            if t_key.lower() in blob:
                suggested.append({
                    "question_text": f"{t_question} (Please confirm)",
                    "answer_type": "boolean",
                    "sources": [{"title": r.get("title"), "url": r.get("url")}],
                })
                break

    return suggested

