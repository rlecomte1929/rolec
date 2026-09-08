"""
AIQ-511 — Materialize the C1 pilot fixture corpus.

Produces EXACTLY 20 synthetic dossiers on demand (binary PDFs are NOT committed):
  - 10 IN→DE  (in_de_generic + in_de_with_family + in_de_it_no_degree)
  - 10 FR→NO  (fr_no_common + fr_no_non_eea_spouse + fr_no_french_spouse)

Exactly 5 dossiers each seed one of the 5 canonical contradiction types
(one per type); the remaining 15 are clean. Fully deterministic apart from each
dossier's generation_meta.generated_at timestamp.

Run:
    cd backend && python -m tests.fixtures.pilot.materialize --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional

from tests.fixtures.pilot.generators import (
    fr_no_common,
    fr_no_french_spouse,
    fr_no_non_eea_spouse,
    in_de_generic,
    in_de_it_no_degree,
    in_de_with_family,
)


class Spec(NamedTuple):
    generate: Callable[..., dict]
    seed: int
    corridor: str
    persona: str
    contradiction: Optional[str]


# Fixed, deterministic 20-dossier plan.
# 5 contradictions (one per canonical type) live on docs that actually support
# them; the other 15 dossiers are clean.
CORPUS: List[Spec] = [
    # ---- IN→DE (10) ----
    # in_de_generic is the canonical (untouched) generator; kept clean.
    Spec(in_de_generic.generate, 1, "IN_DE", "Indian Blue Card applicant (generic)", None),
    Spec(in_de_generic.generate, 2, "IN_DE", "Indian Blue Card applicant (generic)", None),
    Spec(in_de_generic.generate, 3, "IN_DE", "Indian Blue Card applicant (generic)", None),
    Spec(in_de_generic.generate, 4, "IN_DE", "Indian Blue Card applicant (generic)", None),
    Spec(in_de_with_family.generate, 1, "IN_DE", "Indian Blue Card applicant with spouse", "SURNAME_MISMATCH"),
    Spec(in_de_with_family.generate, 2, "IN_DE", "Indian Blue Card applicant with spouse", "DOB_MISMATCH"),
    Spec(in_de_with_family.generate, 3, "IN_DE", "Indian Blue Card applicant with spouse", None),
    Spec(in_de_it_no_degree.generate, 1, "IN_DE", "Indian IT professional, no degree (experience route)", "EMPLOYER_MISMATCH"),
    Spec(in_de_it_no_degree.generate, 2, "IN_DE", "Indian IT professional, no degree (experience route)", None),
    Spec(in_de_it_no_degree.generate, 3, "IN_DE", "Indian IT professional, no degree (experience route)", None),
    # ---- FR→NO (10) ----
    Spec(fr_no_common.generate, 1, "FR_NO", "French (EU) national, free movement (clean)", None),
    Spec(fr_no_common.generate, 2, "FR_NO", "French (EU) national, free movement (clean)", "SALARY_MISMATCH"),
    Spec(fr_no_common.generate, 3, "FR_NO", "French (EU) national, free movement (clean)", None),
    Spec(fr_no_common.generate, 4, "FR_NO", "French (EU) national, free movement (clean)", None),
    Spec(fr_no_non_eea_spouse.generate, 1, "FR_NO", "French (EU) worker with non-EEA spouse", "ADDRESS_MISMATCH"),
    Spec(fr_no_non_eea_spouse.generate, 2, "FR_NO", "French (EU) worker with non-EEA spouse", None),
    Spec(fr_no_non_eea_spouse.generate, 3, "FR_NO", "French (EU) worker with non-EEA spouse", None),
    Spec(fr_no_french_spouse.generate, 1, "FR_NO", "French (EU) worker with French (EU) spouse", None),
    Spec(fr_no_french_spouse.generate, 2, "FR_NO", "French (EU) worker with French (EU) spouse", None),
    Spec(fr_no_french_spouse.generate, 3, "FR_NO", "French (EU) worker with French (EU) spouse", None),
]


def _write_dossier_readme(dossier_path: Path, spec: Spec, gt: dict) -> None:
    eligibility = ", ".join(gt["eligibility_verdict"]["outcome_set"])
    contradictions = gt["seeded_contradictions"]
    if contradictions:
        c_lines = "\n".join(
            f"- `{c['contradiction_type']}` on `{c['field_key']}` "
            f"(documents: {', '.join(c['affected_documents'])})"
            for c in contradictions
        )
    else:
        c_lines = "- None (clean dossier)"
    lines = [
        f"# {gt['dossier_id']}",
        "",
        f"- **Corridor**: {spec.corridor}",
        f"- **Persona**: {spec.persona}",
        f"- **Expected eligibility**: {eligibility}",
        "",
        "## Seeded contradictions",
        c_lines,
        "",
        "_Synthetic fixture — all names/values are drawn from deterministic "
        "synthetic pools. No real personal data._",
        "",
    ]
    (dossier_path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_corpus_readme(out_dir: Path, results: List[tuple]) -> None:
    in_de = [r for r in results if r[1].corridor == "IN_DE"]
    fr_no = [r for r in results if r[1].corridor == "FR_NO"]
    seeded = [(gt["dossier_id"], gt["seeded_contradictions"][0]["contradiction_type"])
              for gt, _ in results if gt["seeded_contradictions"]]

    lines = [
        "# C1 Pilot Fixture Corpus (AIQ-511)",
        "",
        "20 synthetic relocation dossiers materialized on demand for the C1 "
        "extraction / contradiction / eligibility evaluation harness.",
        "",
        "**Synthetic only — PII-redacted.** Every name, employer, address, salary "
        "and date is generated deterministically from a seed via modulo arithmetic "
        "over fixed synthetic pools (see `generators/base.py`). No real personal "
        "data is present anywhere in this corpus.",
        "",
        "## Composition",
        "",
        f"- IN→DE Blue Card: {len(in_de)} dossiers",
        f"- FR→NO EU free movement: {len(fr_no)} dossiers",
        f"- Clean: {len(results) - len(seeded)}",
        f"- With a seeded contradiction: {len(seeded)} (one per canonical type)",
        "",
        "## Seeded contradictions",
        "",
        "| Dossier | Contradiction type |",
        "| --- | --- |",
    ]
    for did, ctype in sorted(seeded):
        lines.append(f"| {did} | {ctype} |")
    lines += [
        "",
        "## Regenerate",
        "",
        "```bash",
        "cd backend && python -m tests.fixtures.pilot.materialize --out <dir>",
        "```",
        "",
        "Output (PDF stubs + per-dossier `ground_truth.json`/`generation.json`/"
        "`README.md`) is git-ignored and reproduced on demand.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def materialize(out_dir: str | Path) -> List[dict]:
    """Materialize all 20 dossiers into *out_dir*; return the list of ground_truth dicts."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    results: List[tuple] = []  # (ground_truth, spec)
    for spec in CORPUS:
        # in_de_generic.generate(seed, output_dir) predates the contradiction
        # param and is always specced clean, so only forward the kwarg when set.
        if spec.contradiction is None:
            gt = spec.generate(spec.seed, out)
        else:
            gt = spec.generate(spec.seed, out, contradiction=spec.contradiction)
        dossier_path = out / gt["dossier_id"]
        _write_dossier_readme(dossier_path, spec, gt)
        results.append((gt, spec))

    _write_corpus_readme(out, results)
    return [gt for gt, _ in results]


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the C1 pilot fixture corpus (20 dossiers).")
    parser.add_argument("--out", required=True, help="Output directory for the materialized corpus.")
    args = parser.parse_args()
    dossiers = materialize(args.out)
    summary = {
        "total": len(dossiers),
        "in_de": sum(1 for d in dossiers if d["dossier_id"].startswith("IN_DE")),
        "fr_no": sum(1 for d in dossiers if d["dossier_id"].startswith("FR_NO")),
        "seeded": sum(1 for d in dossiers if d["seeded_contradictions"]),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
