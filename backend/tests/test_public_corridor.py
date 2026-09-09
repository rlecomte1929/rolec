"""Public corridor-requirements read model (Audos seam) — no auth, no PII.

Located in backend/tests/ (NOT backend/app/routers/ as the task text suggested) because
backend/pytest.ini sets `testpaths = tests` — a co-located router test would not be
collected by CI, defeating the "pytest passes; new test included" gate.

crud.list_requirements is monkeypatched to canned NORWAY seed rows (mirroring
backend/seeds/requirements/long_term_only.yaml) so the test is deterministic and does not
depend on the SQLite test DB being seeded. The real apply_rules (assignment-type filter)
and the response mapping ARE exercised. App is mounted from backend.main (the prod-served
entrypoint) so the test also proves the route reached the prod registration.
"""
import json
import os
from types import SimpleNamespace

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
# App-mounted harness: conftest mocks backend.database, so the query-counter listener
# can't attach to the mocked engine unless it's disabled.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.routers import public_corridor  # noqa: E402

client = TestClient(app)


def _norway_seed():
    """Canned NORWAY requirement_items rows (mirror long_term_only.yaml; gated LTA/PERMANENT)."""
    common = dict(
        country_code="NORWAY", purpose="employment", severity="WARN", owner="EMPLOYEE",
        required_fields_json="[]", citations_json="[]",
        applies_to_assignment_types_json='["LTA","PERMANENT"]', verification_status="representative",
    )
    return [
        SimpleNamespace(
            id="no-residence", pillar="RESIDENCE",
            title="Residence registration (folkeregister)",
            description=("Register at the National Registry (folkeregister) to obtain a national ID "
                         "number or D-number. Indicative — confirm with Skatteetaten."),
            **common,
        ),
        SimpleNamespace(
            id="no-housing", pillar="HOUSING",
            title="Long-term housing contract",
            description="Secure a long-term housing contract. Indicative — confirm with authorities.",
            **common,
        ),
        SimpleNamespace(
            id="no-social", pillar="SOCIAL_SECURITY",
            title="National Insurance registration (folketrygden)",
            description="Register with the National Insurance Scheme (folketrygden) via NAV.",
            **common,
        ),
    ]


def _patch_seed(monkeypatch):
    monkeypatch.setattr(
        public_corridor.crud, "list_requirements",
        lambda db, country, purpose: _norway_seed() if country == "NORWAY" else [],
    )


def test_fr_no_lta_returns_generic_requirements_no_auth(monkeypatch):
    _patch_seed(monkeypatch)
    # No Authorization header at all — must still 200 (public).
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["corridor"] == {"from": "FR", "to": "NORWAY"}
    assert body["employee_type"] == "LTA"
    assert "generated_at" in body

    reqs = body["requirements"]
    assert isinstance(reqs, list) and len(reqs) >= 1
    for r in reqs:  # exact response shape per requirement
        assert set(r.keys()) == {
            "key", "label", "description", "timing", "non_obvious",
            "legalReviewPending", "category", "source",
        }
    # the D-number / folkeregister residence item the engine DOES carry for NO/LTA
    blob = json.dumps(reqs).lower()
    assert "d-number" in blob or "folkeregister" in blob
    assert any(r["category"] == "RESIDENCE" for r in reqs)

    # data minimization: no case/user/PII fields leak into the public payload
    full = json.dumps(body).lower()
    for forbidden in ("email", "reporter", "user_id", "case_id", "caseid", "passport",
                      "statusforcase", "full_name", "fullname", "draft_json"):
        assert forbidden not in full, f"PII/case field '{forbidden}' leaked"


def test_non_obvious_and_timing_are_carried_from_the_catalog_row(monkeypatch):
    """A POPULATED value must reach the payload, not just the key.

    Every row in production has `non_obvious=false` / `timing IS NULL` today, so a live
    check against prod proves only that the keys exist — it cannot tell "carried through
    correctly" apart from "still hardcoded to None", which is what this endpoint did
    before. So seed values that could only have come from the row.

    This is also the regression test for the `apply_rules` pass-through contract seen from
    the caller's side: a rebuild inside the engine would null both of these while
    test_rules_engine_*.py stayed green.
    """
    seeded = _norway_seed()
    seeded[0].non_obvious = True
    seeded[0].timing = "within 8 days of arrival"
    monkeypatch.setattr(
        public_corridor.crud, "list_requirements",
        lambda db, country, purpose: seeded if country == "NORWAY" else [],
    )

    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.status_code == 200, resp.text
    reqs = resp.json()["requirements"]

    carried = next(r for r in reqs if r["key"] == "residence_registration_folkeregister")
    assert carried["non_obvious"] is True
    assert carried["timing"] == "within 8 days of arrival"

    # The other seeded rows carry the column defaults, and must not inherit the neighbour's.
    others = [r for r in reqs if r["key"] != "residence_registration_folkeregister"]
    assert others, "expected more than one requirement in the NO/LTA set"
    assert all(r["non_obvious"] is False and r["timing"] is None for r in others)


def test_a_row_predating_the_columns_degrades_rather_than_raising(monkeypatch):
    """A row object with neither attribute must yield false/None, not a 500.

    `_base_items` reads both with `getattr(..., default)` precisely so the endpoint
    survives a row shape that predates the migration.
    """
    bare = _norway_seed()
    for row in bare:
        assert not hasattr(row, "non_obvious") and not hasattr(row, "timing")
    monkeypatch.setattr(
        public_corridor.crud, "list_requirements",
        lambda db, country, purpose: bare if country == "NORWAY" else [],
    )

    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.status_code == 200, resp.text
    reqs = resp.json()["requirements"]
    assert reqs
    assert all(r["non_obvious"] is False and r["timing"] is None for r in reqs)


def test_cors_wildcard_header(monkeypatch):
    _patch_seed(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_sta_waives_lta_items_with_coverage_note(monkeypatch):
    _patch_seed(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=STA")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Every NO item is LTA/PERMANENT-gated → STA gets an empty list + an explicit note.
    assert body["requirements"] == []
    assert body["coverage_note"]
    assert "Residence registration (folkeregister)" in body["waived_for_assignment_type"]


def test_invalid_employee_type_422(monkeypatch):
    _patch_seed(monkeypatch)
    # lowercase policy-enum value is the wrong vocabulary for this engine → rejected.
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=long_term")
    assert resp.status_code == 422


# ── nationality gating on the public surface ─────────────────────────────────────────
#
# This endpoint published every mutually exclusive track at once. `_base_items` omitted
# `appliesToNationalityClasses`, and `rules_engine._applies_to_nationality_class` treats a
# missing key as "applies to everyone" — so a live NORWAY response carried BOTH
# `Valid passport (6+ months)` (THIRD_COUNTRY) and `Valid identity card or passport (EU/EEA)`.
# That is the failure `nationality_class.py` was written to prevent, on the one surface a
# prospect sees before they trust us.

def _two_track_seed():
    """Two rows that must never appear together: the EEA route and the third-country route."""
    common = dict(
        country_code="NORWAY", purpose="employment", severity="BLOCKER", owner="EMPLOYEE",
        required_fields_json="[]", citations_json="[]",
        applies_to_assignment_types_json=None, verification_status="corpus_grounded",
    )
    return [
        SimpleNamespace(
            id="no-eea-id", pillar="IDENTITY",
            title="Valid identity card or passport (EU/EEA)",
            description="An EU/EEA national needs a valid identity card or passport.",
            applies_to_nationality_classes_json='["OWN_NATIONAL", "EU_EEA"]', **common,
        ),
        SimpleNamespace(
            id="no-passport", pillar="IDENTITY",
            title="Valid passport (6+ months)",
            description="Passport must be valid for at least 6 months beyond entry.",
            applies_to_nationality_classes_json='["THIRD_COUNTRY"]', **common,
        ),
        SimpleNamespace(
            id="no-skattekort", pillar="EMPLOYMENT",
            title="Tax deduction card (skattekort) before first salary",
            description="Without a tax deduction card the employer must deduct 50 percent tax.",
            applies_to_nationality_classes_json=None, **common,   # universal
        ),
    ]


def _patch_two_track(monkeypatch):
    monkeypatch.setattr(
        public_corridor.crud, "list_requirements",
        lambda db, country, purpose: _two_track_seed() if country == "NORWAY" else [],
    )


def _labels(resp):
    return {r["label"] for r in resp.json()["requirements"]}


def test_the_two_nationality_tracks_are_never_served_together(monkeypatch):
    _patch_two_track(monkeypatch)
    for query in ("", "&nationality=FR", "&nationality=IN"):
        resp = client.get(
            "/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA" + query
        )
        assert resp.status_code == 200, resp.text
        both = {"Valid identity card or passport (EU/EEA)", "Valid passport (6+ months)"}
        assert not both.issubset(_labels(resp)), f"both tracks served for {query!r}"


def test_an_eu_nationality_gets_the_eea_track(monkeypatch):
    _patch_two_track(monkeypatch)
    resp = client.get(
        "/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA&nationality=FR"
    )
    labels = _labels(resp)
    assert "Valid identity card or passport (EU/EEA)" in labels
    assert "Valid passport (6+ months)" not in labels
    assert resp.json()["nationality_class"] == "EU_EEA"


def test_a_third_country_nationality_gets_the_permit_track(monkeypatch):
    _patch_two_track(monkeypatch)
    resp = client.get(
        "/api/public/corridor-requirements?from=IN&to=NO&employee_type=LTA&nationality=IN"
    )
    labels = _labels(resp)
    assert "Valid passport (6+ months)" in labels
    assert "Valid identity card or passport (EU/EEA)" not in labels
    assert resp.json()["nationality_class"] == "THIRD_COUNTRY"


def test_no_nationality_falls_back_to_the_most_demanding_track(monkeypatch):
    """Unknown must over-show, never under-inform: telling a third-country national they
    need no visa is a harm; showing an EU citizen a spare passport rule is an annoyance."""
    _patch_two_track(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    labels = _labels(resp)
    assert "Valid passport (6+ months)" in labels
    assert "Valid identity card or passport (EU/EEA)" not in labels
    # and the caller is told which track this is, rather than it reading as universal
    assert resp.json()["nationality_class"] is None


def test_a_universal_requirement_survives_every_track(monkeypatch):
    """NULL nationality classes means "applies to everyone" — the skattekort binds an EU
    citizen exactly as much as a third-country national, and suppressing it for free movers
    is the mirror-image of telling them to get a visa."""
    _patch_two_track(monkeypatch)
    for query in ("", "&nationality=FR", "&nationality=IN"):
        resp = client.get(
            "/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA" + query
        )
        assert "Tax deduction card (skattekort) before first salary" in _labels(resp)


# ---------------------------------------------------------------------------
# `source` allowlist
#
# This endpoint is unauthenticated and answers `Access-Control-Allow-Origin: *`. It used to emit
# `citations_json` RAW, and that field holds three shapes — two of which carry internal material:
# the inline objects written by the corridor generators and `otto.mappings._citations_for` carry
# `needs_lawyer_review` and, on the IE→ES rows, a `review_reason` naming the claim we do not
# trust; bare `source_records` ids are internal identifiers meaning nothing to an anonymous
# caller.
#
# Latent only while every object-shaped row sat at `review_status='pending'`. On 2026-08-21
# 12:02 UTC the nine VE→IE rows were approved and `needs_lawyer_review: true` began appearing in
# the live public body — confirmed against api.relopass.com before this fix.
#
# Allowlist, not denylist: `topic_key` and `corridor` were already being published, and a
# denylist fails open the next time a generator adds a key.
# ---------------------------------------------------------------------------

_public_sources = public_corridor._public_sources


def test_the_counsel_flag_never_reaches_an_anonymous_caller():
    got = _public_sources([{
        "url": "https://www.citizensinformation.ie/en/x/",
        "name": "Citizens Information",
        "topic_key": "spouse_stamp_1g_right_to_work",
        "corridor": "ES->IE",
        "needs_lawyer_review": True,
    }])
    assert got == ["https://www.citizensinformation.ie/en/x/"]


def test_a_review_reason_is_not_published():
    got = _public_sources([{
        "url": "https://sede.agenciatributaria.gob.es/x",
        "needs_lawyer_review": True,
        "review_reason": "sourced to the AEAT residency page, not the treaty text",
    }])
    assert "review_reason" not in json.dumps(got)
    assert "AEAT residency page" not in json.dumps(got)


def test_an_internal_source_record_id_is_dropped():
    assert _public_sources(["1f0e8a2c-0000-4000-8000-000000000001"]) == []


def test_a_resolvable_source_record_id_publishes_the_url():
    record = type("R", (), {
        "id": "src-udi",
        "url": "https://www.udi.no/en/",
        "title": "UDI",
        "publisher_domain": "www.udi.no",
        "retrieved_at": None,
        "snippet": None,
    })()
    assert _public_sources(["src-udi"], {record.id: record}) == [record.url]


def test_a_bare_url_string_still_publishes():
    url = "https://enterprise.gov.ie/permits/"
    assert _public_sources([url]) == [url]


def test_non_web_schemes_are_refused():
    assert _public_sources([{"url": "javascript:alert(1)"}]) == []


def test_one_url_cited_by_several_facts_appears_once():
    url = "https://www.irishimmigration.ie/x/"
    assert _public_sources([{"url": url}, url, {"url": url}]) == [url]


def test_no_citations_is_an_empty_list():
    assert _public_sources(None) == []
    assert _public_sources([]) == []


# ── dual nationality on the public surface ───────────────────────────────────────────
# The engine has always handled this: `rules_engine.apply_rules` calls
# `classify_best((nationality, second_nationality), dest)`, which returns the most
# favourable class because rights are cumulative. But this endpoint never supplied the
# second value, so a dual national could not be represented here at all — a
# Venezuelan/Italian was filtered as THIRD_COUNTRY and shown a permit track they must
# not apply for. That is Andrea's real case (Madrid -> Dublin, VE national, possibly
# also IT), and it is exactly the failure `classify_best`'s docstring describes.

def test_a_second_nationality_upgrades_the_track(monkeypatch):
    """VE alone gets the permit track; VE+IT must get the EEA one instead."""
    _patch_two_track(monkeypatch)

    ve_only = client.get(
        "/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA&nationality=VE"
    )
    assert ve_only.json()["nationality_class"] == "THIRD_COUNTRY"
    assert "Valid passport (6+ months)" in _labels(ve_only)
    assert "Valid identity card or passport (EU/EEA)" not in _labels(ve_only)

    dual = client.get(
        "/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA"
        "&nationality=VE&second_nationality=IT"
    )
    assert dual.json()["nationality_class"] == "EU_EEA", \
        "the Italian passport did not upgrade the track"
    assert "Valid identity card or passport (EU/EEA)" in _labels(dual)
    assert "Valid passport (6+ months)" not in _labels(dual), \
        "a dual EU national was still shown the third-country track"


def test_order_of_the_two_nationalities_does_not_matter(monkeypatch):
    """Rights are cumulative, so whichever passport intake happened to record first
    must not decide the journey."""
    _patch_two_track(monkeypatch)
    a = client.get("/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA"
                   "&nationality=VE&second_nationality=IT")
    b = client.get("/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA"
                   "&nationality=IT&second_nationality=VE")
    assert a.json()["nationality_class"] == b.json()["nationality_class"] == "EU_EEA"
    assert _labels(a) == _labels(b)


def test_an_unrecognised_second_nationality_does_not_discard_a_good_first(monkeypatch):
    """classify_best skips what it cannot classify rather than letting it win."""
    _patch_two_track(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA"
                      "&nationality=FR&second_nationality=ZZZZ")
    assert resp.json()["nationality_class"] == "EU_EEA"
    assert "Valid identity card or passport (EU/EEA)" in _labels(resp)


def test_a_second_nationality_alone_still_classifies(monkeypatch):
    """Defensive: the param must not be silently ignored when the first is absent."""
    _patch_two_track(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA"
                      "&second_nationality=IT")
    assert resp.json()["nationality_class"] == "EU_EEA"


def test_omitting_both_still_falls_back_to_third_country(monkeypatch):
    """The pre-existing contract: no nationality means the most demanding track,
    which can only ever over-show."""
    _patch_two_track(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=ES&to=NO&employee_type=LTA")
    assert resp.json()["nationality_class"] is None
    assert "Valid passport (6+ months)" in _labels(resp)
