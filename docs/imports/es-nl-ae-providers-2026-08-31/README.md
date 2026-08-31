# Madrid + Amsterdam + Dubai providers — Otto batch (2026-08-31)

Otto-sourced (Audos), delivered as 3 city CSVs + manifest on GCS (curl-verified, HTTP 200), pulled here.
53 rows delivered; combined into `providers.csv` (1 stray UK-school row dropped). Validated through
`vendor_harvester.validate` → **35 pass, 17 reject** (all rejects are tier-3 provider-own-websites — not
register-evidenced — so refused by design). The 35 were staged run-scoped and promoted to the vetting
queue (`platform_vetting_status='pending'`); append-only verified (suppliers 277→312, +35 capabilities,
approved unchanged 130→130).

## Landed (35, pending)
| corridor | city | landed | categories |
|---|---|---|---|
| XX-NL | Amsterdam | 17 | movers 2 · legal 3 · tax 4 · banks 3 · schools 2 · housing 3 (all 6) |
| XX-AE | Dubai | 11 | movers 3 · banks 5 · schools 3 |
| XX-ES | Madrid | 7 | movers 5 · schools 2 |

Registers wired (all real regulators/bodies): FIDI (movers), DNB (NL banks), NOvA/Dutch-bar (NL legal),
AFM (NL tax), MVA (NL housing), CBUAE (AE banks), KHDA (AE schools), IBO (international schools, ES/NL/AE).

## Rejected → Otto re-source worklist (17, NOT landed — honest gaps)
- **Madrid banks (5)** — cited the banks' own sites, not a register. Re-source from Banco de España register.
- **Madrid legal (2) + tax (2)** — law-firm / accountancy-firm own sites (ICAM & REAF were login/403-gated). Re-source per-entity.
- **Dubai legal (1)** — law-firm site (DLAD register not publicly queryable). Re-source.
- **Dubai tax (4)** — accountancy-firm own sites. Re-source from a UAE register.
- **Dubai housing (3)** — aggregator site (shozon.com), not RERA. Re-source from Dubai Land Dept / RERA.

Otto's manifest `blocked` block documents the register access issues (COAPI login, REAF 403, DUO JS-only,
DLAD unqueryable). Movers are the strongest (FIDI per-entity across all 3).

## Note on ES/NL facts
ES and NL FACTS are already covered in prod (SPAIN 25 pending, NETHERLANDS 10 approved) and were HELD for
reconciliation — these are the net-new PROVIDER sets for those destinations. Gate remaining: vet at
/admin/vetting-queue.
