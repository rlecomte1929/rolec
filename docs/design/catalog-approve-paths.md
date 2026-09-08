# Catalog Approve → served row

Founder map of what **Approve** actually writes. Do not merge these backends.

## Canonical served catalog (employees + HR)

| Surface | Table | Approve does | Product reads |
| --- | --- | --- | --- |
| **Country requirements** (`/admin/countries`, country detail) | `public.requirement_items` | Sets `review_status` to `approved` or `rejected` | `requirements_builder` and related serving engines **only serve `approved` rows** |

This is the only queue whose Approve publishes a row into the live relocation catalog.

## Evidence / sufficiency (not the served catalog)

| Surface | Table | Approve does | Product reads |
| --- | --- | --- | --- |
| **Content review** (`/admin/content-review`) | Legacy `requirement_facts` | `update_requirement_fact_status` + `requirement_reviews` | Sufficiency / dossier evidence (`list_approved_requirement_facts` → `GET /api/requirements/sufficiency`) |

Approving here records evidence quality. It does **not** insert or flip a `requirement_items` row.

## Dead end (AIQ-1821)

| Surface | Table | Approve does | Product reads |
| --- | --- | --- | --- |
| **Requirement facts** (`/admin/requirement-facts`) | `requirement_fact_candidates` | Status stamp on the candidate only | **Nothing in the serving path.** Hyphenated router is superseded. |

Keep the page for leftover extracts; do not treat it as publication.

## Other Catalog queues (different objects)

- **Catalog queue** — destination scrape allowlist / HR tickets, not requirement rows.
- **Staging** — resource/event candidates before CMS promotion.
- **Resources CMS** — destination lifestyle content, not immigration requirements.
- **Policy workspace** — tenant policy baseline, not country catalog.

## Rule of thumb

If the question is “will an employee see this after I click Approve?”, the answer is **Country requirements** (`requirement_items.review_status = approved`). Everything else is evidence, a candidate, or a different object.
