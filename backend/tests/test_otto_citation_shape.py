"""A citation that points at a whole site cannot evidence a specific claim.

`classify_source` judges the HOST and nothing else, so
`https://www.urssaf.fr/accueil` — a homepage — grades exactly like a statutory article page.
That is how production came to hold facts whose "evidence" is a navigation menu: the quote
check passes (the words really are on the homepage), the publisher check passes (urssaf.fr
really is official), and nothing ever asked whether the URL identifies the *rule*.

Measured on the NO->FR corpus 2026-08-23: three served FRANCE requirement_items cite a bare
domain (`https://www.service-public.fr`, `https://www.ameli.fr`). The ws 630 fabrication
additionally cited a service-public *annuaire* contact record — a directory entry for a phone
number, not a normative page.

A bare UUID is deliberately NOT rejected; see test_a_bare_uuid_is_left_alone.

This is a DOWNGRADE, not a rejection: the fact may be sound and merely cited lazily, and the
existing `grade()` contract is that a row the evidence will not carry drops out of
`auto_accepted` and onto a human's worklist.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Sequence

from backend.imports.otto.parsers import (
    TIER_AUTO,
    TIER_REVIEW,
    read_jsonl,
    unspecific_citation_reason,
)

ARTICLE_URL = "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003"


def _record(**overrides: Any) -> Dict[str, Any]:
    rec = {
        "destination_country": "FR",
        "entity_topic_key": "eu_free_movement_worker",
        "entity_title": "EU/EEA/Swiss citizen - worker right of residence",
        "fact_type": "fee",
        "fact_key": "cardFee",
        "fact_text": "The EU/EEA/Swiss worker residence card is free of charge.",
        "applies_to": {"role": "primary"},
        "source_url": ARTICLE_URL,
        "evidence_quote": "La carte de sejour est delivree gratuitement.",
        "confidence": "high",
    }
    rec.update(overrides)
    return rec


def _write(tmp_path: Path, records: Sequence[Dict[str, Any]]) -> Path:
    path = tmp_path / "FR-immig-test.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


# ── the classifier ───────────────────────────────────────────────────────────────────

def test_an_article_url_is_a_specific_citation():
    assert unspecific_citation_reason(ARTICLE_URL) is None


def test_a_homepage_path_is_not_a_citation():
    reason = unspecific_citation_reason("https://www.urssaf.fr/accueil")
    assert reason is not None
    assert "homepage" in reason


def test_a_bare_domain_is_not_a_citation():
    assert unspecific_citation_reason("https://www.ameli.fr") is not None
    assert unspecific_citation_reason("https://www.service-public.fr/") is not None


def test_a_bare_uuid_is_left_alone():
    """It resolves. `citations_json` carries three formats and all three work.

    Checked against prod 2026-08-23: this exact UUID resolves to a `source_records` row for
    https://www.impots.gouv.fr/resident-de-france with a 162-char snippet. Rejecting it would
    flag the best-cited rows in the corpus, which is why check_requirement_provenance.py
    declines the same check.
    """
    assert unspecific_citation_reason("9ca8e815-79fa-5ff7-9138-544f69f45351") is None


def test_a_directory_contact_record_is_not_a_normative_page():
    reason = unspecific_citation_reason(
        "https://lannuaire.service-public.gouv.fr/centres-contact/R31518"
    )
    assert reason is not None
    assert "directory" in reason


def test_a_deep_path_on_a_known_host_is_accepted():
    # The gate must not punish long or unusual paths — only unspecific ones.
    assert unspecific_citation_reason(
        "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006302521"
    ) is None


# ── the grade() contract ─────────────────────────────────────────────────────────────

def test_a_row_cited_to_a_homepage_does_not_auto_accept(tmp_path):
    path = _write(tmp_path, [_record(source_url="https://www.urssaf.fr/accueil")])
    rows, rejections = read_jsonl(path, batch_id="b1")

    assert rejections == []
    assert len(rows) == 1
    assert rows[0].accuracy_tier == TIER_REVIEW
    assert any("homepage" in d for d in rows[0].downgrades)


def test_a_row_cited_to_an_article_still_auto_accepts(tmp_path):
    path = _write(tmp_path, [_record()])
    rows, _ = read_jsonl(path, batch_id="b1")

    assert rows[0].accuracy_tier == TIER_AUTO
    assert rows[0].downgrades == []
