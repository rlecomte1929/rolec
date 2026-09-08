# Coverage-campaign verification priors (the "model card")

A living distillation of what the 2026-08-31 destination-coverage campaign learned about
sourcing and confirming facts + providers. It has two jobs:

1. **Feed the generators.** The recurring failure modes below are exactly what makes a
   research subagent waste a pass or emit a fact the applier then has to hold. Paste the
   relevant bullets into each new fact/provider brief so the *generation* side avoids them.
2. **Operate the referee.** `scripts/confirm_quotes.py` encodes the fact taxonomy as a
   deterministic classifier; its per-fact verdicts append to
   `docs/imports/_verification_ledger.ndjson` — the accumulating labelled dataset. Re-tune
   the thresholds there against that ledger, never by eyeballing one batch.

The land/hold rule the campaign settled on: **promote `CONFIRMED`; browser-verify
`REVIEW_BROWSER` and promote only if it checks out; never promote a `HOLD_*` on the
researcher's say-so.** Holding beats shipping an unreproducible quote — that discipline is
the whole trust architecture.

## 1. Pillars (hard)
`applies_to.pillar` MUST be one of the 7 catalog pillars: **EMPLOYMENT, HEALTHCARE, HOUSING,
IDENTITY, RESIDENCE, SOCIAL_SECURITY, TIMELINE**. Research often reaches for IMMIGRATION /
TAX / FAMILY — those are NOT catalog pillars and `promote` refuses them. Mapping:
`IMMIGRATION→RESIDENCE`, `FAMILY→RESIDENCE` (residence-permit content), `TAX/PAYROLL→EMPLOYMENT`
(the importer aliases these). `fixpillars` applies the remap; brief subagents with the 7
directly and it stops happening (~0 remaps after wave 3).

## 2. Fact-source confirmation taxonomy (what `confirm_quotes.py` decides)
| verdict | signal | action |
|---|---|---|
| `CONFIRMED` | exact substring OR ≥85% word-bigram overlap (any encoding/extractor) | promote |
| `REVIEW_BROWSER` | 50–85% overlap (present but markup/column-split), OR a tiny/blocked/JS-shell response | drive the in-app browser to the page; it passes WAF/Cloudflare that curl doesn't |
| `HOLD_IMAGE_PDF` | `%PDF` but 0 extractable chars in pdfplumber+pypdf (scanned) | re-source via OCR or the rendered HTML equivalent |
| `HOLD_WRONG_SRC` | source extracts lots of text but <15% overlap | the cited URL is wrong (portal upgrade changed the path, or a `.pdf` URL served an HTML error page) — re-source |
| `HOLD_ABSENT` | text extracts fine, 15–50% overlap | quote genuinely not on that page |

Extraction cascade the tool runs so *you don't have to by hand*: HTML → try utf-8 **and
latin-1/cp1252** (Spanish/`sii.cl` pages are latin-1; utf-8 mangles the accents and drops the
match); PDF → **pdfplumber default, pdfplumber `layout=True`, then pypdf** (column-scrambled
gov PDFs — India MHA, Japan ISA — miss under pypdf's default order but confirm under
pdfplumber layout).

## 3. Known-hard sources — steer generators to the reachable equivalent
- **Scanned/image PDFs (no text layer):** South Africa DHA visa PDFs, Romania ANAF fiscal-
  residence guide. Brief: *prefer the rendered gov HTML page over the PDF; if only a scanned
  PDF exists, flag it — don't claim a verbatim quote you can't reproduce.*
- **Portal upgrades that break PDF/hashed URLs:** Malaysia `hasil.gov.my` (media-hash paths
  changed → 404/misattribution), `esd.imi.gov.my` FAQ PDFs. Brief: *quote the current live
  HTML page, capture its URL fresh; don't cite a cached/hashed PDF path.*
- **WAF/Cloudflare/JS portals (curl 403 or 118-byte stub, browser works):** Qatar
  `hukoomi.gov.qa`, Israel `www.gov.il`, Bahrain `lmra.gov.bh`, Thailand `immigration.go.th`
  + `doe.go.th` (interactive CAPTCHA), `ibo.org`. Brief: *browser-ground these; for Thai
  Immigration facts use the parent-agency Act PDF on `royalthaipolice.go.th` instead.*
- **Latin-1 pages:** Chile `sii.cl`. The referee already re-decodes; no brief change needed.

### 3a. Empirical hold-hosts (from `_verification_ledger.ndjson`, 120 labelled facts)
The ledger's confirmed rate rose from the pre-priors batches (ZA 23%, KR 30%, MY 42%) to the
priors-briefed wave-8 batches (MT 100%, IS 92%, EE 77%, CY 100% via the browser path) — better
briefs measurably raise first-pass confirmation. The chronically-unconfirmable hosts, ranked by
hold count, are the standing re-source worklist — **do not cite a verbatim quote to these from a
headless fetch:**
`dha.gov.za` (image PDFs), `hasil.gov.my` + `esd.imi.gov.my` (portal-upgraded / misattributed
paths), `immigration.go.kr` + `nts.go.kr` (column-scrambled PDFs — pdfplumber layout sometimes
recovers), `static.anaf.ro` (image PDF), `sii.cl` (latin-1 — the referee handles it). WAF/JS hosts
that need the browser (not "holds", but `REVIEW_BROWSER`): `gov.cy`, `riigiteataja.ee`, `eesti.ee`,
`gov.il`, `hukoomi.gov.qa`, `lmra.gov.bh`, `cfr.gov.mt`, `ibo.org`.

## 4. Provider register-availability priors (by category)
Every hub city so far: **banks** always have a register (the central-bank / prudential list —
SAMA, FSA, RBI, BNM, SARB, BCRA, CMF, MNB, BNR, CBB, CBO, CBK, PBOC…); **movers** always via
FIDI; **schools** always via IBO. The variable three:
- **legal_admin / tax_finance / housing_agencies** — strong statutory registers in
  **South Africa** (IRBA, PPRA), **Brazil** (OAB, CRECI, CFC), **Argentina** (CPACF, CPCECABA,
  CUCICBA), **Czechia** (ČAK, KAČR, ARES), **Portugal** (IMPIC, OROC), **Hungary** (MKVK).
  Typically **absent or JS/CAPTCHA-only** in **Chile, Malaysia, Thailand, China, the Gulf
  states, Korea, Mexico**. Brief: for the weak-register countries, *tell the subagent to SKIP
  legal/tax/housing rather than churn on a POST-only search form — skips are expected, never
  pad with firm sites.*

## 5. FIDI / IBO gotchas (cost a re-run each when missed)
- **FIDI movers:** the row's `source_url` MUST be the per-affiliate DETAIL page
  `fidi.org/find-fidi-affiliate/<slug>`, NOT the country-filter search URL
  (`?country=<id>`). `vendor_harvester.validate` rejects the search URL. If a subagent
  returns the search URL, derive the slug (lowercase, punctuation→'', ` - `/spaces→`-`) and
  curl-verify HTTP 200 + name-present before rewriting.
- **IBO schools:** `ibo.org` is Cloudflare-gated to curl; browser-ground or use the indexed
  finder titles. `accreditation_number` = the IB school code.
- **Banks are tier-2 capped** regardless of register strength.

## 6. Append-only invariants (never violated across the campaign)
Every promote: country/run-scoped; before/after count; **md5 fingerprint over all
`review_status='approved'` rows must be unchanged** (held at 153 facts / 130 provider caps
end-to-end); `expert_verified` count unchanged (0). Facts land `pending`/`corpus_grounded`;
the human gate at `/admin/countries` and `/admin/vetting-queue` is the only path to served.
