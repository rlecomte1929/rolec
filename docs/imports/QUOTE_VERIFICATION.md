# Evidence-quote verification

`scripts/verify_batch_quotes.py <batch-dir>` fetches every `source_url` a batch cites, stores
the extracted text under `<batch-dir>/sources/`, and checks that each `evidence_quote` actually
appears on the page it claims to come from. Exit code is non-zero if any quote is missing or any
source is unreachable, so it can gate a batch.

Nothing in this repo checked this before. `check_corridor_facts` asserts a quote is present and
long enough; the delivery gate asserts it is non-empty. Neither ever opened the source. That is
how production came to hold 705 facts whose quote is not a substring of the document they cite.

The stored text is also what the promotion needs: `requirement_facts.source_doc_id` is NOT NULL,
and 8 of the ES→IE batch's 10 URLs had no `knowledge_docs` row. The alternative — a placeholder
document — is exactly what makes a quote unverifiable forever.

## Results, 2026-08-23

| batch | verbatim-present | unchecked | verdict |
|---|---|---|---|
| `es-ie-thirdcountry-requirements-2026-08-22` | **38 / 38** | 0 | every quote confirmed against its live source |
| `no-fr-general-curated-2026-08-22` | 5 / 14 | 3 | 9 quotes are near-verbatim but not verbatim |

**ES→IE passes cleanly.** All ten sources fetched, including the Irish health primary — which is
a 53-page PDF (*HSE National Assessment Guidelines for Medical Card and GP Visit Card*, effective
01/04/2026) served from a URL that looks like HTML. Regex-stripping it yields binary noise that
reads exactly like a dead source; it is extracted with pypdf instead.

**NO→FR does not, and its own metadata already said so** — all 17 records carry
`quote_verbatim_confirmed: false`. The nine misses are not fabrications: the wording is on the
page, but the quote drops punctuation the source renders (`(UE + EEE + Suisse):` quoted without
the colon) or flattens a bulleted list. Near-verbatim is still not verbatim, and the fix is for
the researcher to re-copy the quotes, not for this checker to keep loosening until they pass.

Three more could not be checked at all, and that is reported as *unchecked*, never as a pass:
- `urssaf.fr` resets the connection to an automated fetch.
- `legifrance.gouv.fr` answers with a Cloudflare interstitial ("Just a moment...").

An unreachable source is not a disproof. A source that looks dead is usually a transient outage
or a bot wall — the HSE URL was once "replaced" on exactly that mistake.

## Normalisation, and why each step is not cheating

Words are never reordered, dropped or substituted, so a paraphrase still fails. What is folded:
HTML/entities/whitespace; curly quotes and dashes; list bullets; a space before `,.;:!?)` left
behind by stripping `<a>`/`<li>`; `/` where a researcher flattened a bulleted list; and the
literal `titlecontent` template token that `service-public.fr` renders inside its own sentences.

## Fetching

Uses `curl`, not `urllib`: several statutory sites sit behind a WAF that answers `urllib` with
403 and `curl` with 200, so a `urllib` fetch reports a live source as dead.
