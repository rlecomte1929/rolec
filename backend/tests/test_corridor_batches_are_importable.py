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

import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.imports.otto.mappings import RequirementDraft, resolve
from backend.imports.otto.parsers import read_jsonl

REPO = Path(__file__).resolve().parents[2]
IMPORTS = REPO / "docs" / "imports"

#: The batch files an importer is expected to be able to read. A nested-entity deliverable is
#: converted (see `scripts/convert_es_ie_thirdcountry_to_otto_jsonl.py`) rather than re-issued,
#: so it is the CONVERTED file that has to parse.
IMPORTABLE = (
    "no-fr-general-curated-2026-08-22/no-fr-general-curated-2026-08-22.ndjson",
    "es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.flat.ndjson",
    "ie-eu-eea-freemover-2026-08-22/facts.ndjson",
)

#: Titles already live on IRELAND EU/EEA (payroll / health / posted-worker). The free-mover
#: batch must not reuse them — crud upserts on (country_code, purpose, title) and rewrites.
_IE_LIVE_EU_EEA_TITLES = {
    "A1 Certificate — Posted Workers from Spain (EU/EEA nationals)",
    "Public Health Entitlement — Ordinary Residence (EU/EEA nationals)",
    "Irish Income Tax — Rates and Bands (EU/EEA nationals)",
    "PPS Number — Application and Uses (EU/EEA nationals)",
    "PRSI — Compulsory Social Insurance (EU/EEA nationals)",
    "Universal Social Charge — Threshold (EU/EEA nationals)",
}


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


_IE_EU_BATCH = IMPORTS / "ie-eu-eea-freemover-2026-08-22" / "facts.ndjson"
_CLI_SPEC = importlib.util.spec_from_file_location(
    "import_otto_facts", REPO / "scripts" / "import_otto_facts.py"
)
assert _CLI_SPEC and _CLI_SPEC.loader
_cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(_cli)


def _ie_eu_rows():
    rows, rejects = read_jsonl(_IE_EU_BATCH, batch_id="ie-eu-eea-freemover-2026-08-22")
    assert not rejects
    return rows


def test_the_ie_eu_batch_is_eleven_facts_on_six_topics():
    rows = _ie_eu_rows()
    assert len(rows) == 11
    topics = {r.entity_topic_key for r in rows}
    assert len(topics) == 6
    for row in rows:
        applies = row.applies_to or {}
        assert applies.get("nationality") == "EEA"
        assert applies.get("status") == "professional"


def test_the_ie_eu_batch_promotes_as_ireland_eu_eea_employment():
    """An EU national moving to Ireland must not land on the third-country permit track."""
    by_topic = defaultdict(list)
    for i, row in enumerate(_ie_eu_rows()):
        setattr(row, "id", f"00000000-0000-0000-0000-{i:012d}")
        by_topic[row.entity_topic_key].append(row)

    drafts = []
    for topic, facts in by_topic.items():
        entity = SimpleNamespace(
            destination_country=facts[0].destination_country,
            topic_key=topic,
            title=facts[0].entity_title,
            domain_area="immigration",
        )
        got = resolve(entity, facts)
        assert isinstance(got, RequirementDraft), getattr(got, "reason", got)
        assert got.payload["country_code"] == "IRELAND"
        assert got.payload["purpose"] == "employment"
        assert json.loads(got.payload["applies_to_nationality_classes_json"]) == [
            "OWN_NATIONAL",
            "EU_EEA",
        ]
        drafts.append(got)

    titles = {d.payload["title"] for d in drafts}
    assert not (titles & _IE_LIVE_EU_EEA_TITLES)
    pillars = {d.payload["pillar"] for d in drafts}
    assert "RESIDENCE" in pillars
    assert "IDENTITY" in pillars
    assert "SOCIAL_SECURITY" in pillars


def test_import_otto_facts_finds_the_ie_eu_batch_by_id():
    """A bare batch id used to miss docs/imports/<id>/facts.ndjson entirely."""
    found = _cli.resolve("ie-eu-eea-freemover-2026-08-22")
    assert found is not None
    assert found.resolve() == _IE_EU_BATCH.resolve()
    assert _cli.inferred_batch_id(found) == "ie-eu-eea-freemover-2026-08-22"


def test_facts_ndjson_does_not_ledger_as_batch_id_facts():
    assert _cli.inferred_batch_id(Path("/tmp/docs/imports/ie-eu-eea-freemover-2026-08-22/facts.ndjson")) == (
        "ie-eu-eea-freemover-2026-08-22"
    )
    assert _cli.inferred_batch_id(Path("/tmp/FR-immig-2026-08-11.jsonl")) == "FR-immig-2026-08-11"
