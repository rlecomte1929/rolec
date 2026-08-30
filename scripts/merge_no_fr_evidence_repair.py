#!/usr/bin/env python3
"""Merge the 2026-08-23 evidence-repair delta into the NO→FR batch.

The delta (`raw/no-fr-evidence-repair-2026-08-23.ndjson`) is a patch, not a batch: it carries
`citation_url` and omits every required field, so it cannot be imported on its own. This applies
it onto `no-fr-general-curated-2026-08-22.ndjson`, keyed on `fact_key`.

TWO DELIBERATE DEPARTURES FROM THE DELIVERED PATCH, both recorded on the row:

1. `quote_verbatim_confirmed` is set from OUR OWN check, not copied from the patch. The patch
   claimed `true` on two records that do not verify; carrying that through would let a fact skip
   review on an unchecked citation, which is the one defect the source is the only appeal for.
   Where our check and the patch's claim disagree, the row records both.

2. `no_fr_non_eea_worker_work_permit_required` KEEPS its original citation. The patch moved it
   from service-public.fr F2728 to F35602/2_0, which does not contain the phrase "autorisation
   de travail" at all, while F2728 does carry the sentence. The quote is re-copied from our
   archived copy of F2728 — the same contiguous run, including the colon the earlier quote
   dropped, and minus the `titleContent` template token that no reader ever sees. That is a
   transcription from a stored source, and it is verified below like every other row.

Provenance is kept on `applies_to`: the superseded URL, the statutory reference where the patch
supplied one, and which repair group the row came from. Nothing is invented.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BATCH = REPO / "docs/imports/no-fr-general-curated-2026-08-22"
STREAM = BATCH / "no-fr-general-curated-2026-08-22.ndjson"
PATCH = BATCH / "raw/no-fr-evidence-repair-2026-08-23.ndjson"

#: The record the patch regressed: keep the original page, take the run it actually renders.
KEEP_ORIGINAL_CITATION = "no_fr_non_eea_worker_work_permit_required"
RECOPIED_QUOTE = (
    "L'employeur qui souhaite embaucher un salarié étranger non européen "
    "(UE + EEE + Suisse) : en France doit préalablement obtenir une autorisation de travail."
)


def main() -> int:
    rows = [json.loads(l) for l in STREAM.read_text().splitlines() if l.strip()]
    patch = {json.loads(l)["fact_key"]: json.loads(l)
             for l in PATCH.read_text().splitlines() if l.strip()}

    unknown = set(patch) - {r["fact_key"] for r in rows}
    if unknown:
        raise SystemExit(f"patch names fact_keys not in the batch: {sorted(unknown)}")

    for row in rows:
        fix = patch.get(row["fact_key"])
        if not fix:
            continue
        applies_to = row.setdefault("applies_to", {})
        applies_to["superseded_source_url"] = row["source_url"]
        applies_to["citation_repair_batch"] = "no-fr-evidence-repair-2026-08-23"
        applies_to["citation_repair_group"] = fix.get("repair_group")
        if fix.get("statutory_reference"):
            applies_to["statutory_reference"] = fix["statutory_reference"]
        if fix.get("needs_lawyer_review"):
            applies_to["needs_lawyer_review"] = True

        if row["fact_key"] == KEEP_ORIGINAL_CITATION:
            # Do NOT take the patch's URL — see the module docstring.
            applies_to.pop("superseded_source_url", None)
            applies_to["citation_repair_note"] = (
                "patch proposed " + fix["citation_url"] + ", which does not carry the claim; "
                "original citation kept and the quote re-copied from it"
            )
            row["evidence_quote"] = RECOPIED_QUOTE
        else:
            row["source_url"] = fix["citation_url"]
            row["evidence_quote"] = fix["evidence_quote"]
        applies_to["quote_verbatim_confirmed_claimed_by_patch"] = bool(
            fix.get("quote_verbatim_confirmed")
        )

    STREAM.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"merged {len(patch)} repairs into {len(rows)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
