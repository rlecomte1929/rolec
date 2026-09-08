# Berlin city enrichment — 2026-09-02 (ChatGPT card AIQ-2219, delivered by Claude Code)

The ChatGPT lane did not deliver this batch, so it was produced via a research subagent and landed
by the applier. **16 `country_resources` rows + 8 sources, all `status='draft'`** — nothing
published. Append-only verified: the 73 published resources are untouched (non-draft fingerprint
unchanged); drafts 13 → 29.

## Contents
- `facts.ndjson` — the §3B 8-key city-enrichment stream (city, country, topic, title, body,
  source_url, source_name, retrieved_at). 16 rows.
- `bundle.json` — the same content converted to the `import_resources.py --bundle` shape
  (topic → `resource_categories.key`: neighborhoods→housing, banking→admin_essentials,
  practicalities→daily_life, schools→schools_childcare, etc.).

## Coverage (by topic)
housing/neighborhoods 4 · daily_life/practicalities 3 · admin_essentials/banking 2 · transport 2 ·
schools_childcare 2 · healthcare 2 · cost_of_living 1.

## Sourcing
Berlin city + statutory sources dominate: `berlin.de` (6), `willkommenszentrum.berlin.de` (3),
`n26.com`, `gesund.bund.de`, `rundfunkbeitrag.de`, `bvg.de`; `allaboutberlin.com` / `iamexpat.de`
used only for two soft practicalities, grounded against each page's wording. Cited figures are from
the pages (Deutschland-Ticket €63/mo, Rundfunkbeitrag €18.36/mo, €60 penalty fare, Anmeldung 14
days). No rent figures, price ranges, or "family-friendly" flags were invented — left absent.

## Gate
Human review at the resources admin surface before any draft is published. Draft is the resources
equivalent of `pending`.
