# Supabase load — confirmation and remaining gaps

*Verified directly against `nsvefcvpvwwwhuqyuqmp`, 2026-08-13.*

## Confirmed in the database

| table | rows | note |
|---|--:|---|
| `requirement_facts` | **2,676** | 2,290 `pending`, rest already promoted |
| `requirement_entities` | **917** | across **37 destination countries** |
| `vendor_candidates` | **534** | 530 `pending` |
| `service_catalog_items` (live providers) | **985** | across 21 cities |
| `pet_import_rules` | 66 | 31 countries, origin-group variants merged |
| `staged_resource_candidates` | 33 | guides / reference content |
| `readiness_templates` | 18 | untouched this session (opt-in gate) |

**Quality check on what landed:**

- **0 facts without a `source_url`** — every single one traces to a source.
- 182 of 2,676 facts (6.8%) have no `evidence_quote`. Everything loaded this
  session carries one; the gap is in older rows.
- Nothing was promoted to live automatically — the candidates are all sitting in
  the review queue as designed.

So yes: everything that was reachable has been passed through. What follows is
what is provably *not* in there.

## Gap 1 — 151 vehicle-import entities with zero facts

Eighteen countries have a complete set of `vehicle_import` topics and **not one
fact** against any of them. In the product these render as empty sections.

> NO (9), PT (9), AT (9), CZ (9), PL (9), IN (8), IE (8), JP (8), IT (8), SE (8),
> BR (8), HK (8), AE (8), IL (8), DK (8), KR (8), ZA (8), BE (8)

Plus 21 scattered immigration orphans: CA (5), AE (4), ES (3), DE (3), JP (2),
AT (1), NL (1), and one each in ES `domestic_move` / FR `vehicle` / AT `other`.

## Gap 2 — 16 countries below a usable fact count

| tier | countries | facts each |
|---|---|--:|
| **critical** — under 12 | UA, RU, BR, KR, ZA, IL, HK, CZ, IN | 9–11 |
| **thin** — under 35 | QA, PL, IT, SA, TH, LU, FI | 19–33 |

For comparison, the corridors that work sit at 90–380 facts (NO 377, DE 205,
FR 169, US 163, CH 134, IE 130).

## Gap 3 — five provider cities with nothing, three barely started

| city | rows | categories |
|---|--:|--:|
| Frankfurt, Milan, Amsterdam, Dublin, London | **0** | 0 |
| Dubai | 5 | 1 of 13 |
| Munich | 8 | 2 of 13 |
| Oslo | 12 | 5 of 13 |

Every other live city sits at 32–66 rows across 7–10 categories. Research runs for
Dubai, Frankfurt, Munich, Milan, Oslo, Amsterdam, Dublin and London all reported
complete — the files were produced and never reached the database.

## Gap 4 — 133 facts with no statement

Wave 3a's records carry `source_quote`, `source_url`, `fact_key` and
`confidence_score` but no fact text in any field. They are correctly rejected: a
verbatim sentence from a government page is evidence *for* a fact, not the fact.
These need re-emitting with `fact_text` filled in.

## Gap 5 — three countries never written to GCS

Spain, the UK and Italy exist only as inline chat text. Re-emit requests are
running in all three meetings now (Otto is mid-task on Italy as of writing).

## Gap 6 — reference content is essentially empty

`staged_resource_candidates` holds 33 rows total, 22 of them German and from June.
City guides, neighbourhood briefs, cost-of-living and how-to content are the
thinnest stream in the whole workspace.

---

**Total addressable from here: roughly 45 small research units** — 18 vehicle-import
fact sets, 16 country top-ups, 8 provider cities, plus the wave 3a re-emit. The
prompt in `OTTO_TASK_LAUNCH_PROMPT.md` fans exactly these out, in a format the
loader ingests without further code changes.
