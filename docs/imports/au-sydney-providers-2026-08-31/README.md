# Sydney providers — Australia destination (2026-08-31)

24 Sydney providers across all 6 categories, from the authoritative Australian register per category.
Validated 24/24, staged run-scoped, promoted to the vetting queue (all `platform_vetting_status='pending'`).

| category | n | register | tier |
|---|---|---|---|
| movers | 5 | FIDI FAIM (per-entity + FAIM expiry) | 1 |
| legal_admin | 3 | OMARA Register of Migration Agents | 2 |
| tax_finance | 3 | Tax Practitioners Board (TPB) — statutory, w/ reg. number | 2 |
| banks | 5 | APRA authorised-ADI list | 2 |
| schools | 4 | NESA Approved NSW school providers (CRICOS code) | 2 |
| housing_agencies | 4 | NSW Fair Trading property-agent register (licence no.) | 2 |

Code added: `XX-AU` corridor + 5 AU registers (OMARA/TPB/APRA/NESA/NSW-FairTrading, PUBLIC_REGISTER tier 2;
movers reuse FIDI) in registry_sources.py + domain mappings in suppliers/parsers.py; pairs test 48->54.

Load: read_csv+validate 24/24 -> stage(6 runs, 0 rej) -> promote(run_ids) = 24; suppliers 253->277,
+24 capabilities all pending, approved unchanged (130->130).

Honest substitutions: CPA Australia / CA-ANZ (Cloudflare-blocked) and REINSW (JS geocode) were replaced
with the statutory TPB and NSW Fair Trading registers rather than guessed. Housing website_url left blank
(register carries the licence, not the site) — dedup falls back to name; vetter confirms.

Gate remaining (human): vet at /admin/vetting-queue.
