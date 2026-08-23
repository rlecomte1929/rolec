"""Every committed corridor batch must be readable by the importer that has to load it.

The ES→IE third-country batch sat in `docs/imports/` for a day described as "verified and
waiting" while `read_jsonl` died on its line 1 (`missing required field(s): entity_topic_key`):
it nests the entity, and the parser wants flat `entity_topic_key` / `entity_title`. The NO→FR
batch beside it uses the flat shape and parses cleanly, so two artifacts in the same directory
spoke two vocabularies and nothing checked.

A batch nobody can import is indistinguishable from research nobody did, and the failure is
silent until someone tries to load it. These tests make it loud.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.imports.otto.parsers import read_jsonl

REPO = Path(__file__).resolve().parents[2]
IMPORTS = REPO / "docs" / "imports"

#: The batch files an importer is expected to be able to read. A nested-entity deliverable is
#: converted (see `scripts/convert_es_ie_thirdcountry_to_otto_jsonl.py`) rather than re-issued,
#: so it is the CONVERTED file that has to parse.
IMPORTABLE = (
    "no-fr-general-curated-2026-08-22/no-fr-general-curated-2026-08-22.ndjson",
    "es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.flat.ndjson",
)


@pytest.mark.parametrize("relpath", IMPORTABLE)
def test_the_batch_parses_with_no_rejections(relpath):
    path = IMPORTS / relpath
    assert path.exists(), f"{relpath} is missing — run its converter"
    rows, rejects = read_jsonl(path, batch_id="importability-probe")
    assert not rejects, f"{relpath} rejected {len(rejects)} row(s): {rejects[:3]}"
    assert rows, f"{relpath} parsed to zero rows"


def test_the_es_ie_converted_file_matches_the_delivered_one_row_for_row():
    """The converter moves fields; it must never drop or invent a record."""
    delivered = IMPORTS / "es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson"
    converted = IMPORTS / "es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.flat.ndjson"
    n_delivered = len([l for l in delivered.read_text().splitlines() if l.strip()])
    rows, _ = read_jsonl(converted, batch_id="importability-probe")
    assert len(rows) == n_delivered == 38


def test_the_nested_deliverable_still_fails_so_the_converter_is_not_decorative():
    """If the raw file ever starts parsing, the converter is redundant and this test says so
    rather than leaving a dead script in the tree."""
    delivered = IMPORTS / "es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson"
    with pytest.raises(Exception):
        read_jsonl(delivered, batch_id="importability-probe")
