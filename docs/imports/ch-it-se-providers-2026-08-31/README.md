# Zurich + Milan + Stockholm providers — Otto batch (2026-08-31)

Otto-sourced (Audos) as 3 per-city tasks, each delivering a CSV + blocked.json + manifest to GCS
(curl-verified). 19 register-evidenced rows landed (0 rejects); the national legal/tax/housing
registers for IT/SE (and CH legal/tax/housing) are JS-only, so those categories are blocked — a
re-source worklist, not fabricated.

| corridor | city | landed | categories |
|---|---|---|---|
| XX-CH | Zurich | 10 | movers 4 (FIDI) · banks 3 (FINMA) · schools 3 (SGIS) |
| XX-IT | Milan | 3 | movers 3 (FIDI) — everything else blocked (JS-only registers) |
| XX-SE | Stockholm | 6 | movers 2 (FIDI) · schools 4 (IBO) |

Code: XX-CH/XX-IT/XX-SE corridors + FINMA (CH banks) + SGIS (CH schools) registers + domain mappings;
IBO corridors extended; pairs test 72->90. Load: 19/19 validate -> scoped stage+promote; suppliers
312->331, +19 pending, approved unchanged (130).

Re-source worklist (JS-only registers Otto couldn't extract): Milan legal (Ordine Avvocati), tax (ODCEC),
banks (Banca d'Italia albo), schools (ANINSEI), housing (FIAIP); Stockholm legal (Advokatsamfundet),
tax (FAR), banks (Finansinspektionen), housing (Fastighetsmaklarinspektionen); Zurich legal (SAV/FSA),
tax (EXPERTsuisse), housing (SVIT).

Gate remaining (human): vet at /admin/vetting-queue.
