# Spain destination facts (2026-08-31) — HELD FOR RECONCILIATION (not promoted)

16 statutory-sourced Spain facts (8 EEA free-mover + 8 non-EEA), boe.es consolidated law + seg-social
+ agenciatributaria. `verify_ledger`: **14/16 quotes confirmed verbatim**, 2 dropped to worklist.

## ⚠️ NOT promoted — Spain is already covered
Prod already holds **25 SPAIN `requirement_items` (pending)** from the earlier IE→ES batch, covering the
same topics (registration/certificado, NIE, TIE, empadronamiento, social security/NUSS, tax residency
183-day, healthcare, housing, driving, Beckham regime). Promoting this batch would create ~12
near-duplicate pending rows. Held for a **dedup/reconciliation** pass (titles are the dedup key).

## Genuinely net-new here (worth adding after reconciliation)
- `ES-EEA:entry_no_visa` — EU/EEA entry needs no visa (not in the 25)
- `ES-EEA:no_work_permit` — EU/EEA need no work permit (free movement carve-out, LOEX Art. 1.3)
- `ES-3C:hqp_authorization` — Highly Qualified Professional fast-track (Ley 14/2013, Unidad de Grandes Empresas)
- `ES-3C:work_residence_authorization` — the core prior work+residence authorisation requirement

The rest (NIE, empadronamiento, social security, tax residency, healthcare, TIE) duplicate the 25 and
should be reconciled, not re-added. This batch is a **quality alternative** (statutory-sourced, dual-audience).
