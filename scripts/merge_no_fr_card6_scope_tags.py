#!/usr/bin/env python3
"""Apply the Card 6 patch: nationality_scope_basis on 12 records, and quotes where they verify.

WHY THIS EXISTS. Every record in the NO→FR batch was tagged `nationality: "EEA"` or `"non-EEA"`
with no `nationality_scope_basis`, and the serving layer gates on that field. Our reference mover
Denis is a FRENCH national returning to France — an OWN_NATIONAL, which matches neither label —
so he was served ZERO of the 17. The 5 records the patch tags `audience_scope` are the ones that
reach him.

THE QUOTE RULE, and why it is not "trust the patch". The patch marks 11 of its 12 records
`quote_verbatim_confirmed: true`. Six of those do not appear on the page they cite, and two of
the six are records whose quote ALREADY VERIFIES on `main` — taking the patch wholesale would
have moved the batch backwards. So a quote is taken only when it verifies against the page it
cites; otherwise the existing quote stays, and where neither verifies the record stays
unconfirmed. Scope tags are taken in every case: they are the research this patch was for, and
they are judged from the source rather than machine-checkable.

The one under-claim goes the other way: `no_fr_eea_sejour_card_validity_employee_cdi` was
delivered `false` because a `titleContent` tooltip token sits mid-sentence on service-public.fr.
Our normaliser already strips that token, so the quote does verify and is taken.

Nothing here is invented: every field comes from the patch or is left as it was.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BATCH = REPO / "docs/imports/no-fr-general-curated-2026-08-22"
STREAM = BATCH / "no-fr-general-curated-2026-08-22.ndjson"
PATCH = BATCH / "raw/no-fr-card6-patch-2026-08-23.ndjson"

#: Copied onto applies_to when the patch supplies a non-empty value.
#: Otto's nationality vocabulary drifts between batches. "EEA/EU/Swiss" is the same CLASS as
#: "EEA", but it is not a label the matcher knows, and an unrecognised label FAILS OPEN — so
#: six nationality_determined records silently reached everyone, including the returning French
#: national they do not apply to. Canonicalise on the way in; the matcher also learns the alias
#: so the next batch cannot un-gate itself the same way.
NATIONALITY_ALIASES = {"EEA/EU/Swiss": "EEA", "EU/EEA/Swiss": "EEA", "EEA/EU": "EEA"}

SCOPE_FIELDS = (
    "nationality_scope_basis", "nationality", "scope_justification", "own_national_note",
    "assertion_mode", "conditional_on", "non_obvious", "non_obvious_note",
    "needs_lawyer_review",
)


def norm_for_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("v", REPO / "scripts/verify_batch_quotes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    v = norm_for_check()
    rows = [json.loads(l) for l in STREAM.read_text().splitlines() if l.strip()]
    patch = {json.loads(l)["fact_key"]: json.loads(l)
             for l in PATCH.read_text().splitlines() if l.strip()}

    unknown = set(patch) - {r["fact_key"] for r in rows}
    if unknown:
        raise SystemExit(f"patch names fact_keys not in the batch: {sorted(unknown)}")

    # Page text for every URL either side cites, from the batch's own archived sources plus
    # anything the patch newly cites (fetched on demand).
    index = json.loads((BATCH / "sources/index.json").read_text())
    pages = {u: v.norm((BATCH / "sources" / m["file"]).read_text()) for u, m in index.items()}
    for fix in patch.values():
        url = fix["citation_url"]
        if url not in pages:
            pages[url] = v.norm(v.to_text(v.fetch(url)))

    taken = kept = 0
    for row in rows:
        fix = patch.get(row["fact_key"])
        if not fix:
            continue
        applies_to = row.setdefault("applies_to", {})
        for field in SCOPE_FIELDS:
            value = fix.get(field)
            if value not in (None, ""):
                if field == "nationality":
                    value = NATIONALITY_ALIASES.get(str(value), value)
                applies_to[field] = value

        patch_ok = v.norm(fix["evidence_quote"]) in pages.get(fix["citation_url"], "")
        if patch_ok:
            applies_to["superseded_source_url"] = row["source_url"]
            row["source_url"] = fix["citation_url"]
            row["evidence_quote"] = fix["evidence_quote"]
            taken += 1
        else:
            applies_to["card6_quote_rejected"] = (
                "patch proposed a quote at " + fix["citation_url"]
                + " that does not appear on that page; existing citation kept"
            )
            kept += 1

    STREAM.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    tagged = sum(1 for r in rows if r["applies_to"].get("nationality_scope_basis"))
    print(f"scope-tagged {tagged}/{len(rows)} · quotes taken {taken} · quotes kept {kept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
