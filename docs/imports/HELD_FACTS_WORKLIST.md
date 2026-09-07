# Held-facts re-source worklist (punch-list)

Compiled 2026-09-08 from every batch's `held.ndjson` and README "could-not-verify" notes across the
rank-3→70 coverage campaign. These are facts with **real, wanted content that was blocked purely by a
fetch/verification barrier** — not landed, and re-sourceable. Deliberate scope exclusions
(nationality-neutral facts that also bind an EU citizen; figures folded into `non_obvious_note`) are
**not** on this list — those were correct calls, listed at the bottom for the record.

**How to clear an item:** re-source the quote from a reproducibly-fetchable official page → add it to
that batch's `facts.ndjson` (or a small `<iso>-resource-YYYY-MM-DD` batch) → `confirm_quotes.py`
(browser-verify if WAF/SPA) → `verify_ledger.py --no-fetch --apply` → `import_otto_facts.py
--batch-id` → `promote(country=<ISO>)` → `check_nationality_scope.py --db`. Everything lands **pending**;
re-scope EU-registration-certificate rows to `["EU_EEA"]` before the scope guard (EEA corridors).

---

## ✅ Cleared 2026-09-08

Holds re-sourced and landed **pending** (append-only; approved count unchanged at 325,
expert_verified 0, scope guard green). Each has a `<iso>-resource-2026-09-08/` batch doc (Denmark:
see the be-at-dk batch's § Update 2026-09-08).

| Country | Fact(s) | Verification |
|---|---|---|
| **Colombia** | Cédula de Extranjería registration deadline | CONFIRMED (0.93) — Decreto 1067/2015 on `cancilleria.gov.co` |
| **Panama** | 5-year Panamanian-substitution duty (art. 18) | applier-verified via `pdfplumber` (cetippat server flaky) |
| **Hong Kong** | HKID within 30 days of arrival | browser-verified — Cap. 177A reg. 3(1)(a), exact |
| **Austria** | EU-registration late fine (€50–250) | CONFIRMED (1.0) — `wko.at` (added to `_SEMI_OFFICIAL_HOSTS`) |
| **Japan** | Dependent visa 28-hrs/week cap | CONFIRMED (1.0) — ISA `moj.go.jp/isa` |
| **Denmark** | 8 facts — CPR, health card, tax liability, EU residence doc, work permit | browser-verified verbatim (borger.dk/skat.dk/nyidanmark.dk/kk.dk render cleanly) — DENMARK 11→19 |

**Still held — Indonesia (BPJS Kesehatan).** Claim is true, but the researcher's supplied quote
is **inaccurate** (Perpres 82/2018 Pasal 1 reads *"…dan telah membayar iuran"*, not *"yang telah
membayar Iuran Jaminan Kesehatan"*), and no reproducibly-fetchable official page renders the clean
verbatim right now (BPK = garbled OCR; `peraturan.go.id` down). See `id-resource-2026-09-08/README.md`.

---

## Tier 1 — structured holds (already in `held.ndjson`, one fact each)

| Country | Fact | Pillar | Blocker | Re-source action |
|---|---|---|---|---|
| ✅ **Colombia** | Cédula de Extranjería registration deadline | IDENTITY | ~~`migracioncolombia.gov.co` cédula page empty/redirect~~ | **CLEARED** via Decreto 1067/2015 on `cancilleria.gov.co` |
| ⏳ **Indonesia** | BPJS Kesehatan — foreigner ≥6 months must enrol | HEALTHCARE | Perpres 82/2018 on BPK is a garbled ClearScan-OCR scan; `peraturan.go.id` down. **Researcher's quote also inaccurate** (real: *"…dan telah membayar iuran"*) | STILL HELD — re-source clean verbatim; claim is sound |
| ✅ **Panama** | 5-year Panamanian-substitution duty (Labour Code art. 18) | EMPLOYMENT | ~~quote not verbatim in the PDF~~ | **CLEARED** — applier-verified fragment via `pdfplumber` |

## Tier 2 — cluster / single holds blocked by a portal barrier

Grouped by blocker, because the blocker dictates the fix.

### Bot-walled / CAPTCHA / geo-gated (need a WAF-passing browser or a reachable mirror)
- ✅ **Denmark — 8 facts. CLEARED 2026-09-08.** `borger.dk`/`skat.dk`/`nyidanmark.dk`/`kk.dk` all
  render cleanly in the in-app browser (no CAPTCHA — the referee's *HTTP fetch* was the only thing
  bot-walled). All 8 quotes browser-verified verbatim; landed pending (DENMARK 11→19). Shared-topic
  cpr/tax/health pairs split to `<topic>_3c` to clear the nationality-conflict; EU-residence-document
  row re-scoped `["EU_EEA"]`. See `be-at-dk-facts-2026-08-31/README.md` § Update 2026-09-08.
- **Malta — ~4 facts.** `cfr.gov.mt` (HQP 15% flat-tax, tax residency, non-dom/remittance) +
  `socialsecurity.gov.mt` (social-security registration) — Cloudflare hard-block to every fetcher incl.
  browser here. → re-source from a reproducibly-fetchable official page.
- **Kuwait — ~2 facts** (Civil ID standalone; end-of-service indemnity / Labour Law No. 6/2010).
  `e.gov.kw` / `paci.gov.kw` / `manpower.gov.kw` are **geo-gated to Kuwaiti IPs** (403 / timeout). →
  hardest of the set: needs a Kuwait-egress fetch or an official mirror.
- **Saudi Arabia — 2 facts** (SCE engineer accreditation; CCHI health-insurance ↔ iqama link).
  `saudieng.sa` / `cchi.gov.sa` unreachable. → re-source when reachable, or from `laws.boe.gov.sa`.
- **Malaysia — ~2 facts** (EPF/SOCSO social security; MDEC tech-specific). `hasil.gov.my` portal
  upgrade broke the paths (404); `esd.imi.gov.my` 403. → current LHDN / IMI pages.
- **Brazil — 1 fact** (VITEM V "prior residence authorization" ordering). `gov.br/mre` consular pages
  CAPTCHA-gated (currently folded into a note). → re-source the MRE page.
- **Israel — 1 fact** (foreign-expert flat-tax rule). ITA Income-Tax-Ordinance PDF unreachable; the
  expert-procedure page 404s. → re-source.
- **India — 1 fact** (PAN mandatory, Income-Tax Act §139A). `incometaxindia.gov.in` 403 to direct
  fetch. → re-source.

### JS-SPA (curl gets a shell — capture the rendered text / network payload, SINALEVI-style)
- **Estonia — several facts** (labour-market-test wording; residence-permit-card-as-domestic-ID;
  family-doctor choice; driving-licence 12-month rule). `eesti.ee` / `work.eesti.ee` are Cloudflare JS
  SPAs — readable in a browser, not referee-reproducible by curl. → browser-ground via network capture.
- **Portugal — 1–2 facts** (art. 61-A HQ-work-visa salary threshold — MFA page OCR-garbled; EU Blue
  Card 30-day intra-EU mobility deadline — not in static text). → re-source a clean page.
- ✅ **Austria — 1 fact** (EU-registration late fine, €50–250). ~~Not on the read `oesterreich.gv.at` page.~~ **CLEARED** — CONFIRMED (1.0) on `wko.at` (added to `_SEMI_OFFICIAL_HOSTS`).

### Quote-not-on-page / not verbatim (find the exact page)
- ✅ **Hong Kong — 1 fact** (HKID "within 30 days of arrival"). **CLEARED** — browser-verified
  verbatim at Cap. 177A reg. 3(1)(a) on `elegislation.gov.hk`.
- ✅ **Japan — 1 fact** (Dependent visa 28-hrs/week cap). **CLEARED** — CONFIRMED (1.0) on the ISA
  page `moj.go.jp/isa`.

## Tier 3 — earlier corridors (pre-wave-9, larger reject piles)
- **FR→SG — 13 facts** in the batch's `rejects.ndjson` (quote-not-on-page). → re-source or drop.
- **NO→FR — ~13** (12 quotes unconfirmed on their source + 1 proven false). → re-source the 12; the
  false one should be dropped, not re-sourced.

---

## Separate track — reconciliation holds (NOT re-source; dedup + decide)
These batches were withheld because the destination was **already covered**, so they'd risk duplicate
rows — a dedup/merge decision, not a sourcing task (titles are the dedup key).
- **Spain** — `es-facts-2026-08-31` held for reconciliation against the 25 existing pending SPAIN rows.
- **Netherlands** — `nl-facts-2026-08-31` held against the 10 approved (serving) NETHERLANDS rows.

## Not on this list (correct calls, no action)
Facts the researchers **deliberately did not write** because they were sound exclusions, not holds:
nationality-neutral rules that also bind an EU citizen (Luxembourg impatriate regime, Finland 183-day,
Hungary TB/TAJ, South Africa UIF/SARS, Chile AFP/isapre gaps, …); and figures not worth asserting
without an on-page quote (folded into `non_obvious_note`). Re-sourcing these would add duplicate or
out-of-scope rows — leave them.

---

### Roll-up
~**11 countries** with genuine re-sourceable holds (Tier 1–2) ≈ **25–30 facts**, plus the FR→SG /
NO→FR reject piles (~26). Highest-value quick wins: the 3 Tier-1 structured holds and Austria/Japan/
Hong Kong (single clean facts). Hardest: Kuwait (geo-gated) and Malta (hard Cloudflare). Denmark (8) is
the biggest single-country recovery.
