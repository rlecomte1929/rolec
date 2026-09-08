# Bengaluru (India) providers — 2026-08-31

Tier-3 wave-6 hub-city provider sourcing for INDIA (corridor `XX-IN`). Register-evidenced;
`source_url` is always the register, never a firm marketing site.

Note: the sourcing subagent terminated on an infra error (computer-sleep) after writing
`providers.csv` but before finishing this README. The CSV is complete and validated (13 rows,
9 columns). Only three categories were reached before the failure.

## Rows per category / register
- **movers — 3** · FIDI Global Alliance FAIM affiliate directory (per-affiliate detail pages).
- **banks — 6** · Reserve Bank of India list of scheduled commercial banks (rbi.org.in).
- **schools — 4** · IBO "Find an IB World School" (ibo.org/en/school/<id>), IB code captured.

## Skipped / not reached (re-source worklist)
- **housing_agencies** — Karnataka RERA (rera.karnataka.gov.in) maintains a mandatory registered-agents
  list with RERA numbers; not reached before the subagent failed. Re-source: K-RERA "registered agents".
- **legal_admin** — Bar Council registers individual advocates, not firms; no clean per-firm register.
- **tax_finance** — ICAI firm register ("Know Your Member/Firm") not reached; re-source.

All rows land `platform_vetting_status='pending'` behind the human vetting gate. Nothing served.
