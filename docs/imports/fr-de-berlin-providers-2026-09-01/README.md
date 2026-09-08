# FR→DE Berlin providers — ChatGPT batch 2026-09-01 (Notion AIQ-2220)

ChatGPT research batch (`fr-de-berlin-providers-2026-09-01`) for the **FR-DE** corridor, Berlin.
This folder holds ChatGPT's raw delivery **plus the applier's complement**, because the batch as
delivered accepted **0 of 8** candidates.

## What ChatGPT delivered
- `providers.csv` — header only (**0 accepted**).
- `rejects.csv` — **8 candidates, all rejected** by a self-imposed gate ("strict schema requires
  both a membership/accreditation number AND expiry"). `manifest.json` records the per-category
  reasoning.

That gate is stricter than ReloPass's actual importer. FIDI movers land with a blank
`accreditation_number` (the per-affiliate detail page is the evidence); banks are tier-2 on the
central-bank/BaFin register. So most of the 8 "rejects" are in fact valid candidates.

## Applier complement (`providers.recovered.csv`) → landed to pending
Remapped ChatGPT's `banking` → our `banks`; set aside the 2 `legal_admin` rows (below); ran the 6
movers+banks through `import_supplier_candidates` (via the scoped stage→promote path). Result:

| outcome | rows | detail |
|---|---|---|
| **landed (pending)** | **2** | AGS Global Solutions GmbH (mover, FIDI) · N26 Bank SE (bank, BaFin) |
| already in corridor | 2 | Hertling, Hasenkamp — FIDI movers already harvested for FR-DE (dedup skipped) |
| rejected — evidence gap | 2 | Berliner Sparkasse, DKB — their `kontenvergleich.bafin.de/de/konto/` URL is an account-comparison page, not a per-entity institute record |
| held — weak source | 2 | BLKR, Uznanski (legal_admin) — cited to RAK Berlin **job-ad PDFs** (`ausschreibung`), not a member-registry listing |

Append-only: approved capabilities held at 130; suppliers +2, pending capabilities +2.

## Re-source worklist (before any of these can join)
- **Berliner Sparkasse, DKB** → re-source to the per-entity BaFin institute record
  (`portal.mvp.bafin.de/database/InstInfo/…`), not the `kontenvergleich` comparison page.
- **BLKR, Uznanski** → re-source to an actual RAK Berlin member-registry entry, not a recruitment PDF.

## Note on the sibling batches
The two companion ChatGPT cards were **not delivered** to the import lane as of 2026-09-02:
`fr-de-eea-requirements-2026-09-01` (AIQ-2218, corridor requirement facts) and
`berlin-city-enrichment-2026-09-01` (AIQ-2219, city enrichment). No folder for either exists in
Downloads or the repo; both Notion cards are still `Otto ready / Not started`. Those two carry the
bulk of the corridor's value and still need to be produced/handed off.
