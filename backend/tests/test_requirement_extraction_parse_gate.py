"""[AIQ-1821] The gate that would have caught the raw-HTML bug.

WHAT SHIPPED: `fetch_url_content` returned `resp.text` and the extractor truncated to the
first 24 000 chars. On a modern government page the article begins well past that — measured
on skatteetaten.no, `<main>` starts at ~35 000 — so the model was handed `<head>`, stylesheet
links and the nav menu, and reliably produced zero facts. The LLM eval could not see it:
a zero-yield URL scored `precision 1.0` on the empty denominator, and `--ci` gated on
precision only.

WHY THIS TEST EXISTS: that bug is a *deterministic property of the text*, not of the model.
It needs no LLM, no key, no network and no DB — so unlike the quality eval it can run on
every PR (via conftest full-suite discovery, `ci.yml`), which is where a regression gate
belongs. The LLM precision/recall eval stays report-only on the weekly workflow.

`test_the_gate_actually_discriminates` is the important one: it proves these assertions FAIL
against the old behaviour. A gate that passes both before and after the fix is worthless, and
that is precisely how the previous eval fooled us.

Hermetic: pages are committed snapshots under fixtures/requirement_facts_eval/pages/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.crawler.parsers import immigration_page_parser

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "requirement_facts_eval"
_PAGES_DIR = _FIXTURE_DIR / "pages"
_GOLDEN = _FIXTURE_DIR / "golden.jsonl"

# The extractor's own cap. Mirrored rather than imported so this test also fails if the
# constant moves — the coupling is the thing under test.
_MAX_CONTENT_CHARS = 24_000


def _load_golden() -> List[Dict[str, Any]]:
    entries = []
    for line in _GOLDEN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "_meta" in row:
            continue
        entries.append(row)
    return entries


_ENTRIES = _load_golden()
_POSITIVE = [e for e in _ENTRIES if not e.get("is_negative")]
_NEGATIVE = [e for e in _ENTRIES if e.get("is_negative")]


def _parsed(entry: Dict[str, Any]) -> str:
    html = (_PAGES_DIR / entry["html_fixture"]).read_text(encoding="utf-8")
    return (immigration_page_parser.parse(html).get("text") or "").strip()


def _ids(entries):
    return [e["html_fixture"] for e in entries]


def test_golden_set_is_wellformed():
    assert _POSITIVE, "no positive fixtures — the golden set is empty"
    assert _NEGATIVE, "no negative fixture — nothing pins the JS-shell behaviour"
    meta = json.loads(_GOLDEN.read_text(encoding="utf-8").splitlines()[0])
    assert "_meta" in meta, "golden.jsonl must open with a _meta header (FIXTURE_CURATION.md)"
    assert meta["_meta"].get("verification_status") in {"verified", "representative"}


@pytest.mark.parametrize("entry", _POSITIVE, ids=_ids(_POSITIVE))
def test_every_snapshot_has_its_page_committed(entry):
    path = _PAGES_DIR / entry["html_fixture"]
    assert path.exists(), f"{entry['html_fixture']} is referenced by golden.jsonl but not committed"
    assert path.stat().st_size > 1000, "snapshot is suspiciously small — was it truncated?"


@pytest.mark.parametrize("entry", _POSITIVE, ids=_ids(_POSITIVE))
def test_parser_yields_the_article_body(entry):
    """The core assertion: real prose reaches the extractor, not <head> and nav."""
    text = _parsed(entry)
    assert len(text) >= entry["min_parsed_chars"], (
        f"{entry['html_fixture']}: parsed {len(text)} chars, expected >= "
        f"{entry['min_parsed_chars']}. The parser is no longer reaching the article body."
    )


@pytest.mark.parametrize("entry", _POSITIVE, ids=_ids(_POSITIVE))
def test_topic_anchors_survive_parsing(entry):
    """Length alone is not enough — nav menus are long too. The topic must be present."""
    low = _parsed(entry).lower()
    missing = [a for a in entry["must_contain_in_parsed"] if a.lower() not in low]
    assert not missing, f"{entry['html_fixture']}: anchors absent from parsed text: {missing}"


def _raw_window(entry: Dict[str, Any]) -> str:
    return (_PAGES_DIR / entry["html_fixture"]).read_text(encoding="utf-8")[:_MAX_CONTENT_CHARS]


@pytest.mark.parametrize("entry", _POSITIVE, ids=_ids(_POSITIVE))
def test_the_gate_actually_discriminates(entry):
    """THE POINT. These assertions must FAIL against the pre-fix behaviour.

    Old behaviour = raw HTML truncated at _MAX_CONTENT_CHARS. If every anchor were present
    there too, the gate would be green before AND after the fix — worthless, exactly like the
    eval it replaces.

    `discriminates_vs_raw` is measured per fixture, not assumed. One page (cleiss.fr) legitimately
    cannot discriminate: it is small enough that its body always sat inside the raw window, which
    is why it was the only source still producing facts pre-fix. That is recorded with a reason
    rather than quietly excluded.
    """
    low_raw = _raw_window(entry).lower()
    anchors = entry["must_contain_in_parsed"]
    missing_in_raw = [a for a in anchors if a.lower() not in low_raw]

    if entry.get("discriminates_vs_raw"):
        assert missing_in_raw, (
            f"{entry['html_fixture']} claims discriminates_vs_raw=true, but every anchor "
            f"{anchors} is already in the first {_MAX_CONTENT_CHARS} chars of RAW HTML. "
            "Either pick anchors from deeper in the article, or record why it cannot."
        )
    else:
        assert entry.get("discrimination_note"), (
            f"{entry['html_fixture']} is marked discriminates_vs_raw=false without a "
            "discrimination_note explaining why. An unexplained blind spot is not a fixture."
        )


def test_the_suite_as_a_whole_proves_the_gate_works():
    """A majority of fixtures must genuinely distinguish pre-fix from post-fix behaviour.

    Guards against the set slowly degrading into pages that would have passed anyway.
    """
    discriminating = [e for e in _POSITIVE if e.get("discriminates_vs_raw")]
    assert len(discriminating) >= max(3, (len(_POSITIVE) * 2) // 3), (
        f"only {len(discriminating)}/{len(_POSITIVE)} fixtures discriminate against the "
        "pre-fix extractor — this gate would not reliably have caught the bug it exists for"
    )
    # And prove it concretely on one: the raw window must be mostly markup, not article.
    d_number = next(e for e in _POSITIVE if e["html_fixture"] == "skatteetaten_d_number.html")
    assert "certified copy" in _parsed(d_number).lower()
    assert "certified copy" not in _raw_window(d_number).lower()


@pytest.mark.parametrize("entry", _NEGATIVE, ids=_ids(_NEGATIVE))
def test_js_only_page_yields_nothing(entry):
    """A JS shell must produce no text — never nav chrome the model can hallucinate from."""
    text = _parsed(entry)
    assert len(text) <= entry["max_parsed_chars"], (
        f"{entry['html_fixture']} is committed as a JS-only shell but parsed "
        f"{len(text)} chars. If this site began server-rendering, promote it to a positive "
        "fixture rather than loosening the bound."
    )
