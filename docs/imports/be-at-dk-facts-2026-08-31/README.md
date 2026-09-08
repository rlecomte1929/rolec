# Belgium + Austria + Denmark destination facts (2026-08-31)

EEA destinations. **Landed: Belgium 6 + Austria 2 requirement_items (pending).** Denmark was HELD
(8 facts) — borger.dk bot-walled the referee + reconcile-against-existing concern; **CLEARED
2026-09-08** (see `## Update` below). 28 dual-audience facts; verify_ledger confirmed 21/24 quotes
(ibz.be fetch-failed transiently — reported, not rejected).

## Update 2026-09-08 — Denmark cleared (8 facts, DENMARK 11→19 pending)
All 8 held DK facts browser-verified verbatim (the in-app browser renders borger.dk/skat.dk/
nyidanmark.dk/kk.dk cleanly — no CAPTCHA, unlike the referee's HTTP fetch): EU residence document
before CPR, residence & work permit (3C), CPR registration (EEA+3C), health insurance card
(EEA+3C), full tax liability (EEA+3C). The 3 shared-topic pairs (cpr/tax/health) hit the
nationality-conflict UNMAPPED, so the non-EEA fact of each was split to a `<topic>_3c` staging
topic before promote — 8 rows, 0 unmapped. Reconcile check: distinct titles vs the 11 existing B3
rows → append, no overwrite. EU-residence-document row re-scoped `["EU_EEA"]` (permission content;
a Danish national doesn't need one). Append-only: approved 325 unchanged, expert_verified 0, scope
guard green. nyidanmark.dk Pay-Limit figure confirmed current (DKK 552,000).

Sources: BE = ibz.be (Immigration Office), brussels.be (City), onestopcounter.workinginbelgium.be,
inami.fgov.be. AT = oesterreich.gv.at, migration.gv.at, wien.gv.at. DK = lifeindenmark.borger.dk, skat.dk,
nyidanmark.dk, international.kk.dk.

## Code
- `requirements_country_key.py`: `"BE":"BELGIUM"`, `"AT":"AUSTRIA"` (+test). DK already mapped.
- `parsers.py`: allowlisted `fgov.be` + `gv.at` suffixes and `ibz.be`/`brussels.be`/
  `onestopcounter.workinginbelgium.be` hosts.
- EEA permit-gating: 2 Belgium registration rows re-scoped `["OWN_NATIONAL","EU_EEA"]`→`["EU_EEA"]`. Scope guard exit 0.

## Rejects / honest gaps (documented, not fabricated)
- BE tax residency, social-security affiliation, national-register number — fin.belgium.be / dofi.ibz.be /
  belgium.be are CAPTCHA/bot-walled; no accessible official verbatim (re-source worklist).
- AT EU-registration late fine (€250) — not on the read oesterreich.gv.at page; withheld.
- DK Pay-Limit definitional sentence — in a JS accordion; used the visible salary line instead.
- 4 verify-rejected + a few unmapped pillar-conflict topics stay in worklist/staging.

Gate remaining (human): approve at /admin/countries; serving needs BE/AT catalog + allowlist merged.
