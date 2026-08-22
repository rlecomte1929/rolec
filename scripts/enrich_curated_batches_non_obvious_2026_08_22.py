#!/usr/bin/env python3
"""Add `non_obvious` / `non_obvious_note` / `timing` to the two curated corridor batches.

contract: `docs/otto/andrea-denis-brief-2026-08-21.md` §3.1

**Why this exists.** `scripts/curate_general_batches_2026_08_22.py` made Otto's refused
general batches loadable — correctly nationality- and status-scoped — but it carried no
`non_obvious` flag at all. Measured against production on 2026-08-22:

    IRELAND  29 approved  12 non_obvious (41%)   6 with timing
    FRANCE   16 approved   0 non_obvious ( 0%)   0 with timing

Denis (NO→FR, French own-national) therefore sees a flat list with no "Easy to miss" badge
and no deadlines, which is the one thing the product is for. Loading the curated batches
as-is would have taken him from 6 bland requirements to ~15 bland requirements.

Enrichment happens **here, in the file, before the load** — deliberately. Once a batch is
promoted and approved, changing these columns needs a migration and a re-approval cycle;
while it is still an NDJSON it is a text edit. Load once, enriched.

**What is and is not authored here.** The flag, the note and the timing are editorial
judgement over facts that were already researched, quoted and cited. Nothing here invents a
claim, a source or a number: every `timing` restates a deadline the fact's own `fact_text`
(and therefore its `evidence_quote`) already states, and no fact's text is modified. Facts
keep `quote_verbatim_confirmed: false` — a human still confirms the quote before approval.

**The bar for `non_obvious`.** True when a competent non-expert would not know to look for
it: a cliff-edge, a circular dependency, a step whose omission is only discovered later, or
a widely-held belief that is wrong. Not true for ordinary eligibility, published rates, or
anything the requirement's own title already tells you. Calibrated against the 12 existing
IRELAND traps and the 4 NORWAY ones. Result: ES→IE 13/29 (45%), NO→FR 8/17 (47%).

**Known limit.** `non_obvious_note` has nowhere to land yet — `requirement_items` has
`non_obvious` (bool) and `timing` (text) but no note column, and `mappings.resolve` does not
carry one. The note is recorded here as the authoring record and the audit trail; surfacing
its text to the reader needs a column plus an importer change, tracked as follow-up. The
boolean and the timing DO flow today.

Idempotent: re-running rewrites the same bytes. Updates each manifest's `sha256` and records
the enrichment provenance.

    ./.venv311/bin/python scripts/enrich_curated_batches_non_obvious_2026_08_22.py --check
    ./.venv311/bin/python scripts/enrich_curated_batches_non_obvious_2026_08_22.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ── the disposition table ─────────────────────────────────────────────────────────────
#
# fact_key -> (non_obvious, note_or_None, timing_or_None, justification)
#
# `note` follows the brief's shape: "Commonly believed … Actually … Action required …".
# `timing` must restate something the fact_text already says — never a new deadline.
# A fact absent from this table is left exactly as curated (non_obvious stays unset).

DISPOSITIONS: dict[str, tuple[bool, str | None, str | None, str]] = {
    # ══ ES → IE (Andrea, third-country non-EEA; twins carry the same rule per audience) ══
    "es_ie_non_eea_work_permit_required_over_90_days": (
        True,
        "Commonly believed you can travel to Ireland on a job offer and sort the permission "
        "out after you land. Actually a non-EEA national must hold the employment contract "
        "and have applied for the work permission BEFORE arriving. Action required: start "
        "the permit application while still in Spain — arriving first does not preserve it.",
        "before arriving in Ireland",
        "The 'before arriving' ordering is the trap; the requirement itself is expected.",
    ),
    "es_ie_isd_registration_90_day_deadline": (
        True,
        "Commonly believed that if you cannot get an ISD appointment inside the 90 days your "
        "permission lapses. Actually the permission is NOT cancelled while you are waiting "
        "for an appointment. Action required: book the earliest appointment you can and keep "
        "evidence of the attempt — but do not treat a booking backlog as losing your status.",
        "within 90 days of ISD granting permission",
        "A relief moment: the widely-held belief is wrong in the mover's favour, and the "
        "anxiety it causes is real. Appointment scarcity is the lived experience.",
    ),
    "es_ie_pps_number_required_for_employment__eea": (
        True,
        "Commonly believed the PPS number is paperwork you complete at leisure after moving. "
        "Actually it is mandatory to register with Revenue when you take up employment, and "
        "an employer may not ask for it during recruitment — so it can only be obtained in "
        "the narrow window between accepting the job and starting it. Action required: apply "
        "as soon as you have an address, not once you have started work.",
        None,
        "The recruitment/employment split creates a timing squeeze nobody anticipates.",
    ),
    "es_ie_pps_number_required_for_employment__non_eea": (
        True,
        "Commonly believed the PPS number is paperwork you complete at leisure after moving. "
        "Actually it is mandatory to register with Revenue when you take up employment, and "
        "an employer may not ask for it during recruitment — so it can only be obtained in "
        "the narrow window between accepting the job and starting it. Action required: apply "
        "as soon as you have an address, not once you have started work.",
        None,
        "Twin of the EEA record; identical rule, different audience.",
    ),
    "es_ie_pps_number_proof_of_address_requirements__eea": (
        True,
        "Commonly believed you can prove your address with documents from home. Actually the "
        "proof must be an IRISH document under 3 months old showing your name and address — "
        "and a newly-arrived person has no Irish utility bill or bank statement yet, while "
        "opening a bank account normally wants the PPS number first. Action required: use one "
        "of the accepted alternatives — a signed lease, or third-party confirmation from a "
        "landlord, hotel, hostel or school principal — to break the circle.",
        "proof of address must be dated within the last 3 months",
        "The circular dependency (address proof ↔ bank account ↔ PPSN) is the single most "
        "reported arrival trap and the accepted workaround is buried in the source.",
    ),
    "es_ie_pps_number_proof_of_address_requirements__non_eea": (
        True,
        "Commonly believed you can prove your address with documents from home. Actually the "
        "proof must be an IRISH document under 3 months old showing your name and address — "
        "and a newly-arrived person has no Irish utility bill or bank statement yet, while "
        "opening a bank account normally wants the PPS number first. Action required: use one "
        "of the accepted alternatives — a signed lease, or third-party confirmation from a "
        "landlord, hotel, hostel or school principal — to break the circle.",
        "proof of address must be dated within the last 3 months",
        "Twin of the EEA record; identical rule, different audience.",
    ),
    "es_ie_prsi_unearned_income_rate_oct_2025__eea": (
        True,
        "Commonly believed PRSI is deducted from your salary and that is the end of it. "
        "Actually rent, dividends, interest and other unearned income — including income "
        "arising outside Ireland — is liable to PRSI at 4.2%, and anyone with more than "
        "€5,000 of it becomes a 'chargeable person' who must self-assess. Action required: if "
        "you kept a property or investments in Spain, check whether you must file.",
        "from 1 October 2025",
        "Salaried movers do not expect to acquire a self-assessment filing obligation.",
    ),
    "es_ie_prsi_unearned_income_rate_oct_2025__non_eea": (
        True,
        "Commonly believed PRSI is deducted from your salary and that is the end of it. "
        "Actually rent, dividends, interest and other unearned income — including income "
        "arising outside Ireland — is liable to PRSI at 4.2%, and anyone with more than "
        "€5,000 of it becomes a 'chargeable person' who must self-assess. Action required: if "
        "you kept a property or investments abroad, check whether you must file.",
        "from 1 October 2025",
        "Twin of the EEA record; identical rule, different audience.",
    ),
    "es_ie_a1_certificate_posted_worker_spain_to_ireland": (
        True,
        "Commonly believed the A1 can be arranged once the assignment is under way. Actually "
        "it must be applied for at least 4 weeks BEFORE work begins in Ireland; without it "
        "Irish social insurance applies instead of Spanish, and the two are not "
        "interchangeable. Action required: have the sending employer start the A1 a month "
        "before the first Irish working day.",
        "apply at least 4 weeks before work begins in Ireland",
        "A hard lead time stated in the source and routinely missed; the cost lands on the "
        "employee's contribution record, not the employer's.",
    ),
    "es_ie_usc_threshold_13000__eea": (
        True,
        "Commonly believed the €13,000 USC threshold works like a tax-free allowance, so only "
        "income above it is charged. Actually once gross income crosses €13,000 the USC is "
        "charged on the FULL amount, not just the excess. Action required: expect the whole "
        "of your income to attract USC as soon as you pass the threshold.",
        None,
        "A cliff edge, not a marginal band — the opposite of how every other threshold in "
        "the mover's experience behaves.",
    ),
    "es_ie_usc_threshold_13000__non_eea": (
        True,
        "Commonly believed the €13,000 USC threshold works like a tax-free allowance, so only "
        "income above it is charged. Actually once gross income crosses €13,000 the USC is "
        "charged on the FULL amount, not just the excess. Action required: expect the whole "
        "of your income to attract USC as soon as you pass the threshold.",
        None,
        "Twin of the EEA record; identical rule, different audience.",
    ),
    "es_ie_ordinary_residence_required_for_hse_entitlement__eea": (
        True,
        "Commonly believed that working and paying PRSI in Ireland entitles you to public "
        "health services straight away. Actually entitlement depends on being 'ordinarily "
        "resident' — a year's residence, or provable intent to stay a year — and the HSE can "
        "ask for utility bills, bank statements or a lease as proof. Action required: keep "
        "arrival-dated documents from day one; you may need them to prove intent.",
        "requires one year's residence, or documented intent to stay at least one year",
        "Movers conflate paying social insurance with being covered by it; the evidential "
        "burden falls on them at the worst possible moment.",
    ),
    "es_ie_ordinary_residence_required_for_hse_entitlement__non_eea": (
        True,
        "Commonly believed that working and paying PRSI in Ireland entitles you to public "
        "health services straight away. Actually entitlement depends on being 'ordinarily "
        "resident' — a year's residence, or provable intent to stay a year — and the HSE can "
        "ask for utility bills, bank statements or a lease as proof. Action required: keep "
        "arrival-dated documents from day one; you may need them to prove intent.",
        "requires one year's residence, or documented intent to stay at least one year",
        "Twin of the EEA record; identical rule, different audience.",
    ),
    # Deliberately NO timing. `mappings.resolve` takes the first timing in fact_key order
    # within a topic, and "rate_increase_october_2026" sorts before
    # "unearned_income_rate_oct_2025" — so tagging this record would put a scheduled future
    # rate change in the requirement's timing slot and displace the deadline that belongs to
    # the trap actually flagged in this topic. The 2026 date is already in the fact_text.
    "es_ie_prsi_rate_increase_october_2026__eea": (
        False, None, None,
        "A scheduled rate change is a date, not a deadline; leaving it unset lets the "
        "unearned-income rule supply this topic's timing.",
    ),
    "es_ie_prsi_rate_increase_october_2026__non_eea": (
        False, None, None,
        "A scheduled rate change is a date, not a deadline; leaving it unset lets the "
        "unearned-income rule supply this topic's timing.",
    ),

    # ══ NO → FR (Denis, EEA own-national returning to France) ══════════════════════════
    "no_fr_eea_sejour_card_optional_workers": (
        True,
        "Commonly believed that living in France requires a residence permit, so movers wait "
        "for one before doing anything else. Actually the carte de séjour is OPTIONAL for "
        "EEA nationals and free of charge — you are lawfully resident without it. Action "
        "required: do not hold up housing, banking or payroll waiting for a card you do not "
        "need.",
        None,
        "The belief is wrong in the mover's favour and the wasted delay is the real cost.",
    ),
    "no_fr_eea_sejour_card_application_anef": (
        True,
        "Commonly believed you apply for a French residence card in person at the prefecture. "
        "Actually this category is handled exclusively online through the ANEF portal and "
        "paper applications are not accepted. Action required: do not queue at a prefecture — "
        "apply on ANEF, and collect the card there only once issued.",
        None,
        "A wasted-trip trap: the prefecture is exactly where a reasonable person would go.",
    ),
    "no_fr_urssaf_posted_worker_a1_certificate": (
        True,
        "Commonly believed a short posting to France leaves your Norwegian social security "
        "untouched by default. Actually without an A1 certificate from NAV, FRENCH "
        "contributions apply from your first day in France — you can end up paying into two "
        "systems for the same work. Action required: have the Norwegian employer obtain the "
        "A1 before the first French working day.",
        "before the first day of work in France",
        "Money, immediately, and the default is the expensive one. The EEA equivalent of the "
        "ES→IE A1 trap.",
    ),
    "no_fr_france_numero_secu_ss_number_assignment": (
        True,
        "Commonly believed you apply for a French social security number yourself. Actually "
        "for an employee it is triggered by the EMPLOYER filing the DPAE with URSSAF at least "
        "8 days before your start date — if they file late or not at all, you have no NIR, "
        "and without a NIR there is no carte vitale and no reimbursement. Action required: "
        "confirm with HR that the DPAE has been filed before you start.",
        "employer must file the DPAE at least 8 days before the start of work",
        "The mover's healthcare access depends on someone else's filing deadline, which they "
        "have no visibility of and would never think to check.",
    ),
    "no_fr_france_eea_right_to_remain_unemployed": (
        True,
        "Commonly believed that as an EEA national your right to live in France is "
        "unconditional. Actually if you become involuntarily unemployed, the right past three "
        "months is retained only if you REGISTER with France Travail and stay available for "
        "work — and keeping the carte de séjour needs the termination letter or a training "
        "certificate as evidence. Action required: register immediately on losing a job and "
        "keep the paperwork.",
        "register with France Travail before the three-month mark",
        "Registration is what preserves the right; movers treat France Travail as optional "
        "job-hunting help rather than a status condition.",
    ),
    "no_fr_france_tax_domicile_trigger_cgf_4b__eea": (
        True,
        "Commonly believed French tax residency starts after 183 days. Actually Article 4B of "
        "the CGI makes you tax-resident — on WORLDWIDE income — if ANY ONE of four tests is "
        "met, including having your main home or your centre of economic interests in France. "
        "You can be French tax-resident from arrival while still being paid from Norway. "
        "Action required: establish which side taxes you before the first payslip, not at "
        "year end.",
        None,
        "The single largest financial exposure in the batch, and the 183-day belief is close "
        "to universal.",
    ),
    "no_fr_france_tax_domicile_trigger_cgf_4b__non_eea": (
        True,
        "Commonly believed French tax residency starts after 183 days. Actually Article 4B of "
        "the CGI makes you tax-resident — on WORLDWIDE income — if ANY ONE of four tests is "
        "met, including having your main home or your centre of economic interests in France. "
        "You can be French tax-resident from arrival while still being paid from abroad. "
        "Action required: establish which side taxes you before the first payslip, not at "
        "year end.",
        None,
        "Twin of the EEA record; identical rule, different audience.",
    ),
    "no_fr_eu_eea_single_state_principle_reg_883_2004": (
        True,
        "Commonly believed you can keep Norwegian cover running during the transition as a "
        "safety net. Actually Regulation 883/2004 allows only ONE country's social security "
        "to apply at a time — on a genuine relocation, France takes over and Norwegian "
        "coverage stops. Action required: do not keep paying into both, and check what "
        "lapses in Norway when it does.",
        None,
        "Paying twice for reassurance is the intuitive move and it buys nothing.",
    ),
    # timing only — a document-age constraint, not a trap in itself
    "no_fr_eea_sejour_card_documents_employee": (
        False, None, "proof of domicile must be dated within the last 6 months",
        "Stated in the document list the reader already sees.",
    ),
    "no_fr_eea_sejour_card_documents_self_employed": (
        False, None, "proof of domicile must be dated within the last 6 months",
        "Stated in the document list the reader already sees.",
    ),
}

MANAGED_KEYS = ("non_obvious", "non_obvious_note", "timing")

BATCHES = [
    "docs/imports/es-ie-general-curated-2026-08-22",
    "docs/imports/no-fr-general-curated-2026-08-22",
]


def enrich(records: list[dict], seen: set[str]) -> list[dict]:
    """Enrich one batch's records; record every fact_key encountered in `seen`.

    `seen` accumulates ACROSS batches: the disposition table spans both corridors, so a key
    is only genuinely unknown once every batch has been read.
    """
    out = []
    for rec in records:
        key = rec["fact_key"]
        seen.add(key)
        # Authoritative, not additive: the three managed keys are cleared and then re-set
        # from the table. A merge-only pass could not REMOVE a value written by an earlier
        # run, so correcting a disposition to None would silently leave the old value in the
        # file — which is exactly what happened when the PRSI 2026 timing was withdrawn.
        applies = {k: v for k, v in rec["applies_to"].items() if k not in MANAGED_KEYS}
        disp = DISPOSITIONS.get(key)
        if disp:
            non_obvious, note, timing, _why = disp
            if non_obvious:
                applies["non_obvious"] = True
                if note:
                    applies["non_obvious_note"] = note
            if timing:
                applies["timing"] = timing
        out.append({**rec, "applies_to": applies})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the files (default: check only)")
    args = ap.parse_args()

    seen: set[str] = set()
    failed = False
    for rel in BATCHES:
        d = REPO / rel
        nd = d / f"{d.name}.ndjson"
        records = [json.loads(l) for l in nd.read_text(encoding="utf-8").splitlines() if l.strip()]
        enriched = enrich(records, seen)

        flagged = sum(1 for r in enriched if r["applies_to"].get("non_obvious"))
        timed = sum(1 for r in enriched if r["applies_to"].get("timing"))
        noted = sum(1 for r in enriched
                    if r["applies_to"].get("non_obvious") and r["applies_to"].get("non_obvious_note"))

        # Every flagged record must explain itself. A badge with no reason is a claim the
        # reader cannot check — the same rule test_corridor_ie_es.py enforces on IE→ES.
        if flagged != noted:
            print(f"FAIL {d.name}: {flagged - noted} non_obvious record(s) with no note")
            failed = True

        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in enriched) + "\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        print(f"{d.name}: {len(enriched)} records, {flagged} non_obvious "
              f"({round(100*flagged/len(enriched))}%), {timed} with timing, sha256 {digest[:16]}…")

        if args.apply:
            nd.write_text(body, encoding="utf-8")
            mpath = d / "manifest.json"
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
            manifest["sha256"] = digest
            manifest["non_obvious_count"] = flagged
            manifest["timing_count"] = timed
            manifest["enrichment_script"] = (
                "scripts/enrich_curated_batches_non_obvious_2026_08_22.py")
            manifest["enrichment_note"] = (
                "non_obvious / non_obvious_note / timing added 2026-08-22 by editorial "
                "judgement over the already-cited facts. No fact_text, source_url or "
                "evidence_quote was modified; every timing restates a deadline the fact "
                "already states. quote_verbatim_confirmed remains false pending human "
                "confirmation.")
            mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    unknown = sorted(set(DISPOSITIONS) - seen)
    if unknown:
        print(f"FAIL: disposition keys matching no record: {unknown}")
        failed = True
    if failed:
        return 1
    print("OK" + ("" if args.apply else "  (check only — pass --apply to write)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
