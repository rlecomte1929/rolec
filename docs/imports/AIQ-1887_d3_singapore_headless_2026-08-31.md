# AIQ-1887 D3 — headless render for the mom.gov.sg JS shell

Companion to `AIQ-1887_vc1_demotion_2026-08-31.md`. That file closed VC1 (a disproved fact must
not stay approved). This one gives the fetcher a way to *check* the largest still-unverifiable
cluster: Singapore.

## The problem

`www.mom.gov.sg` is an Angular application. It returns HTTP 200, but the body is a shell — the
work-pass content is rendered client-side by JavaScript. `httpx` (what the backfill uses) plus
`immigration_page_parser` see no article text, so the quote check has nothing to match against
and every Singapore fact stays `evidence_verified IS NULL`. A different User-Agent does nothing;
the page needs a browser.

Measured on prod (`nsvefcvpvwwwhuqyuqmp`, 2026-08-31): **49 served, never-checked SG facts**
across **9 URLs** — the single biggest slice of the served-unchecked cohort (65 total).

| mom.gov.sg URL | facts |
|---|---:|
| `/passes-and-permits/employment-pass/eligibility` | 13 |
| `/passes-and-permits/employment-pass/apply-for-a-pass` | 11 |
| `/passes-and-permits/dependants-pass/eligibility` | 8 |
| `/passes-and-permits/long-term-visit-pass/eligibility` | 4 |
| `/passes-and-permits/overseas-networks-expertise-pass/eligibility` | 4 |
| `/passes-and-permits/entrepass/eligibility` | 4 |
| `/passes-and-permits/overseas-networks-expertise-pass/passes-for-families` | 2 |
| `/passes-and-permits/dependants-pass/documents-required` | 2 |
| `/passes-and-permits/employment-pass/documents-required` | 1 |
| **total** | **49** |

## The fix (this PR)

`backend/scripts/backfill_fact_evidence.py` gains an opt-in `--headless` fallback. When a page
returns 200 but parses to empty text (the client-rendered-shell case, and *only* that case — not
a 404, not a 401/403/429 block), the fetcher renders it with headless Chromium via Playwright and
parses the rendered DOM.

- **Playwright is not a hard dependency.** It is imported lazily and only reached under
  `--headless`. Absent it, `render_headless` returns `None` and the run degrades to the same
  `js_shell_or_empty` result as before — the httpx path, the rest of the backfill, and CI (which
  has no browser) are unaffected.
- A rendered fetch is reported with `reason='fetched_headless'` and otherwise flows through the
  existing evidence check unchanged: a quote that now appears becomes `evidence_verified = TRUE`;
  a quote that still does not appear is a real disproof and — via the VC1 fix in this same PR —
  the fact is demoted from approved to pending rather than left wearing a badge it did not earn.

## Validation

- **Unit tests** (`backend/tests/test_backfill_headless_fallback.py`, 4): the fallback fires only
  on an empty parse, only with `--headless`, uses the rendered text, and degrades to
  `js_shell_or_empty` when the render yields nothing — all with the browser stubbed, so CI needs
  no Chromium.
- **Real render proven locally**: `render_headless` launched Chromium and executed JS on a local
  `data:` page whose text exists only after JS runs; the parser then extracted it. The render →
  parse pipeline works.
- **Not validated here — the live mom.gov.sg fetch.** This build environment blocks all external
  egress by policy (the agent proxy returns 403 CONNECT for `www.mom.gov.sg` and every other
  external host), so the 49-fact run must happen where gov.sg is reachable. That is the operator
  step below.

## Operator runbook (where gov.sg egress exists)

```bash
pip install playwright && playwright install chromium   # browser once; PLAYWRIGHT_BROWSERS_PATH
                                                         # or PLAYWRIGHT_CHROMIUM_EXECUTABLE also work

# 1. Dry run — renders, checks quotes, writes nothing. Expect fetched_headless in the FETCH block.
python backend/scripts/backfill_fact_evidence.py --dest SG --status approved --only-unchecked --headless

# 2. If the verdicts look right, apply. Verified quotes -> evidence_verified TRUE; disproved
#    quotes -> demoted to pending (VC1). NULL (still unrenderable) stays served.
python backend/scripts/backfill_fact_evidence.py --dest SG --status approved --only-unchecked --headless --apply
```

`--only-unchecked` scopes the run to the never-checked facts, so an already-verified SG fact is
never put back at risk. Re-run is safe.

## Out of scope (unchanged)

- `travel.state.gov` (7 US facts) — a hard Cloudflare block that a browser does not fix; a genuine
  "dead source" finding, left NULL/served with an unverified badge.
- The VC1 residue D1 sweep and D4 (provenance FK) — tracked in the companion doc.
