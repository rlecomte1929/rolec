"""Service answers read must normalise jsonb (dict) as well as text (string).

Postgres returns the `answers` jsonb column already parsed as a Python dict
(psycopg2). list_case_service_answers used json.loads() on it, which raised, and
the except silently set answers = {} — so saved service preferences never reached
the recommendation criteria (personalization was ignored in prod). SQLite stores
the column as TEXT, so json.loads worked there and the bug was invisible to SQLite
tests. The fix routes the value through _coerce_answers_field, which accepts both.
"""
from __future__ import annotations

from backend.db.cases import _coerce_answers_field


def test_jsonb_dict_is_kept():
    # Postgres jsonb → driver hands back a dict; must be preserved, not blanked.
    d = {"budget_min": 15000, "housing_lifestyle": ["safety", "green"]}
    assert _coerce_answers_field(d) == d


def test_json_string_is_parsed():
    # SQLite / text column → JSON string.
    assert _coerce_answers_field('{"budget_min": 15000}') == {"budget_min": 15000}


def test_none_and_garbage_become_empty_dict():
    assert _coerce_answers_field(None) == {}
    assert _coerce_answers_field("not json") == {}
    assert _coerce_answers_field("") == {}
    assert _coerce_answers_field(123) == {}
    assert _coerce_answers_field('["a","list"]') == {}  # non-dict JSON → {}
