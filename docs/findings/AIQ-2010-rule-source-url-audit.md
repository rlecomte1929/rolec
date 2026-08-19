# AIQ-2010 — 20 of 34 rule versions cite a source URL that has never existed

**Audited:** 2026-08-19 · **Method:** HTTP probe of all 28 distinct `rce.rule_versions.source_url`
values, one polite request each, honest user-agent, redirects followed.

The task was "point the crawler at the URLs the rule versions cite." Doing that required listing
those URLs first. Most of them are 404s, and they are 404s in a way that indicates they were
constructed rather than collected.

---

## 1. The audit

| verdict | rule versions | distinct URLs |
|---|--:|--:|
| **LIVE** — HTTP 200 | 14 | 8 |
| **DEAD** — HTTP 404, fabricated | **20** | **20** |
| bot-protected | 0 | 0 |

**59% of the rule engine's citations point at pages that do not exist.**

### The eight that are real

All returned 200:

```
https://eur-lex.europa.eu/eli/dir/2021/1883/oj              (6 rule versions)
https://www.gesetze-im-internet.de/aufenthg_2004/__18g.html (2)
https://www.gesetze-im-internet.de/aufenthg_2004/__18.html
https://www.gesetze-im-internet.de/aufenthg_2004/__18b.html
https://www.gesetze-im-internet.de/aufenthg_2004/__27.html
https://www.gesetze-im-internet.de/aufenthg_2004/__82.html
https://www.gesetze-im-internet.de/beschv_2013/
https://www.bundesanzeiger.de/
```

### The twenty that are not

Every dead URL has the same shape: `https://www.gesetze-im-internet.de/Teilliste_<citation>.html`.
`gesetze-im-internet.de` is the **German federal law portal**. The citations pasted into that
template are, in the main, not German law:

| fabricated URL fragment | what the citation actually is |
|---|---|
| `Teilliste_Folkeregisterloven+§4-1` | Norwegian population registration act |
| `Teilliste_Utlendingsloven+§109` / `§110` / `§117` | Norwegian immigration act |
| `Teilliste_Ley+7/1985+(empadronamiento)` | Spanish municipal register law |
| `Teilliste_Real+Decreto+240/2007` | Spanish free-movement decree |
| `Teilliste_Wet+BRP+(Basisregistratie+Personen)` | Dutch population register act |
| `Teilliste_Zorgverzekeringswet+(Zvw)` | Dutch health insurance act |
| `Teilliste_KVG/LAMal` | Swiss health insurance act |
| `Teilliste_VEP/OLCP` | Swiss free-movement ordinance |
| `Teilliste_CGI+art.+4+B` | French tax code |
| `Teilliste_AIG/LEI` | Swiss foreign nationals & integration act |
| `Teilliste_EEA+Agreement+Art.+28` | EEA Agreement |
| `Teilliste_EU–CH+Agreement+…+(AFMP)` | EU–Switzerland agreement |
| `Teilliste_Skatteetaten+—+emigration+/+tax+residence` | Norwegian tax authority guidance |

Norwegian, Spanish, Dutch, Swiss and French law is not published on the German federal law site.
These URLs were produced by taking a legal reference and formatting it into a URL pattern, not by
visiting a page. Even the genuinely German ones in that set (`Teilliste_BMG+§17`,
`Teilliste_SGB+V+§193`, `Teilliste_FreizügG/EU+§2` and `§5`) are 404 — the `Teilliste_` prefix is
not how that site addresses statute sections.

This is the architecture rule in `docs/HANDOFF-2026-08-15.md` inverted:

> "**No fabricated source URLs** — every `requirement_facts` row needs HTTP-200-verified
> `source_url` + verbatim `evidence_quote`."

## 2. Why the crawler could never have matched

The crawler's `sources.json` targeted **eight general newcomer portals** — make-it-in-germany,
handbookgermany, welcometofrance, service-public.fr, oslo.kommune.no, ruter.no, nyinorge.no. The
rule engine cites **legal texts**. The two sets were disjoint by construction, which is why the
crawled ⋈ rule_versions join returned 0 and why `source_change_reviews.rule_version_id`
(NOT NULL) could never be satisfied.

They were never wrong *relative to each other* — they were built for different purposes and
nobody connected them.

## 3. What this change does, and does not, do

**Does:** adds the eight verified-live legal sources to `backend/crawler/config/sources.json` as
active targets, so a change on a page a rule actually cites becomes attributable. The pre-existing
portal sources are retained — they feed the corpus and serve a different purpose; removing them
would be a silent regression elsewhere.

Chosen home: `sources.json`, not a new table. It is the established, version-controlled home for
crawl targets, loaded by `crawler/config/registry.py`, and a change to it is reviewable in a PR. A
table would allow runtime edits, but there is no admin surface for one and no other justification
for a migration.

`robots.txt` checked for all three hosts before adding: `gesetze-im-internet.de` allows
everything; `bundesanzeiger.de` disallows only `/nlp` and a maintenance page;
`eur-lex.europa.eu` permits `/eli/` but sets **`Crawl-delay: 10`**, recorded in that source's
notes and to be honoured by whatever runs the crawl.

**Does not:** fix the 20 fabricated citations. Crawling cannot repair them, and pointing a crawler
at a 404 would be worse than leaving it — it would generate a steady stream of "unchanged"
results that reads as a stable source rather than a missing one. A test
(`test_no_fabricated_citation_is_ever_crawled`) now prevents exactly that.

## 4. What has to happen next — and it is not a crawler task

The 20 affected rule versions need **re-sourcing**: a human or a sourcing pipeline finding the
real published URL for each citation and replacing it, with the HTTP-200 check enforced at write
time so this cannot recur.

Until then, be careful what those 20 rule versions are used for. A citation is the thing that
makes a rule defensible; 20 of 34 currently cannot be checked by anyone who follows the link.
That is a content-integrity issue, and arguably a higher priority than the pipeline repair this
task belongs to.

---

### Evidence index

| claim | check |
|---|---|
| 28 distinct cited URLs, 34 rule versions | `SELECT count(*), count(DISTINCT source_url) FROM rce.rule_versions WHERE source_url <> ''` |
| 8 live / 20 dead | one `curl -L` per URL, 2026-08-19, recorded above |
| crawled ⋈ rule_versions = 0 | join on `COALESCE(final_url, source_url) = rv.source_url` |
| crawler targeted portals, not legal texts | `backend/crawler/config/sources.json` before this change |
| robots.txt permits the 8 | fetched per host, 2026-08-19 |
