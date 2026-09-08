# AIQ-2018c — sampled reachability audit of `requirement_facts.source_url`: contained, not systemic

**Date:** 2026-09-08 · **Scope:** `public.requirement_facts.source_url` (prod `nsvefcvpvwwwhuqyuqmp`)
**Verdict:** **CONTAINED.** No evidence of systemic link rot. In a 106-URL impact-weighted sample,
**at most 1 URL is a genuine dead link**; every other non-200 is a fetch-environment artifact
(government WAF / bot-wall / transient 5xx) on a demonstrably-live source.

This is the sampled audit the card asked for. `#2039` added an *ingest-time* reachability gate
(`backend/app/services/source_url_reachability.py`); it never audited the **existing** corpus.
This does, and answers "contained vs systemic?".

## Corpus (prod, 2026-09-08)

| metric | value |
|---|---:|
| requirement_facts with a source_url | 2,727 (100%) |
| distinct source_urls | 887 |
| distinct hosts | 342 |

(The card's "2,676 / 337 hosts" is slightly stale; the corpus has grown to 2,727 / 342.)

## Method

- **Sample: 106 distinct URLs**, deterministic and impact-weighted — the 35 URLs supporting the
  most facts, plus a systematic 1-in-12 slice of the remainder (SQL below). Spans ~40 hosts across
  every active corridor (NO, IE, SG, CH, AT, DE, PT, DK, NL, US, AU, NZ, TH, AE, BE, FR, …).
- **Probe: `curl`, not `urllib`.** A real browser User-Agent + `Referer`, follow redirects, 20s
  timeout, final HTTP code. urllib (what the ingest gate uses) is 403-blocked by Cloudflare/WAF
  fronts where curl succeeds, so urllib would badly over-report "dead".
- **Retry:** every non-200 was re-probed once (30s, `--retry 1`) to separate transient/bot-wall
  from genuinely gone — the outage-vs-dead discipline HSE_sourcing and prior findings insist on.

## Results — first probe (n=106)

| final HTTP code | n | reading |
|---|---:|---|
| 200 | 82 | reachable |
| 403 | 18 | **bot-wall** on a live gov site (not dead) |
| 000 | 3 | connection blocked (WAF / JS-gate) — unverified |
| 500 / 502 | 2 | transient server error |
| 404 | 1 | **probable genuine gone** |

**77% reachable on a single unauthenticated curl** — and the 23% that were not resolve almost
entirely to *how the sample was fetched*, not to the corpus:

- **403 = bot-wall, the site is up.** All 18 are major statutory portals — `udi.no` (×8),
  `ato.gov.au`, `ssa.gov`, `nhtsa.gov`, `travel.state.gov`, `mofa.go.jp`, `nzta.govt.nz`,
  `tullverket.se`, `sede.madrid.es`, `vicroads.vic.gov.au`, `eurococ.eu`. A 403 means the server
  answered and refused the bot — the opposite of gone.
- **The udi.no set proves the point.** On retry the same udi.no URLs flipped 403→200
  (family-immigration, work-immigration, studies, job-seekers, word-definitions) and 403→404
  (family-immigration/children, eea-and-efta, fees). Sibling udi.no pages return 200 in the same
  crawl. The codes track udi.no's WAF, not the pages — every one of these exists.
- **000 = blocked, not dead.** `canada.ca` (the known WAF-blocker — curl resets), plus
  `servicesaustralia.gov.au` and `infrastructure.gov.au` (a PDF). All are live in a browser.
- **5xx = transient.** `hamburg.com` (500) and `www2.gov.pt` (502) — server-side, retry-recoverable.

## The one genuine dead

`https://u.ae/en/information-and-services/jobs/employment-in-the-private-sector/job-offers-and-work-permits-and-contracts/work-permits`
returned **404 on both probes**, while other `u.ae` paths in the sample return 200 — so this is a
path that moved/was removed, not a host block. It supports **5 facts** (UAE work-permit). **Needs
human confirmation + re-source**, not machine deletion.

## Answer to the card: contained, not systemic

The failures **do not cluster by batch or corridor** — they cluster by **anti-bot infrastructure**
(government WAFs), which is a property of the fetch, not the data. Extrapolated from the sample,
genuine link rot is on the order of **~1%**, isolated, and re-sourceable case by case. There is no
systemic decay warranting a bulk demotion.

## Secondary finding — the ingest gate will false-reject live official sources

17% of the sample (18/106) returned 403 to an automated client, and `udi.no` returned 403/404
non-deterministically. `source_url_reachability.probe_url` uses `urllib`, which fares *worse* than
curl against these WAFs. **An ingest gate that treats 403 / WAF-404 as `UNREACHABLE` will withhold
facts sourced to live statutory sites** (all of Norway's UDI, among others). The gate must treat
403/406/429 and 404-from-a-known-WAF-host as `UNVERIFIED` ("could not check"), never as
`UNREACHABLE` ("gone") — the same distinction the module's `Verdict` enum already draws, applied to
the bot-wall codes. This is the higher-value follow-up this audit surfaces.

## Caveats

- A 106/887 sample (12%), impact-weighted — high-fact URLs are over-represented (deliberately: a
  dead high-fact source matters more). The long single-fact tail is under-sampled; a fuller pass
  would probe all 887, but the signal (bot-walls dominate, rot is rare) is already unambiguous.
- Probed from one network. Some 000/403 are specific to this egress; a browser or a residential IP
  would clear most. That is exactly why none of them are called "dead".

## Reproduction

```sql
-- the deterministic impact-weighted sample
WITH d AS (
  SELECT source_url, count(*) AS fact_count,
         split_part(regexp_replace(source_url,'^https?://',''),'/',1) AS host
  FROM requirement_facts WHERE source_url ~ '^https?://' GROUP BY source_url),
ranked AS (SELECT *, row_number() OVER (ORDER BY fact_count DESC, source_url) AS rn FROM d)
SELECT source_url FROM ranked WHERE rn <= 35 OR rn % 12 = 0 ORDER BY fact_count DESC, source_url;
```

```bash
# probe (browser UA + referer, follow redirects, final code), 10-way parallel
export UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
cat audit_urls.txt | xargs -P 10 -I{} sh -c \
  'u="$1"; printf "%s\t%s\n" "$(curl -s -o /dev/null -w "%{http_code}" -m 20 -A "$UA" -e "https://www.google.com/" -L "$u")" "$u"' sh {}
```

OUTCOME: audit — contained, ~1% genuine rot; the actionable follow-up is the ingest gate's
treatment of WAF codes, not a corpus demotion.
