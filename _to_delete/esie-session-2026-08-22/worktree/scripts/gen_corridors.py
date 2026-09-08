#!/usr/bin/env python3
"""Generate destination-corridor form_template seed migrations for the E2E
personas (ES, US, NL, SG, JP, CH, AE), mirroring the NO/GB/DE sets.

Each corridor = a skilled-worker route: work-route forms on
destination_confirmed (these fire for a `work` case), post-arrival registration,
and family-reunion forms gated on has_spouse / has_children. Field rosters are
representative STARTER sets per category (the trigger only needs the template +
conditions; ops/legal refine fields later). Real authorities per country.

Writes one supabase/migrations/*.sql per corridor (idempotent INSERTs) and also
prints the combined SQL to stdout for MCP apply.
"""
import json
import os

# Compact starter field rosters per category (id, label, type, required,
# prefill_source). Starter sets — ops/legal refine against the official form.
FIELDS = {
    "work_permit": [
        ("full_name", "Full legal name", "text", True, "profile.legal_full_name"),
        ("passport_number", "Passport number", "text", True, "profile.passport_number"),
        ("employer_name", "Employer", "text", True, "contract.employer_name"),
        ("salary_amount", "Gross annual salary", "number", True, "contract.salary_amount"),
    ],
    "registration": [
        ("full_name", "Full legal name", "text", True, "profile.legal_full_name"),
        ("local_address", "Local residential address", "text", True, "profile.destination_address"),
    ],
    "tax": [
        ("full_name", "Full legal name", "text", True, "profile.legal_full_name"),
        ("employer_name", "Employer", "text", True, "contract.employer_name"),
    ],
    "health": [
        ("full_name", "Full legal name", "text", True, "profile.legal_full_name"),
        ("dependents_count", "Dependents to cover", "number", False, "family.dependent_count"),
    ],
    "banking": [
        ("full_name", "Full legal name", "text", True, "profile.legal_full_name"),
        ("local_address", "Local residential address", "text", True, "profile.destination_address"),
    ],
    "family_spouse": [
        ("spouse_full_name", "Spouse full legal name", "text", True, "family.spouse.legal_full_name"),
        ("sponsor_full_name", "Sponsor (employee) name", "text", True, "profile.legal_full_name"),
    ],
    "family_child": [
        ("child_full_name", "Child full legal name", "text", True, "person.legal_full_name"),
        ("sponsor_full_name", "Sponsor (employee) name", "text", True, "profile.legal_full_name"),
    ],
}


def fields_json(kind):
    arr = []
    for i, (fid, label, ftype, req, src) in enumerate(FIELDS[kind], start=1):
        arr.append({"id": fid, "label": label, "type": ftype, "required": req,
                    "prefill_source": src, "requires_original": False, "position": i})
    return json.dumps(arr)


# Corridor specs: code, name, authority_code, authority_name, category,
# event(d=destination_confirmed, a=arrival_confirmed, p=profile_completed),
# skilled_worker?(only on d work forms), person(employee/spouse/each_child),
# fields-kind.
E = {"d": "roadmap.destination_confirmed", "a": "roadmap.arrival_confirmed", "p": "roadmap.profile_completed"}

CORRIDORS = {
    "ES": ("Spain", "20260610030000_seed_es_form_templates", [
        ("ES-WORK-VISA", "Work/residence visa (Visado de trabajo)", "OEX", "Oficina de Extranjeria", "work_permit", "d", True, "employee"),
        ("ES-TIE", "Foreigner ID card (TIE)", "POLICIA", "Policia Nacional - Extranjeria", "work_permit", "d", True, "employee"),
        ("ES-NIE", "Foreigner ID number (NIE)", "POLICIA", "Policia Nacional", "registration", "d", False, "employee"),
        ("ES-SS", "Social Security number (Seguridad Social)", "TGSS", "Tesoreria General de la Seguridad Social", "tax", "d", False, "employee"),
        ("ES-EMPADRON", "Town registration (Empadronamiento)", "AYUNTAMIENTO", "Ayuntamiento", "registration", "a", False, "employee"),
        ("ES-BANK", "Spanish bank account", "ES-BANK", "Spanish retail bank", "banking", "a", False, "employee"),
        ("ES-FAM-SPOUSE", "Family reunification - spouse (Reagrupacion)", "OEX", "Oficina de Extranjeria", "family_spouse", "p", False, "spouse"),
        ("ES-FAM-CHILD", "Family reunification - child (Reagrupacion)", "OEX", "Oficina de Extranjeria", "family_child", "p", False, "each_child"),
    ]),
    "US": ("United States", "20260610040000_seed_us_form_templates", [
        ("US-PETITION", "Nonimmigrant work petition (Form I-129)", "USCIS", "US Citizenship and Immigration Services", "work_permit", "d", True, "employee"),
        ("US-VISA", "Work visa stamping (DS-160)", "DOS", "US Department of State", "work_permit", "d", True, "employee"),
        ("US-SSN", "Social Security number (SS-5)", "SSA", "Social Security Administration", "tax", "d", False, "employee"),
        ("US-I9", "Employment eligibility verification (Form I-9)", "USCIS", "US Citizenship and Immigration Services", "registration", "d", False, "employee"),
        ("US-BANK", "US bank account", "US-BANK", "US retail bank", "banking", "a", False, "employee"),
        ("US-STATE-ID", "State ID / driver license", "DMV", "State Dept of Motor Vehicles", "registration", "a", False, "employee"),
        ("US-DEP-SPOUSE", "Dependent visa - spouse (I-539/derivative)", "USCIS", "US Citizenship and Immigration Services", "family_spouse", "p", False, "spouse"),
        ("US-DEP-CHILD", "Dependent visa - child (derivative)", "USCIS", "US Citizenship and Immigration Services", "family_child", "p", False, "each_child"),
    ]),
    "NL": ("Netherlands", "20260610050000_seed_nl_form_templates", [
        ("NL-HSM", "Highly skilled migrant permit", "IND", "Immigratie- en Naturalisatiedienst", "work_permit", "d", True, "employee"),
        ("NL-MVV", "Entry visa (MVV)", "IND", "Immigratie- en Naturalisatiedienst", "work_permit", "d", True, "employee"),
        ("NL-BSN", "Citizen service number (BSN)", "GEMEENTE", "Gemeente", "registration", "d", False, "employee"),
        ("NL-30RULING", "30% ruling application", "BELASTINGDIENST", "Belastingdienst", "tax", "d", False, "employee"),
        ("NL-REGISTER", "Municipal registration (Inschrijving)", "GEMEENTE", "Gemeente", "registration", "a", False, "employee"),
        ("NL-HEALTH", "Dutch health insurance (Zorgverzekering)", "NL-HEALTH", "Dutch health insurer", "health", "a", False, "employee"),
        ("NL-FAM-SPOUSE", "Family reunification - partner", "IND", "Immigratie- en Naturalisatiedienst", "family_spouse", "p", False, "spouse"),
        ("NL-FAM-CHILD", "Family reunification - child", "IND", "Immigratie- en Naturalisatiedienst", "family_child", "p", False, "each_child"),
    ]),
    "SG": ("Singapore", "20260610060000_seed_sg_form_templates", [
        ("SG-EP", "Employment Pass (EP)", "MOM", "Ministry of Manpower", "work_permit", "d", True, "employee"),
        ("SG-FIN", "Foreign Identification Number (FIN) / NRIC", "ICA", "Immigration & Checkpoints Authority", "registration", "d", False, "employee"),
        ("SG-TAX", "Tax registration (IRAS)", "IRAS", "Inland Revenue Authority of Singapore", "tax", "d", False, "employee"),
        ("SG-BANK", "Singapore bank account", "SG-BANK", "Singapore retail bank", "banking", "a", False, "employee"),
        ("SG-TENANCY", "Tenancy / address registration", "SG-LOCAL", "Local authority", "registration", "a", False, "employee"),
        ("SG-DP-SPOUSE", "Dependant's Pass - spouse", "MOM", "Ministry of Manpower", "family_spouse", "p", False, "spouse"),
        ("SG-DP-CHILD", "Dependant's Pass - child", "MOM", "Ministry of Manpower", "family_child", "p", False, "each_child"),
    ]),
    "JP": ("Japan", "20260610070000_seed_jp_form_templates", [
        ("JP-COE", "Certificate of Eligibility (COE)", "ISA", "Immigration Services Agency of Japan", "work_permit", "d", True, "employee"),
        ("JP-WORK-VISA", "Work visa", "MOFA", "Ministry of Foreign Affairs (Japan)", "work_permit", "d", True, "employee"),
        ("JP-RESIDENCE-CARD", "Residence Card (Zairyu Card)", "ISA", "Immigration Services Agency of Japan", "registration", "d", False, "employee"),
        ("JP-MYNUMBER", "My Number registration", "JP-WARD", "Municipal ward office", "tax", "a", False, "employee"),
        ("JP-WARD", "Ward / address registration (Juminhyo)", "JP-WARD", "Municipal ward office", "registration", "a", False, "employee"),
        ("JP-BANK", "Japanese bank account", "JP-BANK", "Japanese retail bank", "banking", "a", False, "employee"),
        ("JP-DEP-SPOUSE", "Dependent visa - spouse", "ISA", "Immigration Services Agency of Japan", "family_spouse", "p", False, "spouse"),
        ("JP-DEP-CHILD", "Dependent visa - child", "ISA", "Immigration Services Agency of Japan", "family_child", "p", False, "each_child"),
    ]),
    "CH": ("Switzerland", "20260610080000_seed_ch_form_templates", [
        ("CH-PERMIT-B", "Residence/work permit (B permit)", "CANTON-MIGRATION", "Cantonal migration office", "work_permit", "d", True, "employee"),
        ("CH-WORK-AUTH", "Work authorisation (cantonal)", "CANTON-LABOUR", "Cantonal labour market authority", "work_permit", "d", True, "employee"),
        ("CH-REGISTER", "Commune registration (Anmeldung)", "GEMEINDE", "Gemeinde / Commune", "registration", "a", False, "employee"),
        ("CH-AHV", "Social insurance (AHV/AVS)", "AHV", "AHV/AVS compensation office", "tax", "d", False, "employee"),
        ("CH-HEALTH", "Mandatory health insurance (LAMal)", "CH-HEALTH", "Swiss health insurer", "health", "a", False, "employee"),
        ("CH-BANK", "Swiss bank account", "CH-BANK", "Swiss retail bank", "banking", "a", False, "employee"),
        ("CH-FAM-SPOUSE", "Family reunification - spouse", "CANTON-MIGRATION", "Cantonal migration office", "family_spouse", "p", False, "spouse"),
        ("CH-FAM-CHILD", "Family reunification - child", "CANTON-MIGRATION", "Cantonal migration office", "family_child", "p", False, "each_child"),
    ]),
    "AE": ("United Arab Emirates", "20260610090000_seed_ae_form_templates", [
        ("AE-ENTRY-PERMIT", "Employment entry permit", "GDRFA", "General Directorate of Residency and Foreigners Affairs", "work_permit", "d", True, "employee"),
        ("AE-WORK-PERMIT", "Labour card / work permit", "MOHRE", "Ministry of Human Resources & Emiratisation", "work_permit", "d", True, "employee"),
        ("AE-EMIRATES-ID", "Emirates ID", "ICP", "Federal Authority for Identity & Citizenship", "registration", "d", False, "employee"),
        ("AE-MEDICAL", "Medical fitness test", "AE-HEALTH", "DHA / approved medical centre", "health", "d", False, "employee"),
        ("AE-EJARI", "Tenancy registration (Ejari)", "AE-LOCAL", "Land Department / municipality", "registration", "a", False, "employee"),
        ("AE-BANK", "UAE bank account", "AE-BANK", "UAE retail bank", "banking", "a", False, "employee"),
        ("AE-FAM-SPOUSE", "Family sponsorship - spouse", "GDRFA", "General Directorate of Residency and Foreigners Affairs", "family_spouse", "p", False, "spouse"),
        ("AE-FAM-CHILD", "Family sponsorship - child", "GDRFA", "General Directorate of Residency and Foreigners Affairs", "family_child", "p", False, "each_child"),
    ]),
}

PRIO = {"d": 100, "a": 70, "p": 85}


def conditions(cc, event, skilled, person):
    c = {"destination_country": cc}
    if skilled:
        c["visa_type"] = "skilled_worker"
    if person == "spouse":
        c["has_spouse"] = True
    if person == "each_child":
        c["has_children"] = True
    return c


def sql_for(cc, name, forms):
    rows = []
    for code, fname, acode, aname, cat, ev, skilled, person in forms:
        fkind = cat
        cat_db = {"family_spouse": "family", "family_child": "family"}.get(cat, cat)
        rule = [{"event": E[ev], "conditions": conditions(cc, ev, skilled, person),
                 "for_persons": [person], "blocked_by_template_code": None, "priority": PRIO[ev]}]
        rows.append(
            "('{code}', $${fname}$$, '{cc}', '{acode}', $${aname}$$, '{cat}', '1.0.0', '{fields}'::jsonb, '{rules}'::jsonb)".format(
                code=code, fname=fname, cc=cc, acode=acode, aname=aname, cat=cat_db,
                fields=fields_json(fkind), rules=json.dumps(rule),
            )
        )
    header = (
        f"-- Seed {name} ({cc}) corridor form templates — skilled-worker route.\n"
        f"-- Generated by scripts/gen_corridors.py for the E2E personas. Idempotent.\n"
        "INSERT INTO public.form_templates (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules) VALUES\n"
    )
    return header + ",\n".join(rows) + "\nON CONFLICT (code, version) DO NOTHING;\n"


def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "supabase", "migrations")
    for cc, (name, fname, forms) in CORRIDORS.items():
        sql = sql_for(cc, name, forms)
        path = os.path.join(out_dir, fname + ".sql")
        with open(path, "w") as fh:
            fh.write(sql)
        print(f"# wrote {fname}.sql ({len(forms)} forms)")
    print(f"# {sum(len(v[2]) for v in CORRIDORS.values())} forms across {len(CORRIDORS)} corridors")


if __name__ == "__main__":
    main()
