"""AIQ-1311 — guard that submit promotes the route onto relocation_cases for a
FRESH case (no wizard_cases row).

The original criterion-3 regression: the relocation_cases route promotion was gated
on `if wc:` (a wizard_cases lookup), so a freshly-created case — which has only a
relocation_cases row — never got origin/dest written, and HR saw "Not provided"
even after a successful submit. The live spine probe (scripts/verify_intake_submit_spine.py)
caught it; this source guard keeps it from silently regressing.
"""
from __future__ import annotations

import os


def _submit_assignment_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def submit_assignment(")
    end = src.index("\n@app.", start + 1)
    return src[start:end]


def test_promotion_uses_authoritative_draft():
    src = _submit_assignment_source()
    assert "promote_draft = submit_draft" in src
    assert "sync_relocation_case_route_from_wizard_draft(eff_case_for_sync, promote_draft)" in src


def test_promotion_not_gated_on_wizard_cases_row():
    """The authoritative-draft promotion must run BEFORE (not nested under) the
    `wc` wizard_cases fallback — i.e. a fresh case with no wizard_cases row still
    gets its route columns written."""
    src = _submit_assignment_source()
    # authoritative assignment draft is chosen first, with wc only a fallback (elif)
    assert src.index("promote_draft = submit_draft") < src.index("elif wc:")
    # regression: the old wc-gated form synced the wc-derived `draft`, not promote_draft
    assert "sync_relocation_case_route_from_wizard_draft(eff_case_for_sync, draft)" not in src
