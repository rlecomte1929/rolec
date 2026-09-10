"""Employee, public, and admin citation URLs must agree on what is resolvable.

The employee dossier drops unresolvable refs. The public corridor must emit the same
URL set (never a dangling source_records id). Admin may *also* show unresolved labels.
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from backend.app.routers.admin import _admin_citation_dtos
from backend.app.routers.public_corridor import _public_sources
from backend.app.services.requirements_builder import citation_dtos

RETRIEVED = datetime(2026, 8, 1, 12, 0, 0)
RECORD = SimpleNamespace(
    id="src-udi",
    url="https://www.udi.no/en/word-definitions/d-number/",
    title="D-number",
    publisher_domain="www.udi.no",
    retrieved_at=RETRIEVED,
    snippet="Apply for a D-number.",
)
SOURCE_MAP = {RECORD.id: RECORD}

CITATIONS = [
    RECORD.id,
    "https://www.skatteetaten.no/en/person/",
    {"url": "https://www.udi.no/en/want-to-apply/", "name": "UDI apply"},
    "immigration_rule.no.ghost",  # dangling — employee/public drop; admin keeps
]


def test_resolved_urls_match_across_employee_and_public():
    employee = [d.url for d in citation_dtos(CITATIONS, SOURCE_MAP) if d.url]
    public = _public_sources(CITATIONS, SOURCE_MAP)
    assert employee == public
    assert RECORD.url in public
    assert "https://www.skatteetaten.no/en/person/" in public
    assert "https://www.udi.no/en/want-to-apply/" in public
    assert "immigration_rule.no.ghost" not in public


def test_admin_keeps_the_dangling_ref_the_reader_drops():
    admin = _admin_citation_dtos(CITATIONS, SOURCE_MAP)
    admin_urls = {c.url for c in admin if c.url}
    employee_urls = {d.url for d in citation_dtos(CITATIONS, SOURCE_MAP) if d.url}
    assert employee_urls <= admin_urls
    titles = [c.title for c in admin]
    assert any("immigration_rule.no.ghost" in t for t in titles)


def test_public_never_emits_raw_source_record_ids():
    payload = json.dumps(_public_sources(CITATIONS, SOURCE_MAP))
    assert "src-udi" not in payload
