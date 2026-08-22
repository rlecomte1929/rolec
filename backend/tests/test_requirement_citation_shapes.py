"""`citations_json` holds three shapes, and the reader must survive all of them.

Production does not store one citation format. It stores `source_records` ids (the original
design), bare URL strings (written by `otto.executor.promote()` via `mappings.py`), and inline
objects (written by the corridor generators, e.g. `scripts/gen_ie_es_corridor_load.py`).

The reader used to be:

    [_source_dto(source_map[cid]) for cid in item.get("citations", []) if cid in source_map]

which failed two different ways, both silent until now:

1. A **bare URL** is not a key in `source_map`, so it was dropped and the requirement served
   with an empty citation list — while `check_requirement_provenance.py` still passed, because
   that guard only asserts `citations_json IS NOT NULL`. Approved, served, uncited.
2. A **dict is unhashable**, so `cid in source_map` raised `TypeError`. The 25 IE→ES rows
   carrying inline objects are all `review_status='pending'` and have never been served, so
   this has sat latent rather than taking the dossier down.

`retrievedAt` is deliberately None for anything but a real `source_records` row: it drives the
client's StalenessBadge, and a page nobody retrieved must not carry a freshness claim.
"""
from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

from backend.app.services.requirements_builder import _citation_dtos

RETRIEVED = datetime(2026, 8, 1, 12, 0, 0)

RECORD = SimpleNamespace(
    id="1f0e8a2c-0000-4000-8000-000000000001",
    url="https://www.irishimmigration.ie/registering/",
    title="Immigration Service Delivery — registration",
    publisher_domain="www.irishimmigration.ie",
    retrieved_at=RETRIEVED,
    snippet="You must register within 90 days.",
)
SOURCE_MAP = {RECORD.id: RECORD}


class TestSourceRecordId(unittest.TestCase):
    def test_a_known_id_resolves_to_the_full_record(self) -> None:
        [dto] = _citation_dtos([RECORD.id], SOURCE_MAP)
        self.assertEqual(dto.id, RECORD.id)
        self.assertEqual(dto.url, RECORD.url)
        self.assertEqual(dto.title, RECORD.title)
        self.assertEqual(dto.publisherDomain, "www.irishimmigration.ie")

    def test_a_known_id_keeps_its_retrieval_time(self) -> None:
        """Only a real source_records row may make a freshness claim."""
        [dto] = _citation_dtos([RECORD.id], SOURCE_MAP)
        self.assertEqual(dto.retrievedAt, RETRIEVED)


class TestBareUrl(unittest.TestCase):
    """What promote() writes today. Previously dropped without trace."""

    URL = "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/"

    def test_a_bare_url_is_no_longer_dropped(self) -> None:
        dtos = _citation_dtos([self.URL], SOURCE_MAP)
        self.assertEqual(len(dtos), 1)
        self.assertEqual(dtos[0].url, self.URL)

    def test_the_publisher_domain_is_derived_from_the_url(self) -> None:
        [dto] = _citation_dtos([self.URL], SOURCE_MAP)
        self.assertEqual(dto.publisherDomain, "enterprise.gov.ie")

    def test_no_retrieval_time_is_invented(self) -> None:
        [dto] = _citation_dtos([self.URL], SOURCE_MAP)
        self.assertIsNone(dto.retrievedAt)

    def test_a_string_that_is_neither_id_nor_url_is_skipped(self) -> None:
        """An unresolvable reference is not a source. Skipped, never guessed at."""
        self.assertEqual(_citation_dtos(["immigration_rule.ie.stamp1g"], SOURCE_MAP), [])


class TestInlineObject(unittest.TestCase):
    """What the corridor generators write. Previously raised TypeError."""

    CITATION = {
        "url": "https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/",
        "name": "Citizens Information — Visa requirements",
        "corridor": "ES-IE",
        "topic_key": "entry_d_visa_required_venezuela",
        "needs_lawyer_review": True,
    }

    def test_a_dict_citation_does_not_raise(self) -> None:
        """The regression. `cid in source_map` raised `unhashable type: 'dict'`."""
        dtos = _citation_dtos([self.CITATION], SOURCE_MAP)
        self.assertEqual(len(dtos), 1)

    def test_the_name_becomes_the_title(self) -> None:
        [dto] = _citation_dtos([self.CITATION], SOURCE_MAP)
        self.assertEqual(dto.title, "Citizens Information — Visa requirements")

    def test_it_falls_back_to_the_domain_when_unnamed(self) -> None:
        [dto] = _citation_dtos([{"url": self.CITATION["url"]}], SOURCE_MAP)
        self.assertEqual(dto.title, "www.citizensinformation.ie")

    def test_no_retrieval_time_is_invented(self) -> None:
        [dto] = _citation_dtos([self.CITATION], SOURCE_MAP)
        self.assertIsNone(dto.retrievedAt)

    def test_an_object_with_no_url_is_skipped(self) -> None:
        self.assertEqual(_citation_dtos([{"name": "no url here"}], SOURCE_MAP), [])


class TestMixedAndDegenerate(unittest.TestCase):
    def test_all_three_shapes_in_one_list(self) -> None:
        """Real rows mix them — a batch reload can leave both formats on one requirement."""
        dtos = _citation_dtos(
            [RECORD.id, "https://revenue.ie/x", {"url": "https://dfa.ie/y", "name": "DFA"}],
            SOURCE_MAP,
        )
        self.assertEqual(
            [d.publisherDomain for d in dtos],
            ["www.irishimmigration.ie", "revenue.ie", "dfa.ie"],
        )

    def test_empty_and_none_are_both_empty(self) -> None:
        self.assertEqual(_citation_dtos([], SOURCE_MAP), [])
        self.assertEqual(_citation_dtos(None, SOURCE_MAP), [])

    def test_an_unknown_id_with_no_sources_loaded_still_returns_a_list(self) -> None:
        self.assertEqual(_citation_dtos([RECORD.id], {}), [])


class TestSchemeGate(unittest.TestCase):
    """`Citations.tsx:24` renders `href={source.url}` — so a non-web scheme must never survive.

    The string branch always required http/https; the dict branch did not until this was fixed,
    which meant the shape a citation happened to be stored in decided whether it was checked.
    """

    def test_a_dict_citation_cannot_smuggle_a_javascript_url(self) -> None:
        self.assertEqual(_citation_dtos([{"url": "javascript:alert(1)"}], {}), [])

    def test_a_string_citation_still_cannot_either(self) -> None:
        self.assertEqual(_citation_dtos(["javascript:alert(1)"], {}), [])

    def test_https_is_untouched(self) -> None:
        got = _citation_dtos([{"url": "https://www.gov.ie/x", "name": "Gov"}], {})
        self.assertEqual(got[0].url, "https://www.gov.ie/x")


if __name__ == "__main__":
    unittest.main()
