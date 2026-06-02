"""Parker-J: extractive (TextRank) summariser — LLM-free, deterministic."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.nlg.extractive_summarizer import summarise  # noqa: E402


# A small corpus where the housing/tax theme is central and a couple of
# sentences are off-topic filler.
CORPUS = (
    "The relocation policy sets housing budgets for every assignment tier. "
    "Housing budgets must not exceed the tier cap defined for the destination city. "
    "Tax equalisation applies to senior assignments and protects net pay. "
    "The tax team reconciles equalisation at year end for each assignee. "
    "Employees receive a welcome pack on arrival. "
    "The office cafeteria serves lunch from noon. "
    "Housing and tax caps are reviewed annually by the mobility committee. "
    "Pets may travel under a separate allowance subject to quarantine rules."
)


def test_returns_at_most_max_sentences():
    out = summarise(CORPUS, max_sentences=3)
    assert out.count(". ") + 1 <= 3


def test_selects_central_theme():
    out = summarise(CORPUS, max_sentences=3)
    # The housing/tax sentences are the most central; off-topic cafeteria filler
    # should not be selected.
    assert "cafeteria" not in out
    assert "housing" in out.lower() or "tax" in out.lower()


def test_preserves_source_order():
    out = summarise(CORPUS, max_sentences=4)
    chosen = [s.strip() for s in out.split(". ") if s.strip()]
    sources = [s.strip().rstrip(".") for s in CORPUS.split(". ")]
    positions = [sources.index(c.rstrip(".")) for c in chosen]
    assert positions == sorted(positions)


def test_short_text_returned_whole():
    short = "Only one sentence here. And a second one."
    out = summarise(short, max_sentences=5)
    assert out == "Only one sentence here. And a second one."


def test_empty_text():
    assert summarise("", max_sentences=5) == ""


def test_determinism_identical_bytes():
    a = summarise(CORPUS, max_sentences=3)
    b = summarise(CORPUS, max_sentences=3)
    assert a == b and a.encode("utf-8") == b.encode("utf-8")


def test_llm_free_source_has_no_llm_sdk():
    # Parker's whole point: this path is classical NLG, no model fees. Assert the
    # module never imports an LLM SDK.
    import backend.app.services.nlg.extractive_summarizer as mod
    with open(mod.__file__) as fh:
        src = fh.read()
    assert "import openai" not in src
    assert "import anthropic" not in src
