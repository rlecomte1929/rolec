# FR→DE corridor requirement facts — 2026-09-02 (ChatGPT card AIQ-2218, delivered by Claude Code)

The ChatGPT lane did not deliver AIQ-2218, so it was produced via a research subagent and landed by
the applier. **17 facts → 17 requirement_items** promoted to `GERMANY`, all `review_status='pending'`
— nothing served. This is the **EU/EEA corridor** (a French/EU professional relocating Paris→Berlin):
the headline is free movement (no visa, no work permit), so the value is the registration/tax/
health/social-security mechanics and the chicken-and-egg traps.

## Coverage (pillars, 6 of 7)
SOCIAL_SECURITY 5 · RESIDENCE 3 · HEALTHCARE 3 · HOUSING 2 · IDENTITY 2 · EMPLOYMENT 2.
Non-obvious traps captured: Anmeldung within 14 days despite free movement; a lease ≠ the
Wohnungsgeberbestätigung; no EU residence permit exists in DE (the Meldebestätigung is the key
document); Steuer-ID arrives only by post after Anmeldung; **no Steuer-ID → tax class VI** (max
withholding, §39c EStG); local hire = German social security, only a true posting keeps the French
régime (A1, ≤24 months); French pension years aggregate to Germany's 5-year minimum; GKV vs PKV you
can't freely choose; free Familienversicherung for a non-working spouse; a non-EU spouse gets
*derived* free-movement rights (flagged `needs_lawyer_review`).

## Verification
`nationality="EEA"` → EU free-mover categories; the nationality scope guard passed (these are
exemptions/registrations, not permission requirements reaching own-nationals). confirm_quotes
referee: 13/17 CONFIRMED headless; 4 browser-verified — `no_work_permit` (europa.eu, markup-split)
and the 3 health facts (`make-it-in-germany.com` health page; curl was WAF-blocked to a decoy page,
the browser confirmed all three verbatim). All 17 landed. Sources official/statutory only
(service.berlin.de, europa.eu, bzst.de, gesetze-im-internet.de, make-it-in-germany.com, cleiss.fr,
arbeitsagentur.de). Three German statutory hosts were added to the importer allowlist in this wave
(make-it-in-germany.de, deutsche-rentenversicherung.de, gkv-spitzenverband.de).

## Append-only
GERMANY 11 → 28 requirement_items (7 approved untouched, now 21 pending). Global approved
fingerprint unchanged by this promote; expert_verified = 0.
