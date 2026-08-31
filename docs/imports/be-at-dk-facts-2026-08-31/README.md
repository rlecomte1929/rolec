# Belgium + Austria + Denmark destination facts (2026-08-31)

EEA destinations. **Landed: Belgium 6 + Austria 2 requirement_items (pending).** Denmark HELD (8 facts):
DK already has 11 prod requirement_items (B3 batch) — reconcile before adding. 28 dual-audience facts;
verify_ledger confirmed 21/24 quotes (ibz.be fetch-failed transiently — reported, not rejected).

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
