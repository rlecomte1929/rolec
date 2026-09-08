"""Offline tests for backend/imports/otto/quote_grounding.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "backend" / "imports" / "otto" / "quote_grounding.py"


def _load():
    spec = importlib.util.spec_from_file_location("quote_grounding_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


qg = _load()

QUOTE = "o prazo de decisão é de 90 dias"
URL = "https://imigrante.sef.pt/visados/residencia"


def _rec(**over) -> dict:
    rec = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "fact_key": "processing_time",
        "fact_text": "Decision takes 90 days.",
        "source_url": URL,
        "evidence_quote": QUOTE,
        "applies_to": {"nationality": "EEA", "status": "professional"},
    }
    rec.update(over)
    return rec


def _ndjson(tmp_path: Path, rows: list[dict], name: str = "facts.ndjson") -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _cache(tmp_path: Path, url: str, text: str, name: str = "cache") -> Path:
    d = tmp_path / name
    d.mkdir()
    fname = "page.txt"
    (d / fname).write_text(text, encoding="utf-8")
    (d / "index.json").write_text(json.dumps({url: fname}), encoding="utf-8")
    return d


def _verdicts_via_cli(tmp_path: Path, rows: list[dict], **flags) -> tuple[int, dict, list]:
    nd = _ndjson(tmp_path, rows)
    report_path = tmp_path / "report.json"
    argv = [str(nd), "--report", str(report_path)]
    if "fetched_cache" in flags:
        argv.extend(["--fetched-cache", str(flags["fetched_cache"])])
    if "grounding_dir" in flags:
        argv.extend(["--grounding-dir", str(flags["grounding_dir"])])
    code = qg.main(argv)
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return code, report, report.get("verdicts", [])


def test_confirmed_via_http_cache(tmp_path):
    cache = _cache(tmp_path, URL, f"Intro. {QUOTE} Outro.")
    rec = _rec()
    resolver = qg.make_text_resolver(qg.load_text_index(cache), None)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "confirmed"
    assert verdicts[0].grounded_by == "http_fetch"
    code, report, _ = _verdicts_via_cli(tmp_path, [rec], fetched_cache=cache)
    assert code == 0
    assert report["counts"]["confirmed"] == 1


def test_confirmed_via_grounding_dir(tmp_path):
    gdir = _cache(tmp_path, URL, f"Browser capture: {QUOTE}", name="grounding")
    rec = _rec()
    resolver = qg.make_text_resolver({}, gdir)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "confirmed"
    assert verdicts[0].grounded_by == "browser_grounded"
    code, _, _ = _verdicts_via_cli(tmp_path, [rec], grounding_dir=gdir)
    assert code == 0


def test_grounding_wins_over_cache(tmp_path):
    cache = _cache(tmp_path, URL, "HTTP body with no quote here.", name="cache")
    gdir = _cache(tmp_path, URL, f"Grounded: {QUOTE}", name="grounding")
    rec = _rec()
    fetched = qg.load_text_index(cache)
    resolver = qg.make_text_resolver(fetched, gdir)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "confirmed"
    assert verdicts[0].grounded_by == "browser_grounded"


def test_not_on_page_absent_from_needs_grounding(tmp_path):
    cache = _cache(tmp_path, URL, "A page that does not contain the evidence quote.")
    rec = _rec()
    resolver = qg.make_text_resolver(qg.load_text_index(cache), None)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "not_on_page"
    report = qg.build_report(verdicts, ndjson="facts.ndjson", grounding_dir=None)
    assert report["needs_grounding"] == []
    code, report2, _ = _verdicts_via_cli(tmp_path, [rec], fetched_cache=cache)
    assert code == 1
    assert report2["needs_grounding"] == []
    assert report2["counts"]["not_on_page"] == 1


def test_unreachable_is_on_needs_grounding(tmp_path):
    rec = _rec()
    resolver = qg.make_text_resolver({}, None)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "unreachable"
    assert verdicts[0].grounded_by is None
    report = qg.build_report(verdicts, ndjson="x.ndjson", grounding_dir=None)
    assert report["needs_grounding"][0]["dedupe_key"] == verdicts[0].dedupe_key
    code, report2, _ = _verdicts_via_cli(tmp_path, [rec])
    assert code == 1
    assert report2["needs_grounding"][0]["source_url"] == URL


def test_no_quote_fails_exit(tmp_path):
    # Hardened: a fact with no evidence_quote can never be verbatim-confirmed, so it must GATE the
    # batch (non-zero exit) rather than pass silently. It previously passed because norm("") is a
    # substring of every page. This is the no_quote hardening — see gating_exit.
    rec = _rec()
    rec.pop("evidence_quote")
    resolver = qg.make_text_resolver({}, None)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "no_quote"
    assert verdicts[0].grounded_by is None
    assert qg.gating_exit(verdicts) == 1
    code, report, _ = _verdicts_via_cli(tmp_path, [rec])
    assert code == 1
    assert report["counts"]["no_quote"] == 1


def test_slug_fallback(tmp_path):
    gdir = tmp_path / "grounding"
    gdir.mkdir()
    slug = qg.slug_url(URL)
    (gdir / f"{slug}.txt").write_text(f"slug file {QUOTE}", encoding="utf-8")
    rec = _rec()
    text = qg.grounding_text_for(URL, gdir)
    assert text is not None and QUOTE in text
    resolver = qg.make_text_resolver({}, gdir)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].status == "confirmed"
    assert verdicts[0].grounded_by == "browser_grounded"


def test_report_shape(tmp_path):
    cache = _cache(tmp_path, URL, f"{QUOTE}", name="cache")
    rec_ok = _rec()
    rec_miss = _rec(fact_key="other", evidence_quote="this quote is not on the page")
    rec_none = _rec(fact_key="nq")
    rec_none["evidence_quote"] = None
    rec_unreach = _rec(
        fact_key="gone",
        source_url="https://example.gov/missing",
        dedupe_key="PT|residence_permit|gone",
    )
    nd = _ndjson(tmp_path, [rec_ok, rec_miss, rec_none, rec_unreach])
    report_path = tmp_path / "out" / "report.json"
    code = qg.main(
        [str(nd), "--fetched-cache", str(cache), "--report", str(report_path)]
    )
    assert code == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(report) >= {
        "ndjson",
        "grounding_dir",
        "counts",
        "grounded_by",
        "needs_grounding",
        "verdicts",
    }
    assert report["counts"]["confirmed"] == 1
    assert report["counts"]["not_on_page"] == 1
    assert report["counts"]["unreachable"] == 1
    assert report["counts"]["no_quote"] == 1
    assert report["grounded_by"]["http_fetch"] == 2  # confirmed + not_on_page
    assert report["grounding_dir"] is None
    keys = {n["dedupe_key"] for n in report["needs_grounding"]}
    assert "PT|residence_permit|gone" in keys
    assert all(v["status"] != "not_on_page" or v["dedupe_key"] not in keys for v in report["verdicts"])
    assert str(nd) == report["ndjson"]


def test_normalise_parity_hook():
    rec = _rec(evidence_quote="AbC")
    page = "xx abc yy"

    def shout(s: str) -> str:
        return s.upper()

    def resolver(_url: str):
        return page, "http_fetch"

    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=shout)
    assert verdicts[0].status == "confirmed"


def test_dedupe_key_derivation():
    rec = _rec()
    rec.pop("dedupe_key", None)
    assert "dedupe_key" not in rec
    key = qg.derive_dedupe_key(rec)
    assert key == "PT|residence_permit|processing_time"
    resolver = qg.make_text_resolver({URL: QUOTE}, None)
    verdicts = qg.check_quotes([rec], text_for_url=resolver, normalise=qg.default_normalise)
    assert verdicts[0].dedupe_key == "PT|residence_permit|processing_time"


def test_does_not_mutate_applies_to():
    rec = _rec()
    applies = rec["applies_to"]
    snapshot = dict(applies)
    qg.check_quotes(
        [rec],
        text_for_url=qg.make_text_resolver({URL: QUOTE}, None),
        normalise=qg.default_normalise,
    )
    assert rec["applies_to"] == snapshot
    assert "quote_verbatim_confirmed" not in rec
    assert "quote_verbatim_confirmed" not in rec["applies_to"]
