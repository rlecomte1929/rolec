"""A1/CoC candidate facts are pending, employer-owned, and regime-scoped."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FACTS = REPO / "docs/imports/a1-coc-candidates-2026-09-11/facts.ndjson"

EU_EEA_CORRIDORS = {
    "FR-DE", "FR-NL", "ES-IE", "NO-FR", "FR-ES", "FR-NO", "ES-NL", "DE-NO", "IE-ES", "FR-CH",
}


def test_every_a1_candidate_is_pending_employer_posted():
    rows = [json.loads(line) for line in FACTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    seen = set()
    for row in rows:
        assert row["review_status"] == "pending"
        assert row["owner"] == "EMPLOYER"
        assert row["pillar"] == "SOCIAL_SECURITY"
        assert row["applies_to_regimes"] == ["posted"]
        assert row["source_url"].startswith("https://europa.eu/")
        seen.add(row["corridor"])
    assert EU_EEA_CORRIDORS <= seen
