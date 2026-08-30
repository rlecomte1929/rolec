#!/usr/bin/env python3
"""Corrections to the NO→FR batch once the reference scenario was settled.

Denis is **permanent France-based work**, not a posting. He holds a Norwegian contract today and
expects to leave it for French employment. That single answer decides three of the five facts he
would be served, so it is recorded here rather than left implicit.

1. THE REMAINING FIVE RECORDS ARE SCOPE-TAGGED. They are attributes of the same
   `eea_residence_card` entity whose siblings the Card 6 research already tagged
   `nationality_determined` — the optional card, its fee, the self-employed validity, the ANEF
   application route — plus the EEA no-visa rule. Applying the same tag to siblings of one entity
   is carrying an existing decision across, not making a new one. A French national in France
   needs none of them: the burden never existed, so it is not an exemption he holds.

2. THE A1 / POSTED-WORKER RECORD BECOMES CONDITIONAL. It is a real rule and it is genuinely
   corridor-wide — posting does not turn on nationality — but it applies only on the posting
   branch, and Denis is not on it. Serving it flat tells a permanent local hire to obtain a
   certificate that does not exist for him. `assertion_mode: conditional` is exactly the case the
   serving layer already renders as "Applies only in certain cases" with its condition shown, so
   the rule stays visible to whoever IS posted without being asserted at whoever is not.

3. THE DUPLICATE ARTICLE 4B RECORD IS DROPPED. `_cgf_4b__eea` and `_cgf_4b__non_eea` were
   byte-identical in `fact_text`, `evidence_quote` and `source_url`, and both `audience_scope`, so
   every mover read the same paragraph twice. Article 4B does not vary by nationality — which is
   why both ended up audience_scope, and why the split was never meaningful. One is kept.

4. THE FALSE COUNT IN THAT RECORD IS CORRECTED. Its text said "any one of four criteria" and then
   enumerated three. The count is removed rather than a fourth invented: the quote does carry a
   fourth category (State agents abroad), but adding it is authoring, and this file does not
   author.

5. THE NIR RECORD IS FLAGGED, NOT REWRITTEN. Its `fact_text` asserts the DPAE mechanism,
   automatic assignment and an 8-day filing rule. Its quote establishes only that residence plus
   work makes affiliation compulsory — it says nothing about NIR assignment, DPAE, or eight days.
   That is a claim-exceeds-quote gap, which no gate in this repo currently catches: the checker
   proves the quote is on the page, and nothing checks the claim against the quote. Denis is also
   a French national, who in the ordinary case already holds a NIR from birth and needs it
   recovered rather than assigned. Both need a source, so the row is marked for review and left
   for re-sourcing; narrowing the text here would be authoring a legal claim from a gap.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STREAM = (REPO / "docs/imports/no-fr-general-curated-2026-08-22"
          / "no-fr-general-curated-2026-08-22.ndjson")

#: Siblings of the already-tagged `eea_residence_card` records, plus the EEA no-visa rule.
SCOPE_TAG_REMAINING = {
    "no_fr_eea_sejour_card_optional_workers",
    "no_fr_eea_sejour_card_fee_free",
    "no_fr_eea_sejour_card_validity_self_employed",
    "no_fr_eea_sejour_card_application_anef",
    "no_fr_france_eea_no_visa_required",
}

A1 = "no_fr_urssaf_posted_worker_a1_certificate"
NIR = "no_fr_france_numero_secu_ss_number_assignment"
KEEP_4B, DROP_4B = ("no_fr_france_tax_domicile_trigger_cgf_4b__eea",
                    "no_fr_france_tax_domicile_trigger_cgf_4b__non_eea")


def main() -> int:
    rows = [json.loads(l) for l in STREAM.read_text().splitlines() if l.strip()]
    by_key = {r["fact_key"]: r for r in rows}

    for key in SCOPE_TAG_REMAINING:
        applies_to = by_key[key]["applies_to"]
        applies_to["nationality_scope_basis"] = "nationality_determined"
        applies_to["scope_justification"] = (
            "Attribute of the carte de séjour 'citoyen UE/EEE/Suisse', a right that exists "
            "because the holder is an EEA national. Same basis as the sibling records tagged by "
            "the Card 6 research on this entity."
        )
        applies_to["own_national_note"] = (
            "Does not reach a French national in France: a citizen needs no residence document "
            "at all, so this is not an exemption he holds — the requirement never applied."
        )

    a1 = by_key[A1]["applies_to"]
    a1["assertion_mode"] = "conditional"
    a1["conditional_on"] = (
        "Applies only where the move is a genuine temporary posting (détachement) and the "
        "Norwegian institution issues the A1. It does not apply to permanent France-based work, "
        "where French social security applies from the start under Reg. 883/2004 art. 11(3)(a)."
    )
    a1["non_obvious"] = True
    a1["non_obvious_note"] = (
        "Commonly assumed that anyone moving from Norway with a Norwegian employer needs an A1. "
        "The A1 belongs to posting, not to relocation: a permanent local move is covered by the "
        "state where the work is done. Action required: establish whether this is a posting "
        "before treating the A1 as a step, because the wrong branch changes who pays "
        "contributions and where."
    )

    nir = by_key[NIR]["applies_to"]
    nir["needs_lawyer_review"] = True
    nir["claim_exceeds_quote"] = (
        "fact_text asserts the DPAE mechanism, automatic NIR assignment and an 8-day filing "
        "deadline; the quote establishes only that lawful residence plus work makes affiliation "
        "compulsory. It also does not address a French national who already holds a NIR from "
        "birth and needs it recovered rather than assigned. Re-source before promotion."
    )

    keep = by_key[KEEP_4B]["applies_to"]
    keep["deduplicated_from"] = DROP_4B
    keep["dedupe_note"] = (
        "An identical record was carried under a '_non_eea' key. CGI art. 4B does not vary by "
        "nationality, so the split was never meaningful and every mover read the paragraph twice."
    )
    by_key[KEEP_4B]["fact_text"] = by_key[KEEP_4B]["fact_text"].replace(
        "if any one of four criteria is met", "if any one of the following criteria is met")

    rows = [r for r in rows if r["fact_key"] != DROP_4B]
    STREAM.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    tagged = sum(1 for r in rows if r["applies_to"].get("nationality_scope_basis"))
    print(f"records {len(rows)} (dropped 1 duplicate) · scope-tagged {tagged}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
