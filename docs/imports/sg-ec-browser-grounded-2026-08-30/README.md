# SG + EC cores — browser-grounded, 2026-08-30

The FR→SG and US→EC fact batches (#2116, #2118) landed the researchable core but left the
**JS-rendered government pages empty** — Otto's scraper reads only nav HTML on those hosts. This
batch fills the two most-critical of those gaps by opening the real pages in a browser, extracting
**verbatim** quotes, and re-confirming them through `verify_ledger` (**10/10 quotes confirmed on
live re-fetch, 0 rejected**). All three requirements landed **`corpus_grounded`** — a higher tier
than the original `representative` Otto facts.

## Landed (all `review_status='pending'`, `corpus_grounded`)
| corridor | requirement | facts | source |
|---|---|---|---|
| FR→SG | **Tax residence (IRAS)** — 183-day rule; a work pass valid ≥1yr = tax resident; 0–24% progressive | 3 | iras.gov.sg |
| US→EC | **Temporary residence visa — professional** — definition, apostilled-title requirement, passport, criminal record, USD $50+$270 fee, e-VISAS | 6 | gob.ec/mremh |
| US→EC | **Tourist status prohibits work** — the 90-day visitor permanence is tourism-only and forbids all labour activity | 1 | gob.ec/mremh |

The EC residence visa is the corridor's spine (it was 100% missing), and the tourist-trap
(*"están prohibidas de realizar actividades laborales"*) is the #1 non-obvious fact for Abraham —
both now grounded and quote-confirmed.

## Why this works when Otto couldn't
`iras.gov.sg` and `gob.ec` render their content with JavaScript; Otto's fetcher returns nav-only
HTML and reports the page "empty," so it rejects the facts. A real browser renders them, and
`verify_ledger`'s own fetcher (different from Otto's) reaches them too — which is why all 10 quotes
re-confirmed. This is the documented browser-grounding pattern (see Denis's NO→FR transition facts).

## Still open (next browser rounds)
- **SG:** FIN number, EP healthcare cover (EP holders aren't in public healthcare), housing/rental.
- **EC:** work authorization (`trabajo.gob.ec`), the SRI RUC / 183-day tax rule, and the IESS
  social-security topic (5 verified facts staged but UNMAPPED — Otto put two pillars on one topic;
  needs a pension/health split).
