# Indonesia requirement facts — 2026-08-31 (wave 9, rank 55)

12 facts researched for a **third-country national** relocating to **Indonesia** for employment;
**11 landed** (topic-grained → **7 requirement_items**) to `INDONESIA`, 1 held. All
`review_status='pending'` — nothing served. Append-only: global approved held at 153,
`expert_verified=0`.

## Sourcing (all official `*.go.id`)
- `jdih.kemnaker.go.id` — Permenaker 8/2021: employer must hold a Minister-approved **RPTKA**;
  **DKPTKA levy US$100/position/month**; mandatory Indonesian **companion worker**; employer funds
  the expat's Bahasa training; RPTKA locks the KITAS to one position + time window
- `imigrasi.go.id` — RPTKA-first sequencing; C312 visa is the last step (via TKA Online → SIMKIM)
- `pajak.go.id` — 183-days-in-12-months tax residency; worldwide-income principle
- `bpjsketenagakerjaan.go.id` — UU 24/2011: foreigner working ≥6 months → BPJS Ketenagakerjaan
- `kecandran.salatiga.go.id` — SKTT / Dukcapil report within 14 days

## Verification
5 CONFIRMED by the confirm_quotes referee; the 6 PDF-sourced facts were first mis-held by a
`confirm_quotes` PDF-detection bug (fixed this wave), then **applier-verified by direct pdfplumber
substring** against the real official PDFs (the kemnaker server is flaky — the 826 KB Permenaker PDF
returns only on retry). Nationality categorised `non-EEA → THIRD_COUNTRY`.

## Held (`held.ndjson`, re-source worklist)
- **`bpjs_kesehatan`** (HEALTHCARE) — cited to Perpres 82/2018 on `jdih.kemenkeu.go.id`, which is
  unreachable from the harvest environment and is a ClearScan-OCR scan with mojibake. Not
  independently confirmable, so held rather than landed on the researcher's say-so. (The parallel
  BPJS Ketenagakerjaan / social-security fact **was** confirmed and landed.)
