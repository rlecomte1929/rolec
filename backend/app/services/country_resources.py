"""Country-specific resources and personalization for ReloPass Resources page."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional


RESOURCE_SECTIONS = [
    "welcome",
    "admin_essentials",
    "housing",
    "schools",
    "healthcare",
    "transport",
    "daily_life",
    "community",
    "culture_leisure",
    "nature",
    "cost_of_living",
    "safety",
]

SECTION_LABELS = {
    "welcome": "Welcome",
    "admin_essentials": "Administrative Essentials",
    "housing": "Housing",
    "schools": "Schools & Childcare",
    "healthcare": "Healthcare",
    "transport": "Transportation",
    "daily_life": "Daily Life Essentials",
    "community": "Community & Social Integration",
    "culture_leisure": "Culture & Leisure",
    "nature": "Nature & Weekend Activities",
    "cost_of_living": "Cost of Living Snapshot",
    "safety": "Safety & Practical Tips",
}


def _country_code_from_name(name: str) -> str:
    mapping = {
        "norway": "NO",
        "singapore": "SG",
        "united states": "US",
        "usa": "US",
        "united kingdom": "UK",
        "uk": "UK",
        "germany": "DE",
    }
    return mapping.get((name or "").lower().strip(), (name or "")[:2].upper() if name else "")


def _relocation_type_from_duration_months(months: Optional[int]) -> str:
    if months is None:
        return "permanent"
    if months < 12:
        return "short-term"
    if months <= 24:
        return "long-term"
    return "permanent"


def _children_ages(children: List[Dict]) -> List[int]:
    ages = []
    for c in children or []:
        dob = (c or {}).get("dateOfBirth")
        if dob:
            try:
                d = date.fromisoformat(dob[:10])
                today = date.today()
                ages.append(today.year - d.year - ((today.month, today.day) < (d.month, d.day)))
            except (ValueError, TypeError):
                pass
    return ages


def build_profile_context(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Build resources profile from wizard case draft."""
    basics = draft.get("relocationBasics", {}) or {}
    family = draft.get("familyMembers", {}) or {}
    ac = draft.get("assignmentContext", {}) or {}

    dest_country = basics.get("destCountry") or ""
    dest_city = basics.get("destCity") or ""
    country_code = _country_code_from_name(dest_country) or dest_country[:2].upper() if dest_country else ""

    children = family.get("children") or []
    num_children = len(children)
    spouse = family.get("spouse") or {}
    has_spouse = bool(spouse.get("fullName"))
    spouse_working = bool(spouse.get("wantsToWork"))

    duration = basics.get("durationMonths")
    reloc_type = _relocation_type_from_duration_months(duration)

    return {
        "destination_country": dest_country,
        "destination_city": dest_city,
        "country_code": country_code,
        "visa_type": None,  # not in wizard yet
        "arrival_date": basics.get("targetMoveDate"),
        "family_status": family.get("maritalStatus") or ("couple" if has_spouse else "single"),
        "number_of_children": num_children,
        "children_ages": _children_ages(children),
        "spouse_working": spouse_working,
        "relocation_type": reloc_type or ac.get("contractType", "permanent"),
        "housing_status": None,
        "transport_needs": None,
        "language_level": None,
        "has_children": num_children > 0,
        "has_spouse": has_spouse,
    }


def get_personalization_hints(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return personalization hints and AI-style recommendations for the UI."""
    hints = {
        "priorities": [],
        "recommendations": [],
    }
    if profile.get("has_children"):
        hints["priorities"].extend([
            "schools",
            "childcare",
            "family_activities",
            "family_friendly_housing",
        ])
        if profile.get("destination_city", "").lower() in ("oslo",) and profile.get("country_code") == "NO":
            hints["recommendations"].append("Neighborhood: Bærum (family-friendly)")
            hints["recommendations"].append("School: Oslo International School")
            hints["recommendations"].append("Weekend activity: Nordmarka hiking")
        if profile.get("country_code") == "SG":
            hints["recommendations"].append("Neighborhood: East Coast (family-friendly)")
            hints["recommendations"].append("Schools: GIS, UWC, SAS (apply early)")
        if profile.get("country_code") == "US":
            hints["recommendations"].append("Check school districts when choosing housing")
    if profile.get("has_spouse") and profile.get("spouse_working"):
        hints["priorities"].extend(["job_boards", "work_permits", "networking"])
        cc = profile.get("country_code")
        if cc == "NO":
            hints["recommendations"].append("Expat group: Internations Oslo")
        if cc == "SG":
            hints["recommendations"].append("Expat group: Internations Singapore")
    if profile.get("family_status") == "single" or (not profile.get("has_children") and not profile.get("has_spouse")):
        hints["priorities"].extend(["networking", "coworking", "professional_associations"])
        cc = profile.get("country_code")
        if cc == "NO":
            hints["recommendations"].append("Expat group: Internations Oslo")
        if cc == "SG":
            hints["recommendations"].append("Expat group: Internations Singapore")
    return hints


def get_default_section_content(country_code: str, city: str, section_key: str) -> Dict[str, Any]:
    """Return default section content when DB has none. Curated per country."""
    c = country_code.upper()
    city_key = (city or "").strip()

    # Norway-specific content
    if c == "NO":
        no_defaults = {
            "welcome": {
                "intro": "Norway values work-life balance, punctuality, and egalitarianism. Most business is conducted in English.",
                "cultural_tips": [
                    "Punctuality is expected — arrive on time",
                    "Informal but professional communication",
                    "Public holidays: 17 May (Constitution Day), Christmas, Easter",
                    "Winter: prepare for short days; summer: long daylight",
                ],
                "work_culture": ["Typical hours: 37.5/week", "Flexible working common", "Lunch often 30 min"],
            },
            "admin_essentials": {
                "topics": [
                    {"title": "Residence registration (Folkeregisteret)", "timeline": "Within 7 days", "link": "https://www.skatteetaten.no/en/person/national-registry/"},
                    {"title": "Tax card (Skatt kort)", "timeline": "1–2 weeks", "link": "https://www.skatteetaten.no/"},
                    {"title": "D-number or ID number", "timeline": "At registration", "link": None},
                    {"title": "Bank account (BankID required)", "timeline": "1–2 weeks", "link": None},
                    {"title": "Mobile & BankID", "timeline": "First week", "link": None},
                    {"title": "GP registration (fastlege)", "timeline": "First month", "link": "https://helsenorge.no/"},
                ],
            },
            "housing": {
                "overview": "Oslo has a tight rental market. Finn.no is the main platform. Expect deposit of 2–3 months.",
                "platforms": [
                    {"title": "Finn.no", "url": "https://www.finn.no/bolig/", "description": "Main rental and sale portal"},
                    {"title": "Hyalite", "url": "https://hyalite.io/", "description": "Expat-focused rentals"},
                ],
                "neighborhoods": ["Frogner", "Grünerløkka", "Sagene", "Bærum (family-friendly)"],
            },
            "schools": {
                "overview": "Public school is free. International schools charge tuition. Barnehage (kindergarten) has parental fees.",
                "school_types": ["Public (Barneskole)", "International", "Private"],
                "topics": [
                    {"title": "International schools (Oslo)", "timeline": "Apply early", "link": None},
                    {"title": "Barnehage enrollment", "timeline": "Register before arrival", "link": "https://oslo.kommune.no/barn-og-utdanning/"},
                ],
            },
            "healthcare": {
                "overview": "Public healthcare is subsidized. Register with a GP (fastlege). EU health card covers emergencies.",
                "emergency": "113",
                "topics": [
                    {"title": "Emergency", "timeline": "113", "link": None},
                    {"title": "Non-emergency", "timeline": "116 117", "link": None},
                ],
            },
            "transport": {
                "overview": "Ruter runs Oslo public transport. Monthly pass ~700–900 NOK. Cycling is popular.",
                "platforms": [
                    {"title": "Ruter", "url": "https://ruter.no/", "description": "Public transport"},
                    {"title": "VY", "url": "https://www.vy.no/", "description": "Trains"},
                ],
            },
            "daily_life": {
                "overview": "Most shops close early on weekends. Rema 1000, Kiwi, Meny for groceries.",
                "items": [
                    {"title": "Food delivery", "description": "Foodora, Wolt"},
                    {"title": "Banking", "description": "DNB, Nordea, Sbanken"},
                    {"title": "Mobile", "description": "Telenor, Telia, ICE"},
                ],
            },
            "community": {
                "overview": "Expat communities and professional networks.",
                "groups": [
                    {"title": "Internations Oslo", "url": "https://www.internations.org/oslo-expats", "description": "Expat meetups"},
                    {"title": "Meetup Oslo", "url": "https://www.meetup.com/cities/no/oslo/", "description": "Events and groups"},
                ],
            },
            "culture_leisure": {
                "overview": "Oslo has museums, festivals, and a vibrant cultural scene.",
                "items": [
                    {"title": "Munch Museum", "description": "Art museum", "url": "https://www.munchmuseet.no/"},
                    {"title": "Opera House", "description": "Opera and ballet", "url": "https://operaen.no/"},
                ],
            },
            "nature": {
                "overview": "Nordmarka offers hiking, skiing. Easy access from Oslo. Family-friendly trails.",
                "items": [
                    {"title": "Nordmarka", "description": "Forest and lakes, 30 min from city"},
                    {"title": "Vigeland Park", "description": "Sculpture park, free"},
                ],
            },
            "cost_of_living": {
                "items": [
                    {"label": "Average rent (1-bed)", "value": "~15,000–20,000 NOK"},
                    {"label": "Monthly transport", "value": "~700–900 NOK"},
                    {"label": "Groceries (monthly)", "value": "~4,000–6,000 NOK"},
                    {"label": "Restaurant meal", "value": "~200–350 NOK"},
                ],
            },
            "safety": {
                "emergency": "113",
                "tips": [
                    "Emergency: 113 (police/ambulance)",
                    "Keep emergency numbers in phone",
                    "Winter: dress in layers, watch for ice",
                ],
            },
        }
        if section_key in no_defaults:
            return no_defaults[section_key]

    # Ireland-specific content — [AIQ-1746 / T18-06]
    #
    # Before this block Ireland had no entry here at all, so it fell through to the
    # generic defaults at the bottom of this function. That is where the campaign's
    # worst single line came from: admin_essentials offered "Residence registration —
    # Within 7-14 days", which is wrong for EVERY Irish case. An EEA citizen needs no
    # residence registration at all (Citizens Information: they "do not need to register
    # with the immigration authorities"), and a non-EEA national registers for an IRP
    # within 90 days, not 7-14.
    #
    # Nationality never reaches this function (there is no nationality parameter, and
    # `nationality` appears nowhere in the resources read path), so each item below is
    # written to be true for BOTH branches rather than branching. Per-nationality
    # scoping needs a column on country_resources plus read-path threading; tracked
    # separately.
    #
    # Facts dated 2026-08 and sourced. Two are recent enough that most third-party
    # guides are still wrong: Rent Pressure Zones were abolished 1 March 2026 (RTB),
    # and Ireland is not in the EU Blue Card scheme (it uses employment permits).
    if c == "IE":
        ie_defaults = {
            "welcome": {
                "intro": (
                    "Ireland is English-speaking and EU, but it is outside the Schengen area and "
                    "runs its own immigration system. Dublin is small, expensive to rent in, and "
                    "most official steps depend on getting a PPS number first."
                ),
                "cultural_tips": [
                    "Conversation is informal and indirect — 'grand' rarely means excellent",
                    "Pubs are social rather than drinking-led; rounds are reciprocated",
                    "Bank holidays fall on Mondays; St Patrick's Day (17 March) closes most things",
                    "Rain is persistent rather than heavy — a coat beats an umbrella",
                ],
                "work_culture": [
                    "Typical hours: 37.5–40/week",
                    "Hybrid working is common in Dublin tech and finance",
                    "First names used at every level, including with senior leadership",
                ],
            },
            # The sequencing IS the advice. A newly-arrived EEA citizen holds no Irish
            # residence document (they get no IRP), so they cannot satisfy a bank's
            # proof-of-address rule until Revenue has issued them something. PPSN →
            # Revenue → bank is the only order that actually completes.
            "admin_essentials": {
                "overview": (
                    "Do these in order: PPS number first, then register your job with Revenue, "
                    "then open a bank account. Each step produces the document the next one asks "
                    "for, and skipping ahead is what strands people for weeks."
                ),
                "topics": [
                    {
                        "title": "1. PPS number (PPSN) — apply on MyWelfare.ie",
                        "timeline": "Apply week 1 · in-person appointment · ~10–20 days",
                        "link": "https://www.gov.ie/en/department-of-social-protection/services/get-a-personal-public-service-pps-number/",
                    },
                    {
                        "title": "2. Register your job with Revenue (myAccount) — your employer cannot do it for you",
                        "timeline": "Before your first payday — otherwise emergency tax from week 5",
                        "link": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx",
                    },
                    {
                        "title": "3. Open a bank account",
                        "timeline": "After PPSN + a Revenue document",
                        "link": "https://www.citizensinformation.ie/en/money-and-tax/personal-finance/banking/financial-institutions-and-identification/",
                    },
                    {
                        "title": (
                            "Residence registration — not required for EU/EEA and Swiss citizens; "
                            "non-EEA nationals register for an IRP within 90 days"
                        ),
                        "timeline": "EEA/Swiss: none · Non-EEA: within 90 days (Burgh Quay, EUR 300, Stamp 1)",
                        "link": "https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/rights-of-residence-in-ireland/registration-of-non-eea-nationals-in-ireland/",
                    },
                    {
                        "title": "Exchange your driving licence (NDLS)",
                        "timeline": "EU/EEA licence: exchangeable, EUR 55 · Non-EEA: usually the full Irish test",
                        "link": "https://www.ndls.ie/licensed-driver/exchange-my-foreign-driving-licence.html",
                    },
                ],
            },
            "housing": {
                "overview": (
                    "Dublin's rental market is very tight and moves in days, not weeks. Daft.ie's "
                    "Q1 2026 report puts the Dublin average at EUR 2,012 for a 1-bed and EUR 2,609 "
                    "for a 2-bed; by sub-market a 2-bed runs about EUR 2,850 in the South City and "
                    "EUR 2,444 in the North City. Viewings are often group slots — bring ID, proof "
                    "of employment and references ready to send the same day."
                ),
                "platforms": [
                    {"title": "Daft.ie", "url": "https://www.daft.ie/", "description": "The dominant Irish rental portal"},
                    {"title": "MyHome.ie", "url": "https://www.myhome.ie/", "description": "Second major listings site"},
                    {"title": "RTB (Residential Tenancies Board)", "url": "https://www.rtb.ie/", "description": "Tenancy registration, rights and disputes"},
                ],
                # Criterion 2 asks for at least six named Dublin areas.
                "neighborhoods": [
                    "Grand Canal Dock / Docklands — walk to the tech campuses, newest stock, priciest",
                    "Ranelagh — leafy Victorian, 20 min walk to town, popular with professionals",
                    "Rathmines — period conversions, well served by buses, mixed student and family",
                    "Portobello — canal-side, central, small units",
                    "Stoneybatter / Smithfield — northside, red-brick, lively food scene",
                    "Drumcondra — quieter northside, good value, near Croke Park",
                    "Clontarf — coastal, family-oriented, seafront walks",
                    "Dun Laoghaire — coastal town on the DART, family-friendly, more space per euro",
                ],
            },
            "schools": {
                "overview": (
                    "State primary and secondary schools are free, but most are managed by a patron "
                    "body and many are heavily oversubscribed in Dublin — apply as early as you can. "
                    "International schools charge fees and are limited in number."
                ),
                "school_types": ["State (free)", "Educate Together (multi-denominational)", "Gaelscoil (Irish-medium)", "Fee-paying", "International"],
                "topics": [
                    {
                        "title": "How school admissions work",
                        "timeline": "Apply as early as possible — Dublin schools are oversubscribed",
                        "link": "https://www.citizensinformation.ie/en/education/primary-and-post-primary-education/going-to-primary-school/enrolling-in-primary-school/",
                    },
                ],
            },
            "healthcare": {
                "overview": (
                    "Healthcare in Ireland is not free at the point of use for most workers. On a "
                    "professional salary you will not qualify for a medical card (the single-person "
                    "means limit is about EUR 184/week), so expect to pay EUR 45–65 per GP visit — "
                    "fees are unregulated and vary by practice. Many Dublin practices are closed to "
                    "new patients, so register early. Employer health insurance is common and worth "
                    "activating before you arrive."
                ),
                "emergency": "112 or 999 (both work in Ireland)",
                "topics": [
                    {
                        "title": "Register with a GP early — many practices are closed to new patients",
                        "timeline": "First month",
                        "link": "https://www2.hse.ie/services/find-a-gp/",
                    },
                    {
                        "title": "Emergency department charge without a GP referral",
                        "timeline": "EUR 100 per visit unless referred",
                        "link": "https://www.citizensinformation.ie/en/health/health-services/gp-and-hospital-services/hospital-charges/",
                    },
                    {
                        "title": "Medical card means test (under 70s)",
                        "timeline": "Unlikely to qualify on a professional salary",
                        "link": "https://www.citizensinformation.ie/en/health/medical-cards-and-gp-visit-cards/medical-card-means-test-under-70s/",
                    },
                ],
            },
            "transport": {
                "overview": (
                    "Dublin runs on buses, the DART coastal rail line and two Luas tram lines; there "
                    "is no metro. A Leap Card is the cheapest way to pay and caps your spend "
                    "automatically. Traffic is heavy and city-centre parking is expensive, so most "
                    "commuters do not drive in."
                ),
                "topics": [
                    {
                        "title": "Leap Card — 90-minute fare EUR 2, daily cap EUR 6, weekly cap EUR 24",
                        "timeline": "Buy on arrival (airport, shops) or order online",
                        "link": "https://about.leapcard.ie/",
                    },
                    {
                        "title": "TFI journey planner (bus, DART, Luas)",
                        "timeline": "—",
                        "link": "https://www.transportforireland.ie/",
                    },
                ],
            },
            "daily_life": {
                "overview": (
                    "Mobile and broadband are competitive and mostly contract-free if you prefer. "
                    "Electricity and gas are self-arranged and you can switch supplier freely; "
                    "bin collection is a private contract you arrange yourself, which surprises "
                    "most new arrivals."
                ),
                "platforms": [
                    {"title": "Bonkers.ie", "url": "https://www.bonkers.ie/", "description": "Compare energy, broadband and mobile"},
                ],
            },
            "community": {
                "overview": (
                    "Dublin has large Spanish, Brazilian, Polish and Indian communities and an active "
                    "meetup culture. Sports clubs (GAA, rugby, running) are the usual route into a "
                    "local network."
                ),
                "groups": [],
            },
            "culture_leisure": {
                "overview": (
                    "National museums and the National Gallery are free. The city is walkable, and "
                    "the coast is on the DART line in both directions."
                ),
                "events": [],
            },
            "nature": {
                "overview": (
                    "Phoenix Park is one of Europe's largest enclosed city parks. The Dublin and "
                    "Wicklow mountains start about 40 minutes south, and Howth and Bray offer "
                    "coastal cliff walks reachable by DART without a car."
                ),
            },
            "cost_of_living": {
                "overview": (
                    "Dublin is expensive by EU standards and rent dominates the budget. Figures "
                    "below are Dublin-wide averages; see the housing section for sub-market "
                    "variation."
                ),
                "items": [
                    {"label": "Rent — 1-bed (Dublin average)", "value": "EUR 2,012/month", "note": "Daft.ie Rental Report Q1 2026"},
                    {"label": "Rent — 2-bed (Dublin average)", "value": "EUR 2,609/month", "note": "Daft.ie Rental Report Q1 2026"},
                    {"label": "Transport pass", "value": "EUR 24/week (Leap Card cap)", "note": "TFI Leap Card, daily cap EUR 6"},
                    {"label": "GP visit", "value": "EUR 45–65", "note": "Unregulated; varies by practice"},
                    {"label": "Emergency department (no referral)", "value": "EUR 100", "note": "Citizens Information"},
                ],
            },
            "safety": {
                "overview": "Ireland is generally safe; the usual city-centre precautions apply at night.",
                "emergency": "112 or 999 (both work in Ireland)",
                "tips": [
                    "112 and 999 both reach Garda, ambulance and fire",
                    "Rent controls changed on 1 March 2026 — Rent Pressure Zones were abolished and replaced by national rent control, so pre-2026 guidance is out of date",
                    "Ireland is outside the Schengen area — a Spanish residence permit gives you no right to enter Ireland",
                    "Register your tenancy with the RTB — it is the landlord's duty but protects you",
                ],
            },
        }
        if section_key in ie_defaults:
            return ie_defaults[section_key]

    # Singapore-specific content
    if c == "SG":
        sg_defaults = {
            "welcome": {
                "intro": "Singapore is a multicultural hub with English as the main business language. Efficient, safe, and well-connected.",
                "cultural_tips": [
                    "Punctuality is expected",
                    "Remove shoes before entering homes",
                    "Public holidays: Chinese New Year, Hari Raya, Deepavali, Christmas",
                    "Humid year-round; dress light",
                ],
                "work_culture": ["Typical hours: 9–6", "Formal initially", "Many multinationals"],
            },
            "admin_essentials": {
                "topics": [
                    {"title": "Entry visa / IPA", "timeline": "Before arrival", "link": "https://www.ica.gov.sg/"},
                    {"title": "Employment Pass (MOM)", "timeline": "Employer sponsors", "link": "https://www.mom.gov.sg/passes-and-permits"},
                    {"title": "Singpass registration", "timeline": "After EP approval", "link": "https://www.singpass.gov.sg/"},
                    {"title": "Bank account", "timeline": "1–2 weeks", "link": None},
                    {"title": "Mobile (local SIM)", "timeline": "First week", "link": None},
                    {"title": "CPF (employer-managed)", "timeline": "Automatic with employment", "link": "https://www.cpf.gov.sg/"},
                ],
            },
            "housing": {
                "overview": "HDB and private condos. Property Guru and 99.co are main portals. Expect 1–2 months deposit.",
                "platforms": [
                    {"title": "PropertyGuru", "url": "https://www.propertyguru.com.sg/", "description": "Rental and sale listings"},
                    {"title": "99.co", "url": "https://www.99.co/singapore", "description": "Property search"},
                ],
                "neighborhoods": ["Orchard", "Marina Bay", "Tiong Bahru", "East Coast", "Holland Village"],
            },
            "schools": {
                "overview": "Public schools, international schools (GIS, SAS, UWC), and private options. Fees vary widely.",
                "school_types": ["Public", "International", "Private"],
                "topics": [
                    {"title": "MOE school registration", "timeline": "Check MOE website", "link": "https://www.moe.gov.sg/"},
                    {"title": "International schools", "timeline": "Apply early, waitlists common", "link": None},
                ],
            },
            "healthcare": {
                "overview": "Efficient public and private hospitals. Register at a polyclinic or private GP.",
                "emergency": "995",
                "topics": [
                    {"title": "Emergency", "timeline": "995", "link": None},
                    {"title": "Non-emergency", "timeline": "1777", "link": None},
                ],
            },
            "transport": {
                "overview": "MRT and buses run by SBS Transit / SMRT. EZ-Link or bank cards for fares.",
                "platforms": [
                    {"title": "SMRT / SBS Transit", "url": "https://www.smrt.com.sg/", "description": "Public transport"},
                    {"title": "Grab", "url": "https://www.grab.com/sg/", "description": "Rideshare and food"},
                ],
            },
            "daily_life": {
                "overview": "Hawker centres, supermarkets (NTUC, Cold Storage), and delivery apps.",
                "items": [
                    {"title": "Food delivery", "description": "GrabFood, Deliveroo, Foodpanda"},
                    {"title": "Banking", "description": "DBS, OCBC, UOB"},
                    {"title": "Mobile", "description": "Singtel, StarHub, M1"},
                ],
            },
            "community": {
                "overview": "Active expat community. Many professional and social groups.",
                "groups": [
                    {"title": "Internations Singapore", "url": "https://www.internations.org/singapore-expats", "description": "Expat meetups"},
                    {"title": "Meetup Singapore", "url": "https://www.meetup.com/cities/sg/singapore/", "description": "Events and groups"},
                ],
            },
            "culture_leisure": {
                "overview": "Gardens by the Bay, museums, Sentosa, and year-round events.",
                "items": [
                    {"title": "Gardens by the Bay", "description": "Gardens and conservatories", "url": "https://www.gardensbythebay.com.sg/"},
                    {"title": "National Gallery", "description": "Southeast Asian art", "url": "https://www.nationalgallery.sg/"},
                ],
            },
            "nature": {
                "overview": "East Coast Park, MacRitchie Reservoir, Pulau Ubin. Hot and humid; bring water.",
                "items": [
                    {"title": "East Coast Park", "description": "Beach, cycling, BBQ pits"},
                    {"title": "MacRitchie Reservoir", "description": "Hiking, treetop walk"},
                ],
            },
            "cost_of_living": {
                "items": [
                    {"label": "Average rent (1-bed condo)", "value": "~2,500–4,000 SGD"},
                    {"label": "Monthly transport", "value": "~120–150 SGD"},
                    {"label": "Groceries (monthly)", "value": "~400–700 SGD"},
                    {"label": "Restaurant meal", "value": "~15–50 SGD"},
                ],
            },
            "safety": {
                "emergency": "995",
                "tips": [
                    "Emergency: 995 (ambulance), 999 (police)",
                    "Very safe; low crime",
                    "Strict drug laws",
                ],
            },
        }
        if section_key in sg_defaults:
            return sg_defaults[section_key]

    # United States–specific content (NYC / SF as examples)
    if c == "US":
        us_defaults = {
            "welcome": {
                "intro": "The US varies greatly by region. Major cities are diverse, fast-paced, and English-speaking.",
                "cultural_tips": [
                    "Punctuality varies by region",
                    "Direct communication common",
                    "Federal holidays: Thanksgiving, July 4th, etc.",
                    "State laws differ; check your state",
                ],
                "work_culture": ["Hours vary by industry", "At-will employment common", "Benefits through employer"],
            },
            "admin_essentials": {
                "topics": [
                    {"title": "Visa / work authorization", "timeline": "Before arrival", "link": "https://travel.state.gov/"},
                    {"title": "SSN (Social Security Number)", "timeline": "1–2 weeks after entry", "link": "https://www.ssa.gov/"},
                    {"title": "State ID / driver's license", "timeline": "Varies by state", "link": None},
                    {"title": "Bank account", "timeline": "First week", "link": None},
                    {"title": "Mobile plan", "timeline": "First week", "link": None},
                    {"title": "Health insurance", "timeline": "Via employer or marketplace", "link": "https://www.healthcare.gov/"},
                ],
            },
            "housing": {
                "overview": "Rental markets vary by city. Zillow, Apartments.com, and local brokers. Security deposit typically 1–2 months.",
                "platforms": [
                    {"title": "Zillow", "url": "https://www.zillow.com/", "description": "Rentals and sales"},
                    {"title": "Apartments.com", "url": "https://www.apartments.com/", "description": "Rental listings"},
                ],
                "neighborhoods": ["Varies by city"],
            },
            "schools": {
                "overview": "Public (free), private, and international schools. District-based for public. Apply early for private.",
                "school_types": ["Public", "Charter", "Private", "International"],
                "topics": [
                    {"title": "School district registration", "timeline": "Varies by district", "link": None},
                    {"title": "Immunization records", "timeline": "Required for enrollment", "link": None},
                ],
            },
            "healthcare": {
                "overview": "Employer-sponsored insurance typical. ER for emergencies. Urgent care for non-life-threatening.",
                "emergency": "911",
                "topics": [
                    {"title": "Emergency", "timeline": "911", "link": None},
                    {"title": "Primary care", "timeline": "Register with PCP", "link": None},
                ],
            },
            "transport": {
                "overview": "Public transit in major cities (NYC MTA, SF BART). Car often needed elsewhere.",
                "platforms": [
                    {"title": "MTA (NYC)", "url": "https://new.mta.info/", "description": "NYC transit"},
                    {"title": "BART (SF)", "url": "https://www.bart.gov/", "description": "Bay Area transit"},
                ],
            },
            "daily_life": {
                "overview": "Supermarkets (Whole Foods, Trader Joe's, local chains), Amazon, delivery apps.",
                "items": [
                    {"title": "Food delivery", "description": "DoorDash, Uber Eats, Instacart"},
                    {"title": "Banking", "description": "Chase, Bank of America, local credit unions"},
                    {"title": "Mobile", "description": "Verizon, AT&T, T-Mobile"},
                ],
            },
            "community": {
                "overview": "Expat and professional networks. Meetup, LinkedIn, and city-specific groups.",
                "groups": [
                    {"title": "Internations US cities", "url": "https://www.internations.org/", "description": "Expat meetups"},
                    {"title": "Meetup", "url": "https://www.meetup.com/", "description": "Events and groups"},
                ],
            },
            "culture_leisure": {
                "overview": "Museums, sports, concerts, and year-round events. City-specific offerings.",
                "items": [
                    {"title": "Museums & venues", "description": "Check city tourism sites", "url": None},
                    {"title": "Ticketmaster", "url": "https://www.ticketmaster.com/", "description": "Concerts and events"},
                ],
            },
            "nature": {
                "overview": "National parks, state parks, beaches. Varies greatly by region.",
                "items": [
                    {"title": "National Park Service", "url": "https://www.nps.gov/", "description": "Parks and recreation"},
                ],
            },
            "cost_of_living": {
                "items": [
                    {"label": "Average rent (1-bed, varies)", "value": "~1,500–3,500 USD"},
                    {"label": "Monthly transport", "value": "~100–150 USD (transit)"},
                    {"label": "Groceries (monthly)", "value": "~400–700 USD"},
                    {"label": "Restaurant meal", "value": "~15–40 USD"},
                ],
            },
            "safety": {
                "emergency": "911",
                "tips": [
                    "Emergency: 911",
                    "Register with embassy/consulate",
                    "Weather varies by region",
                ],
            },
        }
        if section_key in us_defaults:
            return us_defaults[section_key]

    # Generic defaults
    defaults = {
        "welcome": {
            "intro": "Practical guidance for your relocation.",
            "cultural_tips": ["Punctuality is valued", "Formal communication initially", "Check local public holidays"],
            "work_culture": ["Standard hours vary by sector", "Meetings often scheduled in advance"],
        },
        "admin_essentials": {
            "topics": [
                {"title": "Residence registration", "timeline": "Within 7-14 days", "link": None},
                {"title": "Tax identification", "timeline": "1-4 weeks", "link": None},
                {"title": "Bank account", "timeline": "1-2 weeks", "link": None},
                {"title": "Mobile plan", "timeline": "First week", "link": None},
                {"title": "Healthcare registration", "timeline": "First month", "link": None},
            ],
        },
        "housing": {
            "overview": "Rental market information will appear here.",
            "platforms": [],
            "neighborhoods": [],
        },
        "schools": {
            "overview": "School and childcare options for families.",
            "school_types": ["Public", "International", "Private"],
        },
        "healthcare": {
            "overview": "Healthcare system and registration.",
            "emergency": "112",
        },
        "transport": {
            "overview": "Public transport and mobility.",
        },
        "daily_life": {
            "overview": "Groceries, banking, mobile, postal services.",
        },
        "community": {
            "overview": "Expat communities and networking.",
            "groups": [],
        },
        "culture_leisure": {
            "overview": "Museums, events, and culture.",
            "events": [],
        },
        "nature": {
            "overview": "Parks, hiking, outdoor activities.",
        },
        "cost_of_living": {
            "items": [
                {"label": "Average rent", "value": "—"},
                {"label": "Transport pass", "value": "—"},
                {"label": "Groceries (monthly)", "value": "—"},
            ],
        },
        "safety": {
            "emergency": "112",
            "tips": ["Keep emergency numbers handy", "Register with embassy"],
        },
    }
    return defaults.get(section_key, {"overview": ""})
