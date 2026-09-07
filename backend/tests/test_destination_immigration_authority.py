"""IDR-260820-28EC — pick an immigration authority from curated rows only."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.services.destination_immigration_authority import (
    lookup_destination_immigration_authority,
    normalize_country_code,
    pick_from_form_templates,
    pick_from_key_authorities,
)


def test_normalize_rejects_non_iso2():
    assert normalize_country_code("de") == "DE"
    assert normalize_country_code("Germany") is None
    assert normalize_country_code("") is None


def test_picks_first_immigration_https_and_skips_tax():
    payload = [
        {"name": "Finanças", "url": "https://www.portaldasfinancas.gov.pt", "type": "tax"},
        {"name": "BAMF", "url": "https://www.bamf.de", "type": "immigration"},
        {"name": "Ausländerbehörde", "url": "https://www.bamf.de/en", "type": "immigration"},
    ]
    picked = pick_from_key_authorities(payload)
    assert picked["name"] == "BAMF"
    assert picked["url"] == "https://www.bamf.de"


def test_rejects_non_https_and_empty_list():
    assert pick_from_key_authorities([{"name": "X", "url": "http://bamf.de", "type": "immigration"}]) is None
    assert pick_from_key_authorities([]) is None
    assert pick_from_key_authorities("not-json") is None


def test_form_templates_skips_tax_and_picks_shortest_https():
    rows = [
        {"category": "tax", "authority_name": "HMRC", "source_url": "https://www.gov.uk/hmrc"},
        {
            "category": "work_permit",
            "authority_name": "UDI",
            "source_url": "https://www.udi.no/en/want-to-apply/work-immigration/skilled-workers/",
        },
        {"category": "work_permit", "authority_name": "UDI", "source_url": "https://www.udi.no"},
    ]
    picked = pick_from_form_templates(rows)
    assert picked["url"] == "https://www.udi.no"
    assert picked["name"] == "UDI"


def test_lookup_uses_countries_then_falls_back_to_forms():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE countries (code TEXT PRIMARY KEY, key_authorities TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE form_templates "
                "(country TEXT, category TEXT, authority_name TEXT, authority_code TEXT, source_url TEXT)"
            )
        )
        conn.execute(
            text("INSERT INTO countries (code, key_authorities) VALUES (:c, :k)"),
            {
                "c": "DE",
                "k": '[{"name":"Ausländerbehörde","url":"https://www.bamf.de","type":"immigration"}]',
            },
        )
        conn.execute(
            text(
                "INSERT INTO form_templates (country, category, authority_name, authority_code, source_url) "
                "VALUES ('NO', 'work_permit', 'UDI', 'UDI', 'https://www.udi.no')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO form_templates (country, category, authority_name, authority_code, source_url) "
                "VALUES ('IE', 'tax', 'Revenue', 'REV', 'https://www.revenue.ie')"
            )
        )

    with Session() as session:
        de = lookup_destination_immigration_authority(session, "DE")
        no = lookup_destination_immigration_authority(session, "NO")
        ie = lookup_destination_immigration_authority(session, "IE")
        zz = lookup_destination_immigration_authority(session, "ZZ")

    assert de["url"] == "https://www.bamf.de"
    assert no["url"] == "https://www.udi.no"
    assert ie is None  # tax-only templates must not become the standing immigration link
    assert zz is None
