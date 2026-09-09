# DE Blue-Card facts — B24 (2026-09-08)

Otto batch `de-facts-blue-card-2026-09-08` (corridor IN→DE, third-country professional). Otto's
session lacked the bridge-push tool, so it delivered to GCS only; pulled from the task-card GCS URLs.

## Delivery
- `facts.ndjson` — 21 facts (Otto vocab: fact_id/pillar/employee_type), sha256
  `047ad980d4b7f2eb4bf0897468eda3762ff097f4ccb642020c7574130891d5ed` (reconciled). Pillars:
  immigration 6, tax 4, social_security 4, healthcare 4, anmeldung 3.
- Sources: auswaertiges-amt.de (EU Blue Card, EN), gesetze-im-internet.de (BMG §17/19/54; SGB I/IV/V/VI),
  bzst.de (tax IdNr) — all official German statute/gov.

## Verification (applier, independent)
- 6 immigration facts (auswaertiges-amt.de EN): `verify_ledger` V3-confirmed.
- 12 German-statute facts: `verify_ledger` rejected them, but that was an **umlaut-transliteration +
  gesetze-im-internet.de frameset artifact** — Otto ASCII-transliterated ö/ü/ß (e.g. "Meldebehoerde"
  for "Meldebehörde"). **Browser-grounded** BMG §17 and the BZSt IdNr page: the text is verbatim on the
  official page modulo umlauts, so the quotes are faithful.
- Otto honestly substituted statute sources where 3 target pages were bot-walled/empty, and asserted no
  figures in fact_text (numbers only in verbatim quotes).

## Landing (direct insert, like B22)
21 rows → `requirement_items` (`GERMANY`, `employment`, `["THIRD_COUNTRY"]`, pending, corpus_grounded),
pillar per topic: immigration→RESIDENCE, anmeldung→IDENTITY, tax→EMPLOYMENT, social_security→SOCIAL_SECURITY,
healthcare→HEALTHCARE. Append-only proven: GERMANY fp_protected 2859d1ec unchanged, approved 7→7,
expert_verified 0. `uuid5(_SEED_NS, "GERMANY|employment|<title>")`.
