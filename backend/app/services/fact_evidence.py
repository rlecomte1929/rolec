"""[AIQ-1821] Is a requirement fact's evidence quote actually in its source?

A reviewer must never be asked to judge a fact without its evidence on screen — approving one
without seeing what vouched for it is a rubber stamp. This module is the machine half of that:
it answers, for one fact, "does the stored quote appear in the archived source text, and where",
so the review queue can render the quote inside its surrounding context.

Deliberately pure: text in, verdict out. No DB, no network, no LLM. That keeps it testable
against planted errors (see backend/tests/test_fact_evidence.py) and cheap enough to run over
the whole backlog.

The verdict is intentionally three-valued, because "we never checked" and "we checked and it
isn't there" are very different things to show a reviewer:

    VERIFIED     the quote is in the source, character-for-character (modulo whitespace/curly
                 quotes). The strongest claim available without a human.
    TRANSLATED   the source is in a different language from the quote. A verbatim match is
                 impossible by construction, so this says nothing about correctness — it says
                 the check does not apply. Measured 2026-08-12: every one of France's 97 pending
                 facts is an English rendering of a French service-public.gouv.fr page. Folding
                 those into UNVERIFIED would put 97 sound facts in the suspect pile.
    UNVERIFIED   we have the source, it is the same language, and the quote is NOT in it. Not
                 proof of a hallucination — the extractor legitimately recomposes bullet lists
                 into sentences — but it is exactly the set a human should read.
    NO_SOURCE    no archived text to check against. Says nothing about the fact.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

VERIFIED = "verified"
TRANSLATED = "translated"
UNVERIFIED = "unverified"
NO_SOURCE = "no_source"

# Stop-word profiles for the handful of source languages ReloPass ingests. Deliberately a
# 20-line heuristic and not a language-detection dependency: the only question being asked is
# "could this quote possibly be a substring of this page", and a coarse answer is enough.
_STOPWORDS = {
    "en": {"the", "and", "you", "must", "for", "with", "your", "that", "from", "have", "this",
           "of", "in", "to", "is", "are", "be", "or", "on", "as", "by", "it", "not", "an", "if"},
    "fr": {"le", "la", "les", "des", "vous", "pour", "est", "une", "dans", "que", "sur", "avec",
           "du", "au", "aux", "votre", "vos", "être", "ou", "par", "ce", "cette", "doit"},
    "de": {"der", "die", "das", "und", "sie", "mit", "für", "ist", "nicht", "auf", "eine",
           "den", "dem", "ihre", "muss", "oder", "von", "zu", "im"},
    "no": {"og", "ikke", "som", "til", "med", "har", "kan", "det", "på", "være", "du", "en",
           "av", "for", "eller", "skal", "der"},
    "es": {"la", "los", "las", "que", "para", "con", "una", "por", "del", "en", "su", "es",
           "debe", "sus", "como", "este"},
    "nl": {"het", "een", "van", "voor", "met", "niet", "zijn", "aan", "die", "je", "moet",
           "of", "op", "te"},
}


def _language_of(text: str, *, min_words: int = 8, min_hits: int = 3) -> Optional[str]:
    """Coarsest possible guess. None when no profile clearly wins.

    Two thresholds because the two sides differ in length: an archived page is thousands of
    words, a fact's quote is often only a dozen. Too high a floor and the quote never resolves,
    so a translated fact falls through to UNVERIFIED — which is the mislabel this exists to
    prevent.
    """
    words = re.findall(r"[a-zà-ÿ]+", (text or "").lower())[:400]
    if len(words) < min_words:
        return None
    counts = {lang: sum(1 for w in words if w in sw) for lang, sw in _STOPWORDS.items()}
    best = max(counts, key=lambda k: counts[k])
    runner_up = sorted(counts.values())[-2] if len(counts) > 1 else 0
    # Require a clear win: Dutch/German and Spanish/French share stop words, so a narrow lead
    # is not evidence of anything.
    if counts[best] < min_hits or counts[best] < runner_up * 1.5:
        return None
    return best

# Below this, an "archived" document is a fetch failure or a nav stub rather than an article,
# and matching against it would produce meaningless verdicts. Measured: the pre-backfill corpus
# averaged 441 chars because the old ingest capped excerpts at 5k and mostly failed to fetch.
MIN_USABLE_SOURCE_CHARS = 200

# How much text either side of the quote the queue shows. Enough to make the difference between
# "you can get X if you provide Y" and "you MUST provide Y" visible without opening the source.
CONTEXT_WINDOW_CHARS = 200


@dataclass(frozen=True)
class EvidenceCheck:
    """The verdict for one fact."""

    status: str  # VERIFIED | UNVERIFIED | NO_SOURCE
    offset: Optional[int]  # index into the NORMALISED source text, None unless verified
    context: str  # quote plus surrounding source text, empty unless verified

    @property
    def verified(self) -> Optional[bool]:
        """Tri-state for the DB column.

        None means the check DID NOT APPLY — no archived source, or a language mismatch that
        makes a substring match impossible. False is reserved for the damning case: same
        language, source in hand, quote not there. `evidence_checked_at` separates "never ran"
        from "ran and did not apply".
        """
        if self.status in (NO_SOURCE, TRANSLATED):
            return None
        return self.status == VERIFIED


def normalise(text: str) -> str:
    """Collapse the differences that are noise for a substring match, and only those.

    Whitespace runs (a parsed page has newlines where the quote has spaces), curly vs straight
    quotes and dashes (publishers and models disagree), and NBSP — Norwegian and French
    government pages are full of U+00A0 and U+202F, which would otherwise fail every match.

    NOT case-folded here: callers lower() at comparison time. Keeping case in the returned text
    means the context we show a reviewer is the real sentence, not a flattened one.
    """
    if not text:
        return ""
    # NFKC folds the typographic variants (e.g. U+2019 stays, but ligatures/width variants fold).
    out = unicodedata.normalize("NFKC", text)
    out = out.replace("’", "'").replace("‘", "'")
    out = out.replace("“", '"').replace("”", '"')
    out = out.replace("–", "-").replace("—", "-")
    out = out.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", out).strip()


def check_evidence(quote: Optional[str], source_text: Optional[str]) -> EvidenceCheck:
    """Verdict for one (quote, archived source text) pair."""
    n_source = normalise(source_text or "")
    if len(n_source) < MIN_USABLE_SOURCE_CHARS:
        return EvidenceCheck(NO_SOURCE, None, "")

    n_quote = normalise(quote or "")
    if not n_quote:
        # A fact with no quote can never be machine-verified. It is not "no source" — we have
        # the source; the fact simply cites nothing. That belongs in front of a human.
        return EvidenceCheck(UNVERIFIED, None, "")

    idx = n_source.lower().find(n_quote.lower())
    if idx == -1:
        # Before calling it unsupported, rule out the case where a match was never possible:
        # an English rendering of a French page cannot contain a French substring.
        # The source is long and reliable; the quote is short, so it gets a lower bar.
        src_lang = _language_of(n_source, min_words=30, min_hits=6)
        quote_lang = _language_of(n_quote, min_words=6, min_hits=2)
        if src_lang and quote_lang and src_lang != quote_lang:
            return EvidenceCheck(TRANSLATED, None, "")
        return EvidenceCheck(UNVERIFIED, None, "")

    start = max(0, idx - CONTEXT_WINDOW_CHARS)
    end = min(len(n_source), idx + len(n_quote) + CONTEXT_WINDOW_CHARS)
    context = ("…" if start > 0 else "") + n_source[start:end] + ("…" if end < len(n_source) else "")
    return EvidenceCheck(VERIFIED, idx, context)
