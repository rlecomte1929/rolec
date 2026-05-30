"""C2-04 · Rule-change scraper for UDI / BAMF / dejure.org (AIQ-555).

Architecture Report §5.2. A daily LangGraph job that fetches a fixed set of
regulation pages, normalises each to a whitespace-collapsed text extract, hashes
it, and — when the hash differs from the last captured baseline for the rule —
writes a DIFF-BASED ``RuleChangeProposal`` row into ``rce.rule_change_proposals``
with ``status='pending'``.

Hard invariant (the entire point of this task): **the scraper NEVER promotes or
applies a rule change.** Every proposal it writes is in the ``pending`` review
state. Promotion / rejection is a human action performed elsewhere (the C2-05
admin UI). There is no code path in this module that produces ``promoted`` or
``rejected`` — the :class:`ProposalStatus` the writer is allowed to emit is
fixed to ``pending`` by construction.

Idempotency: a proposal is keyed by ``(rule_id, captured_html_hash)`` where the
hash is computed over the *normalised* text (not raw HTML), so cosmetic markup
changes never raise a proposal, and re-running on identical content is a no-op.

Per the :file:`backend/relopass/__init__.py` package constraint, this module
imports no vendor SDK, no FastAPI, no SQLAlchemy. Network I/O is the injected
:class:`HtmlFetcher` Protocol; persistence is the injected :class:`ProposalStore`
Protocol; the optional LLM diff-summariser is an injected callable. Tests inject
in-memory / stub implementations so the suite is fully hermetic and offline.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Tuple
from uuid import UUID, uuid4

# The only status the scraper is ever permitted to write. Promotion / rejection
# is a human action handled by the C2-05 review UI — never by this job.
ProposalStatus = str
PENDING: ProposalStatus = "pending"


# ─────────────────────────────────────────────────────────────────────────────
# Seeded source list (Cohort 2 launch set) — mirrors the Notion YAML for AIQ-555.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuleSource:
    """A tracked regulation page and the rule ids it feeds."""

    source_id: str
    url: str
    rule_ids: Tuple[str, ...]


RULE_SCRAPER_SOURCES: Tuple[RuleSource, ...] = (
    RuleSource(
        source_id="UDI_VIKTIGE_MELDINGER",
        url="https://www.udi.no/en/important-messages/",
        rule_ids=("NO_UTL_SKILLED_WORKER_SALARY", "NO_UTL_SKILLED_WORKER_GENERAL"),
    ),
    RuleSource(
        source_id="UDI_SKILLED_WORKER_PAGE",
        url="https://www.udi.no/en/want-to-apply/work-and-residence/skilled-workers/",
        rule_ids=("NO_UTL_SKILLED_WORKER_SALARY",),
    ),
    RuleSource(
        source_id="DEJURE_AUFENTHG_18G",
        url="https://dejure.org/gesetze/AufenthG/18g.html",
        rule_ids=("DE_AUFENTHG_18G", "DE_AUFENTHG_18G_SALARY"),
    ),
    RuleSource(
        source_id="DEJURE_AUFENTHG_18B",
        url="https://dejure.org/gesetze/AufenthG/18b.html",
        rule_ids=("DE_AUFENTHG_18B",),
    ),
    RuleSource(
        source_id="BAMF_BLUE_CARD",
        url=(
            "https://www.bamf.de/EN/Themen/MigrationAufenthalt/"
            "ZuwandererDrittstaaten/Arbeit/BlaueKarteEU/blauekarteeu-node.html"
        ),
        rule_ids=("DE_AUFENTHG_18G",),
    ),
    RuleSource(
        # The 2026 BGBl thresholds bulletin (German Blue Card §18g salary floor).
        source_id="BMI_THRESHOLD_BULLETIN",
        url="https://www.bmi.bund.de/SharedDocs/gesetzgebungsverfahren/DE/bgbl-2026-thresholds.html",
        rule_ids=("DE_AUFENTHG_18G_SALARY",),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation + hashing
# ─────────────────────────────────────────────────────────────────────────────

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def normalize_text(html: str) -> str:
    """Reduce raw HTML to a stable, whitespace-collapsed text extract.

    Strips HTML comments, ``<script>``/``<style>`` blocks, and all tags, then
    collapses runs of whitespace to a single space. Cosmetic markup changes
    (re-indentation, comment churn, attribute reordering inside tags that get
    stripped anyway) therefore do not change the output — only the *visible
    text content* does. This is what we hash, so only meaningful changes raise
    a proposal.
    """
    if html is None:
        return ""
    text = _COMMENT_RE.sub(" ", html)
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def sha256_hex(text: str) -> str:
    """SHA-256 hex digest of a (normalised) text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Domain row
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RuleChangeProposal:
    """One row destined for ``rce.rule_change_proposals``.

    ``status`` is fixed to ``"pending"`` at construction and the scraper has no
    code path that mutates it — see the module docstring.
    """

    source_id: str
    source_url: str
    captured_html_hash: str
    captured_text: str
    diff_summary: str
    rule_id: Optional[str] = None
    current_version_id: Optional[UUID] = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    proposal_id: UUID = field(default_factory=uuid4)
    status: ProposalStatus = PENDING

    def __post_init__(self) -> None:
        # Defence-in-depth: the scraper is structurally forbidden from emitting
        # anything other than a pending proposal. If a caller ever tries, fail
        # loud rather than silently auto-promoting a rule change.
        if self.status != PENDING:
            raise ValueError(
                "RuleChangeProposal from the scraper must be 'pending'; "
                f"got {self.status!r}. Promotion is a human-only action."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Injected Protocols (network + persistence + LLM) — all stubbed in tests.
# ─────────────────────────────────────────────────────────────────────────────


class HtmlFetcher(Protocol):
    """Fetches the raw HTML for a source URL.

    The production implementation (service layer) uses httpx with a 30-day
    cache-control respect and honours robots.txt. Tests inject a stub that reads
    fixture HTML — the test suite never touches the live sites.
    """

    def __call__(self, url: str) -> str: ...


class ProposalStore(Protocol):
    """Persistence contract for the proposal queue.

    The concrete Supabase/psycopg2 adapter lives one layer up (service layer).
    Tests use :class:`InMemoryProposalStore`.
    """

    def get_baseline_hash(self, rule_id: Optional[str]) -> Optional[str]:
        """Return the last captured normalised-text hash for ``rule_id``.

        This is the hash of the current ``rce.rule_versions.body`` source for
        the rule (the baseline the live page is diffed against). ``None`` if the
        rule has never been captured (first-seen).
        """
        ...

    def proposal_exists(self, rule_id: Optional[str], captured_html_hash: str) -> bool:
        """Whether a proposal already exists for this (rule_id, hash) pair.

        Mirrors the DB UNIQUE (rule_id, captured_html_hash) constraint so the
        scraper is idempotent across re-runs.
        """
        ...

    def get_baseline_text(self, rule_id: Optional[str]) -> Optional[str]:
        """Return the last captured normalised text for ``rule_id`` (for diffing)."""
        ...

    def insert_proposal(self, proposal: RuleChangeProposal) -> bool:
        """Persist a pending proposal. Returns True if inserted, False if the
        UNIQUE key already existed (ON CONFLICT DO NOTHING)."""
        ...


# A diff summariser turns (old_text, new_text) into a short human summary. The
# production wiring passes a gpt-4o-mini-backed callable (<=500 tokens); the
# default below is deterministic and offline so the scraper degrades gracefully
# and tests need no network.
DiffSummariser = Callable[[Optional[str], str], str]


def default_diff_summary(old_text: Optional[str], new_text: str) -> str:
    """Deterministic, offline fallback summary (no LLM)."""
    if old_text is None:
        return "New source captured (no prior baseline); manual review required."
    if old_text == new_text:
        return "No change detected."
    old_len, new_len = len(old_text), len(new_text)
    delta = new_len - old_len
    return (
        "Content changed since last capture "
        f"({old_len} -> {new_len} chars, delta {delta:+d}). "
        "Review numeric thresholds, dates, and eligibility predicates."
    )


# ─────────────────────────────────────────────────────────────────────────────
# In-memory store for tests
# ─────────────────────────────────────────────────────────────────────────────


class InMemoryProposalStore:
    """Hermetic test double for :class:`ProposalStore`.

    Seed baselines via :meth:`set_baseline`. Inserted proposals are appended to
    :attr:`proposals` and enforce the (rule_id, captured_html_hash) UNIQUE key.
    """

    def __init__(self) -> None:
        self._baseline_hash: Dict[Optional[str], str] = {}
        self._baseline_text: Dict[Optional[str], str] = {}
        self.proposals: List[RuleChangeProposal] = []
        self._seen_keys: set[Tuple[Optional[str], str]] = set()

    def set_baseline(self, rule_id: Optional[str], normalized_text: str) -> None:
        self._baseline_hash[rule_id] = sha256_hex(normalized_text)
        self._baseline_text[rule_id] = normalized_text

    def get_baseline_hash(self, rule_id: Optional[str]) -> Optional[str]:
        return self._baseline_hash.get(rule_id)

    def get_baseline_text(self, rule_id: Optional[str]) -> Optional[str]:
        return self._baseline_text.get(rule_id)

    def proposal_exists(self, rule_id: Optional[str], captured_html_hash: str) -> bool:
        return (rule_id, captured_html_hash) in self._seen_keys

    def insert_proposal(self, proposal: RuleChangeProposal) -> bool:
        key = (proposal.rule_id, proposal.captured_html_hash)
        if key in self._seen_keys:
            return False  # ON CONFLICT DO NOTHING — idempotent no-op
        self._seen_keys.add(key)
        self.proposals.append(proposal)
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScrapeResult:
    sources_fetched: int = 0
    pages_unchanged: int = 0
    proposals_created: int = 0
    duplicates_skipped: int = 0
    fetch_errors: int = 0
    proposals: List[RuleChangeProposal] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────────────────────


class RuleScraper:
    """Daily diff-based scraper. Writes pending proposals only — never promotes.

    All side-effecting dependencies are injected:

    * ``fetcher`` — :class:`HtmlFetcher` (stubbed in tests, httpx in prod).
    * ``store`` — :class:`ProposalStore` (in-memory in tests, Supabase in prod).
    * ``diff_summariser`` — optional; defaults to the deterministic offline
      summary. Production passes a gpt-4o-mini-backed callable.
    """

    def __init__(
        self,
        *,
        fetcher: HtmlFetcher,
        store: ProposalStore,
        sources: Sequence[RuleSource] = RULE_SCRAPER_SOURCES,
        diff_summariser: DiffSummariser = default_diff_summary,
    ) -> None:
        self._fetcher = fetcher
        self._store = store
        self._sources = tuple(sources)
        self._summarise = diff_summariser

    def run(self) -> ScrapeResult:
        result = ScrapeResult()
        for source in self._sources:
            try:
                raw_html = self._fetcher(source.url)
            except Exception:
                result.fetch_errors += 1
                continue
            result.sources_fetched += 1

            normalized = normalize_text(raw_html)
            new_hash = sha256_hex(normalized)

            # A source can feed multiple rule_ids; each is diffed independently
            # against its own baseline.
            for rule_id in source.rule_ids:
                self._process_rule(source, rule_id, normalized, new_hash, result)
        return result

    def _process_rule(
        self,
        source: RuleSource,
        rule_id: Optional[str],
        normalized: str,
        new_hash: str,
        result: ScrapeResult,
    ) -> None:
        baseline_hash = self._store.get_baseline_hash(rule_id)

        # Unchanged page → no-op. This is the common daily case.
        if baseline_hash == new_hash:
            result.pages_unchanged += 1
            return

        # Idempotency: a proposal for this exact (rule_id, hash) may already
        # exist from a prior run before the human resolved it.
        if self._store.proposal_exists(rule_id, new_hash):
            result.duplicates_skipped += 1
            return

        baseline_text = self._store.get_baseline_text(rule_id)
        try:
            summary = self._summarise(baseline_text, normalized)
        except Exception:
            # LLM failure must never block the queue or auto-resolve — fall back
            # to the deterministic summary and still write a pending proposal.
            summary = default_diff_summary(baseline_text, normalized)

        proposal = RuleChangeProposal(
            source_id=source.source_id,
            source_url=source.url,
            captured_html_hash=new_hash,
            captured_text=normalized,
            diff_summary=summary,
            rule_id=rule_id,
            status=PENDING,  # explicit: scraper writes pending and only pending
        )
        inserted = self._store.insert_proposal(proposal)
        if inserted:
            result.proposals_created += 1
            result.proposals.append(proposal)
        else:
            result.duplicates_skipped += 1
