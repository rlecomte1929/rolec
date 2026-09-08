#!/usr/bin/env python3
"""
Seed 11 additional destination countries — B14 / AIQ-282.

Brings ``public.country_profiles`` from 14 (current) to 25+ rows so the HR
Resources picker covers the EU mid-market corridors the audit flagged as
mandatory (France, Netherlands, Spain) plus the Americas + Asia round-out
(Mexico, China) and the Nordic/Anglo-EU set (Sweden, Denmark, Ireland,
Poland, Belgium, Portugal).

Idempotent: each insert is gated on a ``WHERE NOT EXISTS`` clause keyed on
``country_code``. Re-running prints "skipped — already present" for each row
that already exists. Safe to run on dev, staging, and production.

Usage
-----
::

    DATABASE_URL=postgresql://user:pass@host:port/postgres \\
      python3 scripts/seed_additional_countries.py

Or, for a dry run that only prints what *would* be inserted::

    DATABASE_URL=... python3 scripts/seed_additional_countries.py --dry-run

Exit codes
----------
* 0 — at least one row inserted **or** all rows already present (no work needed)
* 1 — DB connection failed or an insert raised

This script was written for AIQ-282 (B14 country expansion 12 → 25+).
The corresponding HR-facing surface is ``GET /api/admin/countries``
(``backend/app/routers/admin.py``). The frontend HR Resources picker reads
from the same table.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ───────────────────────────────────────────────────────────────────────────
# Curated country data
# ───────────────────────────────────────────────────────────────────────────
#
# Schema reference (matches live ``public.country_profiles``):
#   id (varchar PK)              — generated via gen_random_uuid()
#   country_code (varchar)       — uppercase full English name; matches the
#                                  existing convention ('AUSTRALIA',
#                                  'UNITED ARAB EMIRATES', etc.)
#   last_updated_at (timestamp)  — now()
#   confidence_score (float)     — 0.7 for curated-but-not-crawl-verified
#                                  (matches the audit's confidence guidance)
#   notes (text)                 — HOUSING / IMMIGRATION / COST OF LIVING /
#                                  RECOMMENDED SERVICES / PRACTICAL TIPS,
#                                  mirroring the JAPAN/CANADA/UAE templates
#
# Numbers below are intentionally directional rather than authoritative —
# anchor points for HR conversations, not legal/tax advice. The
# country_resources Resources CMS and the requirement_items table carry the
# operational detail downstream.

COUNTRIES: List[Tuple[str, str]] = [
    (
        "FRANCE",
        "REGION: Western Europe. CURRENCY: EUR (€). LANGUAGE: French. CAPITAL: Paris. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Paris remains tight — 1-bed in arrondissements 1–8/16: €1,800–€3,000/month; family 3-bed in inner Paris: €3,500–€6,000+. Inner-suburb alternatives (Neuilly, Boulogne, Levallois) cheaper by 15–25%. Lyon and Marseille: 40–55% of Paris rent. Most rentals unfurnished; 'meublé' (furnished) carries a 10–20% premium and shorter leases. Standard deposit: 1 month unfurnished, 2 months furnished.\n\n"
        "IMMIGRATION: 'Passeport Talent' multi-year permit (4 years, renewable) is the standard corporate route — covers Salarié Qualifié, EU Blue Card, and ICT variants. Minimum salary: 1.8× SMIC for Salarié Qualifié; 1.5× annual average wage for EU Blue Card. Total timeline: 4–8 weeks online + 2–4 weeks consulate. OFII medical visit on arrival is mandatory within 3 months. EU/EEA employees: no permit needed, just sécurité sociale registration.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): national 80–85; Paris itself sits at 100. Income tax progressive (0–45%) plus social charges (~22% employee-side); gross-up tables essential.\n\n"
        "RECOMMENDED SERVICES: (1) Relocation agent with French immigration desk for Passeport Talent. (2) Furnished short-stay provider for the first 30–60 days while the unfurnished hunt runs. (3) French school advisory (lycée international vs international schools). (4) Tax advisor familiar with the 'régime des impatriés' — meaningful tax exemption window for inbound assignees. (5) French-fluent destination services for utility setup and CAF/sécurité sociale registration.\n\n"
        "PRACTICAL TIPS: (1) Bank account requires a justificatif de domicile — interim solution: Wise/Revolut for first 30 days. (2) Carte Vitale (health card) takes 6–8 weeks; keep European Health Insurance Card or company top-up during the gap. (3) Apartment hunting is dossier-based — full income proof + guarantor (or company guarantee). (4) August is dead for everything — paperwork, viewings, even some doctors. Plan moves Sept–Nov or Jan–March. (5) Régime des impatriés requires election in the first year — coordinate with payroll early."
    ),
    (
        "NETHERLANDS",
        "REGION: Western Europe. CURRENCY: EUR (€). LANGUAGE: Dutch (English widely used). CAPITAL: Amsterdam. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Amsterdam expat areas (Centrum, Oud-Zuid, Jordaan, De Pijp): 1-bed €1,800–€2,800/month; 3-bed family €3,000–€5,500. Suburb hubs (Amstelveen, Diemen, Haarlem) 20–35% cheaper. Rotterdam, Eindhoven, The Hague: 30–45% of Amsterdam premium. Furnished stock limited; most leases unfurnished. Many landlords require employer letter + 1–3 months deposit.\n\n"
        "IMMIGRATION: Highly Skilled Migrant (HSM) permit is the dominant corporate route — recognised sponsor required (employer registers with IND once). Minimum monthly salary (2026): €5,688 for 30+; €4,171 for under 30; €3,008 for recent EU graduates. Timeline: 2–4 weeks for sponsor applications. EU Blue Card alternative for higher mobility within EU. EU/EEA: no permit. UK post-Brexit: HSM applies.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Amsterdam ~100–105; rest of NL 80–90. Income tax progressive (37–49.5%). '30% ruling' tax exemption available to inbound recruits meeting salary threshold and 'specific expertise' test — substantial value, must be applied for within first 4 months.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration desk for HSM filings (employer's sponsor registration is one-time but file is per-employee). (2) Amsterdam rental agent with corporate access — DIY market is tight and slow. (3) Tax advisor for 30% ruling application. (4) Dutch school placement (public schools excellent; international schools long waitlists in Amsterdam/The Hague). (5) BSN (citizen number) registration and DigiD setup support for first week.\n\n"
        "PRACTICAL TIPS: (1) BSN registration at the gemeente in the first 5 working days — everything else (bank, payroll, health insurance) is blocked until BSN exists. (2) Health insurance (basisverzekering) mandatory within 4 months of arrival; ~€140/month. (3) 30% ruling applies for up to 5 years — payroll must enroll, employee must apply (joint application). (4) Bikes are infrastructure, not recreation — budget €300–€600 for a decent commuter, lock 10–20% of bike value. (5) Apartment hunting via Pararius/Funda is competitive; have dossier ready (passport, contract, salary slip, employer letter) before viewings."
    ),
    (
        "SPAIN",
        "REGION: Southern Europe. CURRENCY: EUR (€). LANGUAGE: Spanish (Catalan in Catalonia). CAPITAL: Madrid. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Madrid expat hubs (Salamanca, Chamberí, Retiro): 1-bed €1,300–€2,000; 3-bed €2,500–€4,500. Barcelona (Eixample, Gràcia, Sarrià): 1-bed €1,200–€1,900; 3-bed €2,400–€4,200. Both markets tightened ~10% YoY in 2025–2026. Furnished is the norm for short-term; unfurnished standard for 12-month+ contracts. Deposit: 1–2 months.\n\n"
        "IMMIGRATION: ICT permit ('Traslado Intra-Corporativo') for established employees — requires 9 months prior employment at sending entity, up to 3 years renewable. 'Highly Qualified Professional' permit for direct hires earning above sector threshold. Spain Startup Act extends fast-track residence for tech profiles. Timeline: 4–12 weeks online; consular step adds 2–4 weeks. EU/EEA: no permit.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Madrid 70–75; Barcelona 75–80; rest of Spain 55–65. Income tax progressive (national + regional), broadly comparable to France but with the 'Beckham Law' (Régimen Especial) — 24% flat rate on Spanish-sourced income for up to 6 years for inbound assignees meeting criteria. Major incentive for senior packages.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration lawyer for Beckham Law election + permit filing. (2) Bilingual relocation agent (DIY market is opaque without Spanish). (3) International school advisory — Madrid and Barcelona both have strong British/American/French schools but capacity tight. (4) Tax advisor specialised in Régimen Especial. (5) NIE (foreigner ID) acquisition support — must be done in person or via consulate before arrival.\n\n"
        "PRACTICAL TIPS: (1) NIE is required for everything — bank, lease, payroll. Schedule consular appointment 4–8 weeks before move. (2) Empadronamiento (town hall registration) needed within 30 days — also a prerequisite for healthcare. (3) Beckham Law application has a 6-month window from start date — payroll must coordinate. (4) Working hours are shifted — many offices 9:30–18:30 with a long lunch; brief employees adjusting from northern Europe. (5) Catalan in Catalonia is widely used in schooling and bureaucracy — factor into Barcelona school choice."
    ),
    (
        "PORTUGAL",
        "REGION: Southern Europe. CURRENCY: EUR (€). LANGUAGE: Portuguese. CAPITAL: Lisbon. TIMEZONE: WET/WEST (UTC+0/+1).\n\n"
        "HOUSING: Lisbon centre (Príncipe Real, Chiado, Avenida da Liberdade, Estrela): 1-bed €1,400–€2,200; 3-bed €2,500–€4,500. Cascais/Estoril (coast, ~30 min west): 10–20% premium for family-sized stock. Porto: ~55–65% of Lisbon rent. Furnished common in city centre, less so in suburbs. Market remains tight after 5 years of tech-driven inflow; vacancy under 2%.\n\n"
        "IMMIGRATION: D8 'Digital Nomad' visa available for remote workers ≥ 4× minimum wage. D3 'Highly Qualified Activity' visa for corporate hires. Standard residence permit timeline: 2–4 months consular + AIMA (formerly SEF) appointment after arrival. EU/EEA: registration only.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Lisbon 65–70; Porto 55–60; rest of Portugal 45–55. Income tax progressive (14.5–48%). The historic Non-Habitual Resident (NHR) flat-rate regime was closed to new entrants in 2024 — current inbound regime is the IFICI (Innovation/Investment) replacement, narrower scope and harder to qualify. Tax advisor essential.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration lawyer for D3/D8 routing and AIMA scheduling. (2) Lisbon rental agent with corporate stock — tight market punishes DIY. (3) International school advisory (Lisbon has 5–6 strong international options; capacity tight). (4) Tax advisor for IFICI eligibility and the new vs old regime decision. (5) NIF (tax number) acquisition support — needed before lease and bank.\n\n"
        "PRACTICAL TIPS: (1) NIF first — without it, no lease, no bank, no utilities. Available via fiscal rep before arrival. (2) AIMA appointments are scarce — book the moment the visa is approved. (3) NHR is closed; do not budget on it. IFICI rules are stricter — confirm eligibility before signing the package. (4) Healthcare: SNS public system is broad but slow; most expats add private (Médis, Multicare) at €40–€100/month. (5) Portuguese is required for many bureaucratic interactions despite Lisbon's English fluency — destination services pays back fast."
    ),
    (
        "BELGIUM",
        "REGION: Western Europe. CURRENCY: EUR (€). LANGUAGE: Dutch (Flemish), French, German. CAPITAL: Brussels. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Brussels expat areas (Ixelles, Uccle, Woluwe-Saint-Pierre, Etterbeek): 1-bed €1,000–€1,600; 3-bed family €1,800–€3,200. Antwerp: 70–80% of Brussels rent. Most rentals unfurnished; 9-year lease common (employee can break early with 1–3 months notice). Deposit held in escrow account, not landlord.\n\n"
        "IMMIGRATION: Single Permit ('combined work + residence') is the dominant corporate route. Regional competence (Flemish, Walloon, Brussels) decides processing — Flanders/Brussels typically 4–8 weeks, Wallonia 6–10. EU Blue Card threshold: €60,594/year (2026). EU/EEA: registration only.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Brussels 85–90; Antwerp 75–80. Income tax very progressive (25–50%) with extra municipal surcharge (~7%). The 'Special Tax Regime for Inbound Taxpayers and Researchers' (introduced 2022, refined 2024) allows up to 30% non-taxable expense reimbursement subject to a salary floor (€75,000 in 2026) and 5-year horizon. Major saver if the package qualifies.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration counsel for Single Permit at the right regional authority. (2) Tax advisor for the Inbound Special Regime election (joint employer-employee application). (3) Brussels-area relocation agent with corporate stock — international schools are clustered, housing choice depends on school. (4) International school advisory — BSB, ISB, ISF; tight capacity. (5) Health insurer (mutualité) registration support — choice of mutuality is a Belgian-specific quirk.\n\n"
        "PRACTICAL TIPS: (1) Commune registration within 8 working days — police visit follows to verify residency. (2) Choose between French- and Dutch-speaking schools deliberately — Brussels is bilingual but specific institutions are not. (3) Special Inbound Regime requires the joint application within 6 months — payroll must be on board. (4) Bank requires national register number (acquired at commune registration). (5) Brussels traffic is among Europe's worst — proximity to school + metro/tram line matters more than apartment grade."
    ),
    (
        "SWEDEN",
        "REGION: Northern Europe. CURRENCY: SEK (kr). LANGUAGE: Swedish (English widely used). CAPITAL: Stockholm. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Stockholm rental market is famously constrained — first-hand (förstahandskontrakt) leases have multi-year queues. Expats use second-hand (andrahandskontrakt) at premium: 1-bed SEK 14,000–22,000/month (~€1,250–€1,950); 3-bed SEK 22,000–35,000. Gothenburg and Malmö: ~70% of Stockholm. Most rentals furnished or partly furnished.\n\n"
        "IMMIGRATION: Work permit ('arbetstillstånd') is the standard route. Online application via Migrationsverket. Minimum salary 80% of Swedish median (SEK 28,480/month gross in 2026). Processing: 2–6 months — long enough that the audit's MVG-6 7-day deadline warnings need adjustment. EU/EEA: no permit; right of residence after 3 months. UK post-Brexit: work permit applies.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Stockholm 100–105; Gothenburg/Malmö 90–95. Income tax very high (~32% municipal + 20% national above SEK 614k in 2026). 'Expert Tax Relief' available for inbound recruits in qualifying expert roles — 25% of income exempt for 7 years (up from 5 in 2024 reform). Application via Forskarskattenämnden within 3 months of arrival.\n\n"
        "RECOMMENDED SERVICES: (1) Migrationsverket-experienced immigration lawyer — long timelines reward early filing. (2) Stockholm housing service (Diplomatic Lettings, Blocket Pro) — DIY is brutal. (3) Tax advisor for Expert Tax Relief application. (4) International school advisory (SIS, BISS); Swedish public schools also excellent for early years. (5) Personal Identity Number (personnummer) facilitation — gate to everything.\n\n"
        "PRACTICAL TIPS: (1) Personnummer is the universal key — bank, healthcare, even gym membership. Apply at Skatteverket immediately after arrival. (2) BankID (digital identity) is the second gate — flows from personnummer; required for most online services. (3) Expert Tax Relief: 3-month application window from arrival; payroll coordination needed. (4) Winter is dark — December has 5–6 hours of daylight in Stockholm. Brief employees from southern climates on vitamin D, light therapy, and seasonal mood. (5) Cash is essentially dead — Swish (mobile payments) is the default. Set up first week."
    ),
    (
        "DENMARK",
        "REGION: Northern Europe. CURRENCY: DKK (kr). LANGUAGE: Danish (English widely used). CAPITAL: Copenhagen. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Copenhagen expat areas (Frederiksberg, Østerbro, Nørrebro, Vesterbro): 1-bed DKK 11,000–17,000/month (~€1,475–€2,280); 3-bed family DKK 18,000–32,000. Aarhus: 60–70% of Copenhagen. Furnished rare in long-term stock; corporate housing services bridge the first 60–90 days. Cooperative housing (andelsbolig) is a Danish-specific quirk — buy-in fee, not pure rental.\n\n"
        "IMMIGRATION: 'Fast-Track Scheme' for certified employers — work + residence permit in 1–4 weeks for qualifying employees (salary threshold DKK 510,000/year in 2026, or 'Researcher' / 'Educational' tracks). Pay Limit Scheme for direct hires above DKK 514,000. EU/EEA: no permit. UK post-Brexit: scheme applies.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Copenhagen 105–110; Aarhus 95–100. Income tax very high — total marginal rate ~55–57%. The 'Researcher Tax Scheme' (forskerskatteordning) offers a flat 32.84% (27% + 8% labour market contribution) for 7 years on qualifying salaries (DKK 75,100/month in 2026). Application via SKAT within 1 month of starting.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration counsel for Fast-Track certification (employer-side) and individual filing. (2) Tax advisor for Researcher Tax Scheme — material upside if the package qualifies. (3) Copenhagen relocation agent — bilingual stock is corporate-only and not on Boligportal. (4) International school placement (CIS, Rygaards, Copenhagen International School). (5) CPR number (central person register) facilitation — first-week priority.\n\n"
        "PRACTICAL TIPS: (1) CPR number is everything — apply at International House Copenhagen as soon as the residence card is issued. (2) MitID (digital ID, successor to NemID) is universal — banking, healthcare, government. Flows from CPR. (3) Researcher Tax Scheme has a hard 1-month registration window — payroll must move quickly. (4) Bicycle is mainstream transport — 60% of Copenhageners commute by bike year-round; brief employees on winter cycling. (5) Healthcare via the 'sygesikringsbevis' (yellow card) follows CPR; choose GP at registration."
    ),
    (
        "IRELAND",
        "REGION: Western Europe. CURRENCY: EUR (€). LANGUAGE: English (Irish official). CAPITAL: Dublin. TIMEZONE: GMT/IST (UTC+0/+1).\n\n"
        "HOUSING: Dublin remains tight — 1-bed in D2/D4 €1,900–€2,800/month; 3-bed family €2,800–€4,800. South-county Dublin (Dún Laoghaire, Sandymount, Blackrock) for school-led decisions. Cork and Galway: ~55–65% of Dublin rent. Most leases unfurnished long-term; furnished 'corporate lets' available at 15–25% premium for first 30–90 days. Daft.ie and Rent.ie dominate listings.\n\n"
        "IMMIGRATION: Critical Skills Employment Permit (CSEP) is the standard corporate route — fast-track to permanent residency (2 years). Salary threshold: €38,000 for occupations on the Critical Skills Occupations List, €64,000 for any other role. Intra-Company Transfer permit for transfers earning above €46,000. Timeline: 6–12 weeks. EU/EEA: no permit.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Dublin 100–105; Cork/Galway 80–90. Income tax progressive (20–40%) plus PRSI and USC (Universal Social Charge). 'Special Assignee Relief Programme' (SARP) — 30% of income above €100,000 exempt from income tax for up to 5 years for qualifying inbound assignees. Payroll-led election; tight eligibility.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration solicitor for CSEP filing and Stamp 1 → Stamp 4 progression. (2) Tax advisor for SARP eligibility (joint application). (3) Dublin relocation agent — competitive market punishes DIY first-time searchers. (4) International school advisory — Dublin has a dense international school cluster (St Andrew's, Sutton Park, Lycée Français, etc.). (5) PPS (Personal Public Service) number facilitation — gate to everything else.\n\n"
        "PRACTICAL TIPS: (1) PPS number is the universal key — book the appointment via mywelfare.ie before arrival if possible. (2) Bank account requires PPS + proof of address — interim Revolut/N26 covers the gap. (3) SARP claim: payroll must coordinate, employee must sign declaration. (4) Health insurance: public HSE coverage is broad but slow; nearly all expats add private (Irish Life Health, Laya, VHI) at €100–€250/month. (5) Driving licence: most EU/EEA licences exchangeable; UK post-Brexit requires road test."
    ),
    (
        "POLAND",
        "REGION: Central Europe. CURRENCY: PLN (zł). LANGUAGE: Polish (English in major cities). CAPITAL: Warsaw. TIMEZONE: CET/CEST.\n\n"
        "HOUSING: Warsaw (Śródmieście, Mokotów, Powiśle): 1-bed PLN 4,500–7,500/month (~€1,070–€1,790); 3-bed family PLN 7,500–14,000. Krakow: 70–80% of Warsaw. Wrocław, Poznań, Gdańsk: 60–70%. Furnished standard for expat corporate stock; 12-month leases typical. Deposit: 1–3 months.\n\n"
        "IMMIGRATION: Single Permit ('Zezwolenie jednolite') is the standard corporate route. EU Blue Card available above PLN 142,000/year (2026). 'Type A' work permit for employer-sponsored hires. Processing has improved post-2024 reform: 4–12 weeks typical. EU/EEA: registration only.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Warsaw 55–60; other major cities 45–55. Income tax progressive (12–32%) with a substantial PIT-free allowance. ZUS (social security) employer contribution adds ~20%. No analogous special inbound regime; standard rules apply.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration lawyer for Single Permit and Blue Card routing. (2) Warsaw/Krakow relocation agent — non-Polish-speaking DIY is hard. (3) International school advisory — Warsaw has AAW, BSW; Krakow has BISC; capacity tight. (4) PESEL (national ID) facilitation — required for almost everything. (5) Tax advisor for cross-border specifics (Poland enforces aggressively on remote-work residency).\n\n"
        "PRACTICAL TIPS: (1) PESEL via municipality after arrival; takes 1–4 weeks. (2) Banking requires PESEL + residence card; some banks (Citi Handlowy, mBank) accept earlier with passport + employment contract. (3) Health insurance through NFZ (public) flows automatically once ZUS is active; private top-up (Medicover, LUX MED) is standard at PLN 200–400/month. (4) Winter is real — January temperatures 0 to –10 °C in Warsaw, brief southern hires accordingly. (5) Polish bureaucracy rewards in-person presence at the right office; budget destination-services time generously."
    ),
    (
        "MEXICO",
        "REGION: North America. CURRENCY: MXN ($). LANGUAGE: Spanish. CAPITAL: Mexico City. TIMEZONE: CST/CDT (UTC-6/-5).\n\n"
        "HOUSING: Mexico City expat hubs (Polanco, Lomas de Chapultepec, Roma, Condesa): 2-bed MXN 35,000–80,000/month (~$1,900–$4,400); premium 3-bed in Polanco MXN 80,000–180,000. Monterrey (Valle, San Pedro): MXN 25,000–60,000 for 2-bed. Furnished common in expat-grade buildings; corporate housing services standard for first 60–90 days. Deposits typically 1 month + insurance bond.\n\n"
        "IMMIGRATION: 'Visa de Residente Temporal' for assignments >180 days — issued at the consulate before arrival, then exchanged for Temporary Resident Card at INM after entry. Employer-sponsored 'Permission to Work' authorisation required. Timeline: 4–8 weeks consular + 30–45 days post-arrival INM processing. Renewable up to 4 years, after which Permanent Resident pathway opens. Business visa for assignments <180 days.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Mexico City 55–65; Monterrey 50–60; smaller cities 35–45. Income tax progressive (1.92–35%) plus IMSS social contributions. Brief expat regime under 'Programa de Repatriación' is narrow and rarely applies to inbound non-Mexicans — standard rules dominate.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration agency familiar with INM and the consular ↔ post-arrival handoff. (2) Bilingual relocation agent in CDMX or Monterrey — corporate stock is opaque to outsiders. (3) International school advisory — CDMX has American, French, German, British schools; family decisions often drive neighborhood choice. (4) Driver service for first 30 days — CDMX traffic + altitude (2,240 m) is a real adjustment. (5) Security advisor for site-specific risk briefings — varies sharply by neighborhood.\n\n"
        "PRACTICAL TIPS: (1) RFC (tax ID) and CURP (personal ID) needed for bank, payroll, lease — start week 1. (2) Altitude affects newcomers for 1–3 weeks — brief on hydration and limited cardio during adjustment. (3) Earthquake protocol — CDMX is seismic; brief employees on building drills and apartment safety features. (4) Healthcare: IMSS public is broad but slow; private hospitals (ABC, Médica Sur, Ángeles) are world-class and standard in expat packages. (5) Driving licence: most foreign licences accepted for 6 months; CDMX issuance is straightforward after that."
    ),
    (
        "CHINA",
        "REGION: East Asia. CURRENCY: CNY (¥). LANGUAGE: Mandarin (Putonghua). CAPITAL: Beijing. TIMEZONE: CST (UTC+8, no DST).\n\n"
        "HOUSING: Shanghai expat hubs (Jing'an, Xuhui French Concession, Pudong Lujiazui): 2-bed CNY 18,000–40,000/month (~$2,500–$5,500); premium 3-bed villas in compounds CNY 35,000–90,000. Beijing (Chaoyang, Sanlitun, Shunyi for families): CNY 16,000–45,000 for 2-bed. Furnished standard for expat-grade stock; serviced apartments common for first 60–90 days. Most leases 1–3 years; 1 month deposit + 1 month broker fee.\n\n"
        "IMMIGRATION: Z work visa is the standard corporate route — invitation letter + Foreigner Work Permit Notice (employer files), then Z visa at consulate, then Residence Permit converted within 30 days of arrival. Skill scoring system (A/B/C tiers) gates eligibility — Class A: senior/specialist; Class B: standard professional; Class C: temporary/seasonal. Timeline: 6–10 weeks total. PU letter system has been retired; standard process restored fully.\n\n"
        "COST OF LIVING vs PARIS (Paris=100): Shanghai 80–90; Beijing 75–85; Shenzhen 75–85; tier-2 cities 50–60. Income tax progressive (3–45%). The 6-year residency rule and the Greater Bay Area tax rebate for Hong Kong-bordering employees are the two material levers — tax advisor essential.\n\n"
        "RECOMMENDED SERVICES: (1) Immigration agency with FESCO/CIIC employer-of-record relationship if direct sponsorship isn't possible. (2) Bilingual destination service — banking, mobile, residence registration all require local navigation. (3) International school placement (Shanghai American, Dulwich, Yew Chung, etc.) — capacity tight; apply 12 months ahead. (4) Tax advisor for IIT structuring and the 6-year rule. (5) VPN and tech stack briefing — employees need pre-approved tools for company access (most western SaaS is blocked).\n\n"
        "PRACTICAL TIPS: (1) Residence registration at the local police station within 24 hours of arrival/move — strictly enforced; landlord usually assists. (2) Health check at the designated entry-exit inspection bureau is part of residence permit conversion — book in week 1. (3) WeChat is infrastructure — payment, messaging, services, even building access. Set up before arrival. (4) Air quality varies by city/season — Beijing winter, Chengdu year-round; budget for air purifiers in housing. (5) Internet: corporate VPN for work systems; personal usage adjusts — brief employees calmly on what changes."
    ),
]

# ───────────────────────────────────────────────────────────────────────────
# SQL & main loop
# ───────────────────────────────────────────────────────────────────────────

INSERT_SQL = """
INSERT INTO public.country_profiles (id, country_code, last_updated_at, confidence_score, notes)
SELECT gen_random_uuid()::text, %(code)s, NOW(), 0.70, %(notes)s
WHERE NOT EXISTS (
    SELECT 1 FROM public.country_profiles WHERE country_code = %(code)s
)
"""


def _load_dotenv_if_present() -> None:
    """Allow ``python scripts/seed_additional_countries.py`` to pick up .env locally."""
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Connect to DB but do not execute INSERTs; print what would happen.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (falls back to the env var).",
    )
    args = parser.parse_args(argv)

    _load_dotenv_if_present()
    db_url = args.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "ERROR: DATABASE_URL not set. Either pass --database-url=... or "
            "export DATABASE_URL (Supabase pooler URL works).",
            file=sys.stderr,
        )
        return 1

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print(
            "ERROR: psycopg2 is required. Install with: pip install psycopg2-binary",
            file=sys.stderr,
        )
        return 1

    print(f"Seeding {len(COUNTRIES)} additional country_profiles rows.")
    print(f"  Target: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"  Mode:   {'DRY RUN' if args.dry_run else 'apply'}")
    print()

    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: cannot connect to Postgres: {exc}", file=sys.stderr)
        return 1

    inserted = 0
    skipped = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM public.country_profiles;"
            )
            row = cur.fetchone()
            before = int((row or {}).get("n", 0))
            print(f"Before: {before} country_profiles rows.")

            for code, notes in COUNTRIES:
                cur.execute(
                    "SELECT 1 FROM public.country_profiles WHERE country_code = %s LIMIT 1",
                    (code,),
                )
                if cur.fetchone():
                    print(f"  skip   {code:<22} — already present")
                    skipped += 1
                    continue
                if args.dry_run:
                    print(f"  would  {code:<22} ({len(notes)} chars of notes)")
                    inserted += 1
                    continue
                cur.execute(INSERT_SQL, {"code": code, "notes": notes})
                print(f"  insert {code:<22} ({len(notes)} chars of notes)")
                inserted += 1

            if not args.dry_run:
                conn.commit()

            cur.execute(
                "SELECT COUNT(*) AS n FROM public.country_profiles;"
            )
            row = cur.fetchone()
            after = int((row or {}).get("n", 0))

        print()
        print(f"Inserted:           {inserted}")
        print(f"Skipped (existing): {skipped}")
        print(f"After:              {after} country_profiles rows.")
        if after < 25 and not args.dry_run:
            print(
                "WARNING: post-seed total is below 25 — expected ≥ 25. "
                "Check that earlier seeds ran on this DB.",
                file=sys.stderr,
            )
        return 0
    except Exception as exc:  # noqa: BLE001 — script wants a final hard stop
        conn.rollback()
        print(f"ERROR during seed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
