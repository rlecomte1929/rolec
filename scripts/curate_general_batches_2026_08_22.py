#!/usr/bin/env python3
"""Curate Otto's refused es-ie-general / no-fr-general batches into loadable candidates.

Otto delivered 53 facts on branch fix/td-qa-services-batch-0719 (2026-08-21) with
`applies_to.nationality` null on every record — the loader refuses null nationality by
design (mappings.NATIONALITY_CLASSES; "categorise or refuse"). The corridor campaign will
have Otto re-deliver under the contract, but the Andrea (ES→IE) and Denis (NO→FR) demo
cases need the loadable subset now. This script is the audit trail for that curation:

  raw JSONL (verbatim from the branch, committed under <batch>/raw/)
    → per-fact disposition table (CURATION below — every decision is a code-reviewable line)
    → curated NDJSON + manifest + gate report

Curation rules (docs/otto/andrea-denis-brief-2026-08-21.md §3, the contract of record):
  * nationality is READ FROM THE FACT'S OWN TEXT, never inferred from the corridor. The
    justification string on every row quotes the reading.
  * a truly universal obligation becomes TWO records (audience "both" → `__eea` /
    `__non_eea` twins) — there is no "applies to all" value, deliberately.
  * promotion groups facts by entity_topic_key and REFUSES mixed-audience groups
    (mappings._one_value), so topics are re-keyed to requirement granularity and twins get
    distinct topic keys AND distinct group titles — the natural key
    (country_code, purpose, title) is UNIQUE as of migration 20261117000000, so twin
    requirements must never share a title.
  * fact_type "step" records leave the fact stream (steps are the pathway graphs') —
    they land in the README as step candidates.
  * origin-side obligations (Norway exit duties in a destination-FR file) belong in
    corridors/NO_FR/facts.yaml, not in FRANCE requirement_items — routed to the README
    as origin candidates for the D2 Otto task.
  * the self-employment sub-corpus is DEFERRED (both movers are employees; the A1/D1
    Otto re-delivery re-scopes it) — preserved verbatim in raw/, listed in the README.
  * quote_verbatim_confirmed is set to false on every curated record: nobody has yet
    re-verified the quotes against the pages, so every fact grades needs_review. Honest.

Run:  python scripts/curate_general_batches_2026_08_22.py        # writes curated files
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

EEA_SUFFIX = " (EU/EEA nationals)"
NON_EEA_SUFFIX = " (non-EEA nationals)"

# action: load | step | origin | defer
# load rows: (action, final_or_base_topic, audience, group_title, justification)
#   audience "both" → the topic is a base; twins <topic>_eea / <topic>_non_eea are emitted.
#   audience "EEA"/"non-EEA" → the topic given is FINAL (may join a twin group).
ES_IE = {
    "es_ie_non_eea_work_permit_required_over_90_days": (
        "load", "work_permission_non_eea", "non-EEA",
        "Work Permission Requirement for Non-EEA Workers (Ireland)",
        "fact_text: obligation on non-EEA nationals; EU/EEA explicitly excluded → non-EEA"),
    "es_ie_isd_registration_mandatory_non_eu_only": (
        "load", "irp_registration_non_eea", "non-EEA",
        "IRP / ISD Immigration Registration (non-EEA nationals)",
        "fact_text: applies only to nationals outside EU/UK/Switzerland → non-EEA"),
    "es_ie_irp_card_issued_on_registration": (
        "load", "irp_registration_non_eea", "non-EEA",
        "IRP / ISD Immigration Registration (non-EEA nationals)",
        "fact_text: card issued to registering non-EEA nationals; EU nationals not issued → non-EEA"),
    "es_ie_isd_registration_90_day_deadline": (
        "load", "irp_registration_non_eea", "non-EEA",
        "IRP / ISD Immigration Registration (non-EEA nationals)",
        "fact_text: 90-day registration duty for non-EEA nationals who need permission → non-EEA"),
    "es_ie_pps_number_definition": (
        "load", "ppsn_application", "both",
        "PPS Number — Application and Uses",
        "PPSN is required of every resident accessing services regardless of passport → universal, two records"),
    "es_ie_pps_number_required_for_employment": (
        "load", "ppsn_application", "both",
        "PPS Number — Application and Uses",
        "mandatory when starting work in Ireland, no nationality condition stated → universal, two records"),
    "es_ie_pps_number_mandatory_services": (
        "load", "ppsn_application", "both",
        "PPS Number — Application and Uses",
        "required across public services for all residents → universal, two records"),
    "es_ie_pps_number_identity_proof_eu_citizen": (
        "load", "ppsn_application_eea", "EEA",
        "PPS Number — Application and Uses",
        "fact_text: identity-proof rule stated for EU citizens (passport or national ID) → EEA only"),
    "es_ie_pps_number_proof_of_address_requirements": (
        "load", "ppsn_application", "both",
        "PPS Number — Application and Uses",
        "proof-of-address rule applies to every applicant → universal, two records"),
    "es_ie_pps_number_online_application_mygov_id": (
        "step", None, None, None, "how-to-apply sequence → pathway step candidate, not a requirement fact"),
    "es_ie_prsi_employer_requires_pps_number": (
        "step", None, None, None, "payroll sequencing (employer needs PPSN before PRSI) → step candidate"),
    "es_ie_self_employed_must_register_with_revenue": (
        "defer", None, None, None, "self-employment sub-corpus; both movers are employees"),
    "es_ie_self_employed_ros_mandatory_if_eligible": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_business_name_registration_cro_one_month": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_self_employed_mandatory_record_keeping": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_self_assessment_preliminary_tax_october_31": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_self_employed_form_11_tax_return": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_self_employed_earned_income_tax_credit_2025": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_irish_income_tax_rates_2025_2026": (
        "load", "income_tax_basics", "both",
        "Irish Income Tax — Rates and Bands",
        "tax rates apply to every taxpayer regardless of passport → universal, two records"),
    "es_ie_prsi_class_s_self_employed": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_prsi_compulsory_most_workers": (
        "load", "prsi_social_insurance", "both",
        "PRSI — Compulsory Social Insurance",
        "compulsory for most employees over 16, no nationality condition → universal, two records"),
    "es_ie_prsi_unearned_income_rate_oct_2025": (
        "load", "prsi_social_insurance", "both",
        "PRSI — Compulsory Social Insurance",
        "unearned-income PRSI applies to chargeable persons generally → universal, two records"),
    "es_ie_prsi_rate_increase_october_2026": (
        "load", "prsi_social_insurance", "both",
        "PRSI — Compulsory Social Insurance",
        "rate change applies across all PRSI classes → universal, two records"),
    "es_ie_prsi_self_employed_included_in_self_assessment": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_a1_certificate_posted_worker_spain_to_ireland": (
        "load", "a1_posted_worker_eea", "EEA",
        "A1 Certificate — Posted Workers from Spain",
        "EU social-security coordination instrument as published (Reg 883/2004 framing). Whether it "
        "extends to third-country nationals for IRELAND (Reg 1231/2010 opt-outs) is a legal "
        "determination — NOT asserted here; see README open questions"),
    "es_ie_usc_threshold_13000": (
        "load", "usc_universal_social_charge", "both",
        "Universal Social Charge — Threshold",
        "USC applies to all persons over the income threshold → universal, two records"),
    "es_ie_usc_self_employed_surcharge_over_100k": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_usc_paid_with_preliminary_tax": (
        "defer", None, None, None, "self-employment sub-corpus (and a payment-sequence step)"),
    "es_ie_vat_registration_threshold_self_employed": (
        "defer", None, None, None, "self-employment sub-corpus"),
    "es_ie_ordinary_residence_required_for_hse_entitlement": (
        "load", "health_entitlements", "both",
        "Public Health Entitlement — Ordinary Residence",
        "ordinarily-resident test governs every person's HSE entitlement → universal, two records"),
    "es_ie_two_tier_health_eligibility": (
        "load", "health_entitlements", "both",
        "Public Health Entitlement — Ordinary Residence",
        "the two eligibility categories cover all ordinarily-resident persons → universal, two records"),
    "es_ie_eu_citizen_medical_card_posted_worker_e106": (
        "step", None, None, None, "E106/S-form submission sequence → step candidate (EEA posted workers)"),
    "es_ie_eu_citizen_medical_card_eu_pension_basis": (
        "load", "health_entitlements_eea", "EEA",
        "Public Health Entitlement — Ordinary Residence",
        "fact_text: medical-card route under EU rules for EU/EEA citizens → EEA only"),
}

NO_FR = {
    "no_fr_eea_sejour_card_optional_workers": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "fact_text: card available to EEA nationals working in France, not mandatory → EEA"),
    "no_fr_eea_sejour_card_three_conditions": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "eligibility conditions of the EEA card → EEA"),
    "no_fr_eea_sejour_card_fee_free": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "fee attribute of the EEA card → EEA"),
    "no_fr_eea_sejour_card_validity_employee_cdi": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "validity attribute of the EEA card → EEA"),
    "no_fr_eea_sejour_card_validity_self_employed": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "validity attribute of the same EEA card (self-employed variant of the card, kept with its card) → EEA"),
    "no_fr_eea_sejour_card_application_anef": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "where-to-apply attribute of the EEA card → EEA"),
    "no_fr_eea_sejour_card_documents_employee": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "document list of the EEA card → EEA"),
    "no_fr_eea_sejour_card_documents_self_employed": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "document list of the same EEA card → EEA"),
    "no_fr_eea_sejour_card_permanent_residence_5yr": (
        "load", "eea_residence_card", "EEA",
        "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
        "permanent-residence right of EEA nationals after 5 years → EEA"),
    "no_fr_non_eea_worker_work_permit_required": (
        "load", "work_authorization_non_eea", "non-EEA",
        "Work Authorization for Non-EEA Workers (France)",
        "fact_text: autorisation de travail required for non-EEA hires; Norwegians explicitly exempt → non-EEA"),
    "no_fr_norway_folkeregister_deregistration_obligation": (
        "origin", None, None, None,
        "Norway-side exit duty (Folkeregisteret emigration notice) → corridors/NO_FR/facts.yaml origin fact (Otto D2)"),
    "no_fr_france_eea_no_visa_required": (
        "load", "entry_no_visa_eea", "EEA",
        "Entry to France — No Visa for EEA Nationals",
        "fact_text: EEA citizens enter and reside without a visa → EEA"),
    "no_fr_norway_must_notify_move_abroad_skatteetaten": (
        "origin", None, None, None,
        "Norway-side exit duty (Skatteetaten move-abroad notice) → origin fact (Otto D2)"),
    "no_fr_urssaf_self_employed_registration_obligation": (
        "defer", None, None, None, "self-employment sub-corpus (Guichet unique registration); also a sequence step"),
    "no_fr_urssaf_posted_worker_a1_certificate": (
        "load", "a1_posted_worker_eea", "EEA",
        "A1 Certificate — Workers Posted from Norway",
        "EEA social-security coordination instrument as published → EEA"),
    "no_fr_france_numero_secu_ss_number_assignment": (
        "load", "french_social_security_number_eea", "EEA",
        "French Social Security Number (NIR) — Assignment",
        "fact_text describes the automatic DPAE-triggered mechanism for EEA employees → EEA (the "
        "universal first sentence is not separable from the EEA mechanism it documents)"),
    "no_fr_france_eea_right_to_remain_unemployed": (
        "load", "eea_unemployment_residence_right", "EEA",
        "EEA Residence Right if Involuntarily Unemployed",
        "fact_text: retention of residence right by EEA nationals → EEA"),
    "no_fr_norway_tax_4_year_rule": (
        "origin", None, None, None,
        "Norway-side exit rule (Skatteloven §2-1(3) continued tax liability) → origin fact (Otto D2)"),
    "no_fr_france_tax_domicile_trigger_cgf_4b": (
        "load", "french_tax_domicile", "both",
        "French Tax Domicile — CGI Article 4B",
        "Art. 4B fiscal-domicile criteria apply to any person meeting them regardless of passport → universal, two records"),
    "no_fr_eu_eea_single_state_principle_reg_883_2004": (
        "load", "social_security_single_state_eea", "EEA",
        "Single-State Social Security Principle (Reg. 883/2004)",
        "coordination rule between EEA states, applicable via the EEA Agreement → EEA"),
}

BATCHES = [
    {
        "raw": "docs/imports/es-ie-general-curated-2026-08-22/raw/es-ie-general-2026-08-21.jsonl",
        "out_dir": "docs/imports/es-ie-general-curated-2026-08-22",
        "batch_id": "es-ie-general-curated-2026-08-22",
        "table": ES_IE,
        "corridor": "ES-IE", "origin": "ES", "destination": "IE",
        "target_country": "IRELAND",
    },
    {
        "raw": "docs/imports/no-fr-general-curated-2026-08-22/raw/no-fr-general-2026-08-21.jsonl",
        "out_dir": "docs/imports/no-fr-general-curated-2026-08-22",
        "batch_id": "no-fr-general-curated-2026-08-22",
        "table": NO_FR,
        "corridor": "NO-FR", "origin": "NO", "destination": "FR",
        "target_country": "FRANCE",
    },
]


def _twin(record: dict, topic_base: str, audience_value: str, suffix: str, title: str) -> dict:
    out = json.loads(json.dumps(record))  # deep copy
    out["fact_key"] = record["fact_key"] + ("__eea" if audience_value in ("EEA", "EU") else "__non_eea")
    out["entity_topic_key"] = topic_base + ("_eea" if audience_value in ("EEA", "EU") else "_non_eea")
    out["entity_title"] = title + suffix
    out["applies_to"] = dict(record.get("applies_to") or {})
    out["applies_to"]["nationality"] = audience_value
    return out


def curate(batch: dict) -> dict:
    raw_path = REPO / batch["raw"]
    table = batch["table"]
    curated, steps, origins, deferred = [], [], [], []
    raw_lines = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    seen = set()
    for rec in raw_lines:
        key = rec["fact_key"]
        if key not in table:
            raise SystemExit(f"UNCURATED fact_key in {raw_path.name}: {key}")
        seen.add(key)
        action, topic, audience, title, why = table[key]
        if action == "step":
            steps.append((rec, why))
            continue
        if action == "origin":
            origins.append((rec, why))
            continue
        if action == "defer":
            deferred.append((rec, why))
            continue
        base = dict(rec)
        base["applies_to"] = dict(rec.get("applies_to") or {})
        base["applies_to"].update({
            "status": "professional",
            "quote_verbatim_confirmed": False,
            "curation_justification": why,
        })
        if audience == "both":
            for aud, suffix in (("EEA", EEA_SUFFIX), ("non-EEA", NON_EEA_SUFFIX)):
                curated.append(_twin(base, topic, aud, suffix, title))
        else:
            out = dict(base)
            out["entity_topic_key"] = topic
            suffix = EEA_SUFFIX if audience == "EEA" and topic.endswith("_eea") else (
                NON_EEA_SUFFIX if topic.endswith("_non_eea") else "")
            out["entity_title"] = title + suffix
            out["applies_to"] = dict(base["applies_to"])
            out["applies_to"]["nationality"] = audience
            curated.append(out)
    missing = set(table) - seen
    if missing:
        raise SystemExit(f"curation table names fact_keys absent from {raw_path.name}: {missing}")

    out_dir = REPO / batch["out_dir"]
    ndjson_name = batch["batch_id"] + ".ndjson"
    ndjson_path = out_dir / ndjson_name
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in curated) + "\n"
    ndjson_path.write_text(payload)
    sha = hashlib.sha256(payload.encode()).hexdigest()

    manifest = {
        "batch_id": batch["batch_id"],
        "generated_at": "2026-08-22",
        "generated_by": "claude-code curation of otto raw batch (see raw/ + this script)",
        "curation_script": "scripts/curate_general_batches_2026_08_22.py",
        "raw_artifact": batch["raw"].split("/")[-1],
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "corridor": batch["corridor"],
        "origin_country_code": batch["origin"],
        "destination_country_code": batch["destination"],
        "nationality_class": "MIXED — per-record applies_to.nationality (EEA / non-EEA; universal facts are twinned)",
        "target_table": "public.requirement_items (via otto_staging; candidates only)",
        "target_country_code": batch["target_country"],
        "record_count": len(curated),
        "raw_record_count": len(raw_lines),
        "step_candidates": len(steps),
        "origin_candidates": len(origins),
        "deferred": len(deferred),
        "artifact": ndjson_name,
        "sha256": sha,
        "review_status_all": "pending",
        "verification_status_all": "representative",
        "scope": ("Curated, nationality-scoped subset of Otto's refused general batch. Covers "
                  "employed-mover destination requirements only; steps routed to pathway-graph "
                  "candidates, origin-side duties routed to corridors/<id>/facts.yaml candidates, "
                  "self-employment sub-corpus deferred to the Otto re-delivery (AIQ-1833). Must "
                  "reconcile: curated + steps + origin + deferred == raw_record_count "
                  "(twinned records counted once via their base fact_key)."),
        "load_task": "AIQ-1833",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    # reconciliation: every raw fact is accounted for exactly once
    base_keys = {r["fact_key"].replace("__eea", "").replace("__non_eea", "") for r in curated}
    accounted = len(base_keys) + len(steps) + len(origins) + len(deferred)
    assert accounted == len(raw_lines), (accounted, len(raw_lines))
    return {"batch": batch["batch_id"], "raw": len(raw_lines), "curated_records": len(curated),
            "loaded_base_facts": len(base_keys), "steps": len(steps), "origin": len(origins),
            "deferred": len(deferred), "sha256": sha,
            "steps_list": [(r["fact_key"], w) for r, w in steps],
            "origin_list": [(r["fact_key"], w) for r, w in origins],
            "deferred_list": [(r["fact_key"], w) for r, w in deferred]}


def main() -> None:
    reports = [curate(b) for b in BATCHES]
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
