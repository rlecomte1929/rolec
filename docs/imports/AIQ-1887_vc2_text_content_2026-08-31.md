# AIQ-1887 VC2 — reconcile the stale placeholder `text_content`

Companion to `AIQ-1887_vc1_demotion_2026-08-31.md`. VC1 was the fact-status invariant; this is
VC2: *"0 `knowledge_docs` with `fetch_status='fetched'` whose `text_content` is the Otto
placeholder."*

## What VC2 is, and why it regressed

`knowledge_docs.text_content` is Otto's original capture, and for 218 docs its *entire* value is
the literal string `Otto bridge capture, unverified — see source_url`. When the evidence backfill
later re-fetched a page it wrote the real archived text to a **different** column,
`content_excerpt` (the column the evidence check and the review queue actually read), and set
`fetch_status='fetched'` — but never rewrote the stale `text_content`. So a successfully-fetched
doc ends up `fetched` while its `text_content` still reads the placeholder. That is the VC2
violation.

`text_content` is **not** on the serving or evidence path — it is read only by the admin/ops
display (`backend/app/routers/admin.py`). Replacing the placeholder with the real
`content_excerpt` is therefore safe and strictly an improvement; it changes no served output.

## Measured on prod (`nsvefcvpvwwwhuqyuqmp`, 2026-08-31)

| cohort | count |
|---|---:|
| `text_content` = placeholder, **all** `fetch_status` | 218 |
| …of those `fetch_status='fetched'` (the VC2 target) | **172** *(drifting; 176 earlier — a backfill is running)* |
| …of the 172, carrying a real `content_excerpt` (≥200 chars, not the placeholder) | **172 (100%)** |
| …of the 172, NOT fixable from `content_excerpt` | 0 |

Every one of the 172 has a real archived excerpt, so a single UPDATE clears the whole cohort. The
other `218 − 172 = 46` are `not_fetched` / `fetch_failed`: their placeholder is honest (no real
content was ever captured), so they are **out of VC2 scope** — refetching them is D3-style work,
not this.

## The fix (operator applies; idempotent; not applied here)

```sql
-- Capture the rollback set FIRST, in the same session, because the cohort drifts:
\copy (SELECT id FROM public.knowledge_docs \
        WHERE fetch_status='fetched' AND text_content LIKE '%Otto bridge capture, unverified%') \
  TO 'AIQ-1887_vc2_rollback_ids.csv' CSV

BEGIN;
UPDATE public.knowledge_docs
   SET text_content = content_excerpt
 WHERE fetch_status = 'fetched'
   AND text_content LIKE '%Otto bridge capture, unverified%'
   AND content_excerpt IS NOT NULL
   AND length(content_excerpt) >= 200
   AND content_excerpt NOT LIKE '%Otto bridge capture, unverified%';   -- ~172 rows (drifting)

-- VC2 acceptance — must be 0 before COMMIT:
SELECT count(*) FROM public.knowledge_docs
 WHERE fetch_status='fetched' AND text_content LIKE '%Otto bridge capture, unverified%';
COMMIT;
```

Idempotent: a second run matches 0 rows, because the updated `text_content` no longer contains the
placeholder. The `content_excerpt`-not-placeholder guard means a doc whose excerpt is itself the
placeholder (none today) is left untouched rather than copied onto itself.

Rollback: `UPDATE public.knowledge_docs SET text_content = 'Otto bridge capture, unverified — see
source_url' WHERE id IN (<the captured ids>);` — the whole `text_content` of every affected row was
that exact string before the change.

No frozen id list is committed here — the cohort drifts while the backfill runs, so the `\copy`
above captures the true set at the instant of the change.

## D4 is already done (recorded here so nobody re-builds it)

The tail card also named D4 — a unique index on `requirement_items (country_code, purpose, title)`.
**It already exists.** `supabase/migrations/20261118000000_requirement_items_corridor_import_idempotency.sql`
dedupes the natural-key groups and creates `uq_requirement_items_country_purpose_title`; that
version is in the prod ledger and the index is live (verified 2026-08-31: index present, 0 duplicate
groups across 574 rows). `docs/corridors/DATA-PATHS.md` recommending it is simply stale. The two
*optional* follow-ons it lists — pointing convention-4 (`gen_ie_es_corridor_load.py`) at `crud`, and
normalising `citations_json` to `source_record` ids — remain open but are separate, lower-priority
refinements, not the natural-key backing.
