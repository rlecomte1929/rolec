# Knowledge-layer contract — pending-only inserts + citation sufficiency

Status: descriptive (documents shipped behavior). Introduced by commit `82c02e0f`
("Ship the knowledge-layer contract: pending-only inserts, citation parity, and catalog
sufficiency", 2026-09-09) and the hotfix `#2245` that repaired its rollout.

This is the "why not just use ChatGPT" trust story made mechanical: **we only serve
requirements a human has approved, and we tell the reader when a corridor is too thinly
cited to trust yet.** Two rules enforce it.

## 1. Pending-only inserts

`backend/app/services/crud.py::create_requirement_item` — the single funnel every
automated producer flows through (Otto promote, YAML seed, research stub) — does:

```python
insert_payload.setdefault("review_status", "pending")
```

So a row inserted by an automated producer that does not name a `review_status` lands as
**`pending`** and is **not served** until a human approves it. Notes:

- The column's server default is still `'approved'` (`backend/app/models.py`), which covers
  pre-existing rows and rows written by other paths; the funnel above overrides it for
  automated inserts.
- The UPDATE branch of the same upsert **preserves** a reviewer's `review_status` and any
  non-empty `citations_json` — re-running a seed/import must never re-approve a demoted row
  or blank a curated citation (`#1822`, `#1924`; regression covered by
  `backend/tests/test_requirement_review_gate.py`).
- `requirements_builder` / the public corridor endpoint serve only `review_status='approved'`.

## 2. Citation-sufficiency gate ("not ready")

`backend/app/services/knowledge_layer_scorecard.py::score_catalog` scores each
`(destination, purpose)` catalog. A corridor is **ready** only when all three hold:

| threshold | value | meaning |
|---|---|---|
| `MIN_APPROVED` | 1 | at least one approved row |
| `CITATION_RESOLVE_BAR` | 0.5 | ≥ 50% of **approved** rows carry a **resolvable citation** |
| `MIN_PILLARS` | 2 | approved rows cover more than one requirement pillar |

- **"Resolvable citation"** = one that `requirements_builder.citation_dtos(...)` turns into a
  served DTO. A bare official URL counts; so does a `source_records` UUID or an
  `immigration_rule.*` corpus ref. (Three citation formats coexist in `citations_json` and
  all resolve.)
- When a corridor is **not ready**, the public endpoint
  (`backend/app/routers/public_corridor.py`) returns HTTP **200** with
  `catalog_ready: false` and a `coverage_note` — and **still serves the approved rows**. The
  three messages (`NOT_READY_EMPTY`, `NOT_READY_CITATIONS`, `NOT_READY_PILLARS`) name which
  bar failed. An **empty** `requirements` list means a genuine catalog gap (no approved rows
  for that destination), not a finding that nothing is required.

### Consequence: uncited served rows now cost twice

A row that is `approved` but uncited fails two things at once:

1. the **provenance guard** (`scripts/check_requirement_provenance.py`, baseline
   `scripts/requirement_provenance_baseline.txt`) — a served row must be cited, because
   `disclaimers.py` defines the platform's `'representative'` status as *curated AND cited*;
2. the **sufficiency gate** — enough uncited approved rows drop a whole corridor below
   `CITATION_RESOLVE_BAR`, so real users see a "not ready" caveat.

Working the provenance baseline toward zero (cite the citable, demote the inputs — see
`supabase/migrations/20261112000000_cite_served_requirement_items.sql` and
`…20261134000000_cite_or_demote_de_us_employment.sql` for the taxonomy) therefore both
satisfies the guard and lifts corridors back to `catalog_ready`.

## Related
- `scripts/check_requirement_provenance.py` — the served-but-uncited guard.
- `backend/app/services/disclaimers.py` — the `'representative'` definition.
- `docs/specs/serving-llm-isolation.md` — the serving path may never reach an LLM at request time.
