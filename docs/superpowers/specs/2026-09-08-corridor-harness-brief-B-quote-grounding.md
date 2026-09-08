# Cursor Brief B — quote-grounding engine (`--grounding-dir` + `--report`)

- **Deliverable:** `backend/imports/otto/quote_grounding.py` (new, self-contained) +
  `scripts/tests/test_quote_grounding.py` (new).
- **Runtime:** Python 3.11. Stdlib only (no `requests`, no network in this module). Uses `argparse`
  for the thin CLI.
- **You (Cursor) have no repo access.** Do **not** try to modify `scripts/verify_batch_quotes.py` —
  you can't see it. Build a self-contained engine with injected seams; the integrator (Claude Code)
  grafts it onto `verify_batch_quotes.py` so Brief A's invocation
  `verify_batch_quotes.py <dir> --grounding-dir <dir> --report <json> --target <ndjson>` works.

---

## 0. Why this exists

The referee (`verify_ledger.py` / `verify_batch_quotes.py`) confirms each fact's `evidence_quote` is
verbatim on its cited page by fetching that page over HTTP. JS-rendered gov pages, PDFs, and
bot-walled sites return nothing to an HTTP fetch, so their quotes can't be confirmed that way. The
**applier** (Claude Code) reads those pages in a real in-app browser and drops the rendered text into
a *grounding directory*. This engine lets the quote check consume that captured text — so a quote can
be confirmed against a browser-grounded page — while stamping a **distinct provenance** so a
browser-grounded confirmation is never silently laundered into the researcher's own
`quote_verbatim_confirmed` flag (which has been wrong: Indonesia BPJS, Taiwan).

It also emits a **machine-readable report** the orchestrator (Brief A, stage 3) reads to decide
whether to pause for an applier hop.

---

## 1. The two vocabularies you're bridging (embedded — you can't see them)

Each fact record (one JSON object per NDJSON line) carries at least:
```jsonc
{ "destination_country": "PT", "entity_topic_key": "residence_permit", "fact_key": "processing_time",
  "fact_text": "…", "source_url": "https://imigrante.sef.pt/…",
  "evidence_quote": "o prazo de decisão é de 90 dias",      // may be absent
  "applies_to": { … },                                       // jsonb; you MUST NOT mutate its meaning
  "dedupe_key": "PT|residence_permit|processing_time" }      // may be absent; derive if so
```
`dedupe_key`, if absent, is `f"{destination_country}|{entity_topic_key}|{fact_key}"`.

**Verbatim matching MUST reuse the repo's normaliser** for parity with the 350+ rows already verified
that way. You can't import it, so take it as an **injected callable** `normalise(str) -> str`; the
integrator wires `backend.app.services.fact_evidence.normalise`. Your module ships a *default*
`normalise` (lowercase, collapse whitespace, strip a small punctuation set) used **only** by your
tests. A quote is "present" iff `normalise(evidence_quote)` is a substring of `normalise(page_text)`.

---

## 2. Public API (pure, injected — this is what the orchestrator and tests call)

```python
def check_quotes(
    records: list[dict],
    *,
    text_for_url: Callable[[str], str | None],   # returns page text for a source_url, or None if unavailable
    normalise: Callable[[str], str],             # injected; parity with fact_evidence.normalise
) -> list[QuoteVerdict]: ...

@dataclass
class QuoteVerdict:
    dedupe_key: str
    source_url: str
    evidence_quote: str | None
    status: str        # 'confirmed' | 'not_on_page' | 'unreachable' | 'no_quote'
    grounded_by: str | None   # 'http_fetch' | 'browser_grounded' | None
```
Rules:
- `evidence_quote` absent/empty ⇒ `no_quote`, `grounded_by=None` (informational, not a failure).
- `text_for_url(url)` returns `None` ⇒ `unreachable`, `grounded_by=None`.
- text returned and quote present ⇒ `confirmed`; text returned and quote absent ⇒ `not_on_page`.
- `grounded_by` is set by the **caller's** `text_for_url` — see §3 (the grounding loader tags its
  source). `check_quotes` copies the tag the loader attached; if the loader can't tag, default
  `http_fetch`. (Simplest: `text_for_url` returns `(text, source_tag)`; pick that shape.)

Use the two-value return: `text_for_url(url) -> tuple[str | None, str]` where the second element is
`'browser_grounded'` when the text came from the grounding dir, else `'http_fetch'`.

## 3. Grounding-dir loader

```python
def grounding_text_for(url: str, grounding_dir: Path) -> str | None: ...
```
- Canonical format of `grounding_dir`:
  - `index.json` = `{ "<source_url>": "<relative-filename.txt>", … }` (authoritative), plus the UTF-8
    text files it names.
  - If `index.json` is absent, fall back to `<slug(url)>.txt` where
    `slug = re.sub(r'[^a-z0-9]+','-', url.lower()).strip('-')[:120]`.
- Return the file's text, or `None` if neither the index entry nor the slug file exists.
- The applier (Claude Code) writes this directory between a pause and a resume; your loader only reads.

Compose the two sources into one `text_for_url` the orchestrator uses:
```python
def make_text_resolver(fetched: dict[str, str], grounding_dir: Path | None):
    # 'fetched' = URL -> already-fetched/cached HTTP text (supplied by verify_batch_quotes at integration)
    def resolve(url):
        if grounding_dir is not None:
            g = grounding_text_for(url, grounding_dir)
            if g is not None:
                return g, "browser_grounded"      # grounding dir WINS — it's the applier's deliberate capture
        t = fetched.get(url)
        return (t, "http_fetch") if t is not None else (None, "http_fetch")
    return resolve
```
Grounding-dir text **wins** over a cached HTTP fetch for the same URL: if the applier bothered to
browser-ground a source, that capture is the intended evidence.

## 4. CLI (thin wrapper, for standalone use + the orchestrator)

```
python -m backend.imports.otto.quote_grounding <ndjson> [--grounding-dir DIR] [--report JSON] [--fetched-cache DIR]
```
- `<ndjson>`: the fact stream to check (the orchestrator passes `clean.ndjson` explicitly — see the
  `--target` note below). Read records from here.
- `--grounding-dir DIR`: as §3.
- `--fetched-cache DIR`: optional dir of pre-fetched page text keyed by an `index.json` (same format
  as grounding-dir) — lets the CLI run **without network** by consuming text someone already fetched.
  In the integrated `verify_batch_quotes.py`, the integrator supplies the live HTTP fetch instead;
  in your CLI + tests, this cache is the only text source besides grounding-dir.
- `--report JSON`: write the machine-readable report (§5). Also print a human summary.
- CLI uses the **default** normalise (tests/standalone). The integrated path injects the real one.
- **Exit:** `1` if any verdict is `not_on_page` or `unreachable` (a real gap); `0` otherwise
  (`confirmed`/`no_quote` only). This mirrors `verify_batch_quotes`'s gating semantics so Brief A's
  stage 3 can rely on it.

**Integrator note (not your task):** I graft `--grounding-dir`, `--report`, and a `--target <ndjson>`
selector onto `scripts/verify_batch_quotes.py` by calling `check_quotes(...)` with the real
`fact_evidence.normalise` and the script's existing fetch/cache as `fetched`. `--target` fixes the
current "first `*.ndjson` in the dir" ambiguity (the batch dir will hold several NDJSON by then).

## 5. Report JSON (`--report`) — what the orchestrator reads

```jsonc
{
  "ndjson": "docs/imports/<batch>/_harness/clean.ndjson",
  "grounding_dir": "docs/imports/<batch>/_harness/grounding/",   // or null
  "counts": {"confirmed": 7, "not_on_page": 1, "unreachable": 2, "no_quote": 3},
  "grounded_by": {"http_fetch": 5, "browser_grounded": 2},
  "needs_grounding": [                                            // the pause worklist for stage 3
    {"source_url": "https://iras.gov.sg/…", "evidence_quote": "…", "dedupe_key": "SG|tax_residence|183_day"}
  ],
  "verdicts": [ {"dedupe_key": "…", "source_url": "…", "status": "confirmed", "grounded_by": "browser_grounded"} ]
}
```
`needs_grounding` = every verdict whose status is `unreachable` (the applier can ground these) — NOT
`not_on_page` (those are a genuine quote-mismatch the applier can't fix by re-reading; they surface in
the report but do not go on the grounding worklist).

## 6. Acceptance tests you deliver green — NO network

Load the module by path with `importlib.util.spec_from_file_location` (the `scripts/` vs
`backend/scripts/` shadowing hazard — do not `from scripts... import`). Fixtures are tiny inline
NDJSON + inline text files under `tmp_path`.

1. **confirmed via HTTP cache** — a record whose quote is verbatim in a `--fetched-cache` text ⇒
   `confirmed`, `grounded_by='http_fetch'`, exit 0.
2. **confirmed via grounding-dir** — same record, no cache entry, but a `grounding_dir/index.json`
   pointing at a text file that contains the quote ⇒ `confirmed`, `grounded_by='browser_grounded'`.
3. **grounding wins over cache** — both present, cache text lacks the quote, grounding text has it ⇒
   `confirmed`, `grounded_by='browser_grounded'`.
4. **not_on_page** — text present (either source) but quote absent ⇒ `not_on_page`, exit 1, and the
   verdict is **absent** from `needs_grounding`.
5. **unreachable** — no cache, no grounding file ⇒ `unreachable`, exit 1, and the verdict **is** in
   `needs_grounding`.
6. **no_quote** — record without `evidence_quote` ⇒ `no_quote`, does not affect exit code on its own.
7. **slug fallback** — grounding-dir with no `index.json` but a `<slug(url)>.txt` present ⇒ resolves.
8. **report shape** — `--report` writes the JSON of §5 with correct `counts`, `grounded_by`,
   `needs_grounding`, `verdicts`.
9. **normalise parity hook** — passing a custom `normalise` that upper-cases both sides still matches
   (proves matching goes through the injected normaliser, not a hardcoded one).
10. **dedupe_key derivation** — a record without `dedupe_key` derives
    `dest|entity_topic_key|fact_key`.

## 7. Do NOT
- fetch anything over the network in this module (the integrated script owns HTTP);
- mutate `applies_to` or write the researcher's `quote_verbatim_confirmed` flag — browser-grounded
  confirmations are reported as `grounded_by='browser_grounded'`, never as the researcher's flag;
- put `not_on_page` rows on the grounding worklist (a re-read can't fix a genuine mismatch);
- import from `scripts.*` or `backend.app.*` at module top level — take `normalise` as an argument.

## 8. Return to the integrator
The two files + a 3-line note: the exact `python -m pytest …` that greens your tests, and the default
`normalise` you shipped (so I can confirm it's a reasonable stand-in for `fact_evidence.normalise`).
