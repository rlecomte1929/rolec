# FR→SG providers — Adrien (Paris → Singapore), 2026-08-30

First provider batch for the FR→SG corridor. Otto sourced 20 firms across all 6 live categories from
the Singapore registers; all landed at `platform_vetting_status='pending'` in `/admin/vetting-queue`.

## Landed (20, pending vet)
| category | n | register | evidence |
|---|---|---|---|
| banks | 4 | **MAS Financial Institutions Directory** | per-entity `/fid/institution/detail/<id>` pages (strong) |
| movers | 5 | **FIDI FAIM directory** | per-entity affiliate pages, FAIM expiry captured (strong) |
| housing_agencies | 4 | CEA Public Register (ACEAS) | `PUBLIC_REGISTER` claimed — rows carry real CEA licence nos (e.g. L3008022J) |
| legal_admin | 3 | Law Society of Singapore | `PUBLIC_REGISTER` claimed — search page, vetter confirms by name |
| schools | 2 | MOE International Schools List | `PUBLIC_REGISTER` claimed — IFS + UWCSEA |
| tax_finance | 2 | ACRA Company Register | `PUBLIC_REGISTER` claimed — **Otto flagged Low confidence** (KPMG/EY via BizFile snippets) |

Staged 12 + 8 duplicates (the FIDI movers overlap prior corridors); 0 rejected. Landed via a
**scoped** promote (`promote(run_ids=[…])`), never the unscoped CLI `--promote` (≈474-row backlog).

## Code dependency
- `registry_sources.py` — added `FR-SG`/`US-EC` to `CORRIDORS` + 5 SG registers: **MAS** as a normal
  `HTTP_LISTING` (its detail pages are per-entity, tier 1), and **CEA / Law Society / ACRA / MOE** as
  `PUBLIC_REGISTER` (tier 2, `claimed`) because they are JS-rendered SPAs answering only a search form.
- `parsers.py` — 5 SG domains in `_DOMAIN_TO_SOURCE`.

## Browser-grounding worklist (from `blocked.json`)
The JS-blocked per-entity registers to upgrade the `claimed` rows later: CEA ACEAS (per-agency URLs),
Law Society mandatory register, ACRA BizFile+ (per-firm records), MOE/CPE (per-school). banks + movers
already carry per-entity evidence and need no upgrade.
