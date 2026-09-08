"""The admin review surface must survive every `citations_json` shape prod holds.

`_review_dto` fed the raw parsed `citations_json` into a DTO field typed `List[str]`. That was
correct for the era it was written in — #1822 shipped the review surface when every citation was
a `source_records` id or a bare URL string. Since #1941 `otto.executor.promote()` writes citations
as inline OBJECTS, and pydantic rejects a dict against `str`:

    ValidationError: citations.0 Input should be a valid string [type=string_type]

`_review_dto` is called inside the handler, so ONE object-shaped row takes down the whole country
listing — the reviewer cannot see, let alone approve, any row for that country. Measured in
production on 2026-08-21:

    SPAIN     25 object-shaped of 25   -> /admin/countries/SPAIN   500s
    IRELAND    9 object-shaped of 29   -> /admin/countries/IRELAND 500s

Those 34 rows are all `review_status='pending'`, so the publication gate
(`crud.list_requirements`) is the only reason nothing wrong is being served — the review step that
is supposed to gate them simply could not run.

The second case here is not hypothetical either. `_citation_dtos` on the employee path SKIPS a
string it cannot resolve, which is right for a reader: an unresolvable reference is not a source.
On the review surface it is the opposite — a citation that vanishes is a requirement being
approved as uncited without anyone noticing. Production holds 14 non-URL string citations for
FRANCE of which only 4 resolve in `source_records`, so 10 real dangling references would silently
disappear from the one screen whose job is to catch them.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime
from types import SimpleNamespace

from backend.app.routers.admin import _review_dto

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

#: Copied verbatim from `supabase/migrations/20261108000000_ie_es_requirement_items.sql:49` —
#: one of the 25 SPAIN rows that takes the page down today. The `review_reason` is exactly the
#: kind of internal note the reviewer is meant to read and the public must never see.
IE_ES_CITATION = {
    "url": "https://sede.agenciatributaria.gob.es/Sede/no-residentes.html",
    "name": "AEAT — residencia fiscal",
    "topic_key": "tax_residency_183_days",
    "corridor": "IE->ES",
    "needs_lawyer_review": True,
    "review_reason": (
        "Claim concerns the Ireland–Spain double taxation treaty tie-breaker but is sourced to "
        "the AEAT residency page, not the treaty text."
    ),
}

#: What `otto.executor.promote()` writes since #1941 — the shape of all 9 VE→IE rows.
VE_IE_CITATION = {
    "url": "https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/",
    "topic_key": "spanish_residence_does_not_grant_irish_entry",
    "name": "Citizens Information — Visa requirements for entering Ireland",
    "corridor": "ES->IE",
    "needs_lawyer_review": True,
}


def _item(citations, **overrides):
    """A `requirement_items` row as the ORM hands it to `_review_dto`."""
    base = dict(
        id="a114fd40-f8d1-5562-aba4-d0e83e127670",
        purpose="employment",
        pillar="RESIDENCE",
        title="Spouse's Stamp 1G — work without a separate permit",
        description="The spouse of a CSEP holder is registered on a Stamp 1G on arrival.",
        severity="WARN",
        owner="EMPLOYEE",
        verification_status="representative",
        review_status="pending",
        reviewed_by=None,
        reviewed_at=None,
        applies_to_nationality_classes_json='["THIRD_COUNTRY"]',
        applies_to_assignment_types_json=None,
        citations_json=json.dumps(citations),
        last_verified_at=RETRIEVED,
        attestation_status=None,
        attested_by=None,
        attested_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestObjectShapedCitations(unittest.TestCase):
    """The regression that 500s IRELAND and SPAIN."""

    def test_an_inline_object_does_not_raise(self) -> None:
        dto = _review_dto(_item([VE_IE_CITATION]), SOURCE_MAP)
        self.assertEqual(len(dto.citations), 1)

    def test_the_object_url_survives(self) -> None:
        dto = _review_dto(_item([VE_IE_CITATION]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].url, VE_IE_CITATION["url"])

    def test_the_object_name_becomes_the_link_text(self) -> None:
        # Without this the reviewer reads a bare hostname and cannot tell one Citizens
        # Information page from another.
        dto = _review_dto(_item([VE_IE_CITATION]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].title, VE_IE_CITATION["name"])

    def test_the_spain_row_that_takes_the_page_down_today(self) -> None:
        dto = _review_dto(_item([IE_ES_CITATION]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].publisherDomain, "sede.agenciatributaria.gob.es")

    def test_a_whole_country_of_object_rows_renders(self) -> None:
        # The handler builds every row before returning, so one bad row is a 500 for all of
        # them. Mixing shapes is the real IRELAND state: 9 objects beside 20 strings.
        items = [_item([VE_IE_CITATION]) for _ in range(9)]
        items += [_item([RECORD.id]) for _ in range(20)]
        dtos = [_review_dto(i, SOURCE_MAP) for i in items]
        self.assertEqual(len(dtos), 29)


class TestExistingShapesStillWork(unittest.TestCase):
    """Nothing above may cost the 8 countries that render fine today."""

    def test_a_source_records_id_still_resolves_to_the_full_record(self) -> None:
        dto = _review_dto(_item([RECORD.id]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].url, RECORD.url)
        self.assertEqual(dto.citations[0].title, RECORD.title)

    def test_a_bare_url_string_still_renders(self) -> None:
        url = "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/"
        dto = _review_dto(_item([url]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].url, url)
        self.assertEqual(dto.citations[0].publisherDomain, "enterprise.gov.ie")

    def test_no_citations_is_an_empty_list_not_an_error(self) -> None:
        self.assertEqual(_review_dto(_item([]), SOURCE_MAP).citations, [])
        self.assertEqual(_review_dto(_item(None), SOURCE_MAP).citations, [])


class TestUnresolvableReferenceIsShownNotDropped(unittest.TestCase):
    """The reviewer is the one person who must see a broken citation.

    The employee path drops these deliberately. Here that would hide the defect from the only
    screen positioned to catch it — 10 such references exist in FRANCE today.
    """

    def test_a_dangling_source_record_id_is_still_listed(self) -> None:
        dto = _review_dto(_item(["fr-src-0007-not-in-source-records"]), SOURCE_MAP)
        self.assertEqual(len(dto.citations), 1)

    def test_a_dangling_reference_carries_no_url_to_link_to(self) -> None:
        dto = _review_dto(_item(["fr-src-0007-not-in-source-records"]), SOURCE_MAP)
        self.assertIsNone(dto.citations[0].url)
        self.assertEqual(dto.citations[0].title, "fr-src-0007-not-in-source-records")


class TestOnlyWebSchemesReachAnHref(unittest.TestCase):
    """A citation URL is rendered straight into `<a href=...>` on both surfaces.

    The string branch of `citation_dtos` has always required http/https. The dict branch, added
    when the reader learned the inline-object shape, did not — so a citation object could carry
    `javascript:` all the way to the reviewer's link, and to the employee's via `Citations.tsx`.
    Citation objects come from research NDJSON and generator scripts; the shape of a citation
    must not decide whether its scheme is checked.

    The admin surface still LISTS the rejected entry as an unresolved source. Silently dropping
    a hostile citation would hide it from the person deciding whether to publish the row.
    """

    def test_a_javascript_url_never_becomes_a_link(self) -> None:
        hostile = {"url": "javascript:alert(document.cookie)", "name": "Official source"}
        dto = _review_dto(_item([hostile]), SOURCE_MAP)
        self.assertEqual(len(dto.citations), 1)
        self.assertIsNone(dto.citations[0].url)

    def test_the_check_is_not_defeated_by_casing_or_padding(self) -> None:
        dto = _review_dto(_item([{"url": "  JaVaScRiPt:alert(1)"}]), SOURCE_MAP)
        self.assertIsNone(dto.citations[0].url)

    def test_a_data_url_is_refused_too(self) -> None:
        dto = _review_dto(_item([{"url": "data:text/html,<script>alert(1)</script>"}]), SOURCE_MAP)
        self.assertIsNone(dto.citations[0].url)

    def test_a_real_https_source_is_unaffected(self) -> None:
        dto = _review_dto(_item([VE_IE_CITATION]), SOURCE_MAP)
        self.assertEqual(dto.citations[0].url, VE_IE_CITATION["url"])


if __name__ == "__main__":
    unittest.main()
