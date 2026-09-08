# How to load Otto (Audos) research into ReloPass — playbook

*Paste this whole file into a new Claude Cowork session (one with the Supabase
connector). It is self-contained: it tells you exactly how to pull Otto's research
from Google Cloud Storage (GCS) and load it into the ReloPass Supabase database.
Proven working on 2026-08-13.*

---

## 1. The idea in one paragraph

Otto runs research inside Audos. Its **real deliverable is not the chat text** —
it's a set of **JSON files saved on Google Cloud Storage (GCS)**. Each research
run also produces a **manifest**: a small JSON file that lists every data file
with its target table, record count, and full GCS URL. To get the data into
ReloPass, you point a pre-built loader at a manifest URL; the loader fetches every
file, maps each record to the right ReloPass table, removes duplicates, and
inserts everything as **pending candidates** (nothing goes live until a human
review step promotes it).

## 2. The ONE rule about URLs (this bites everyone)

When Otto pastes GCS links into chat, they get **truncated** (they end in `…`) and
are useless. Always get the **complete** URL. Two reliable ways:

- Ask Otto to deliver the manifest + data files as **attachments**, or
- Ask Otto to paste the GCS URLs as **plain text, one per line, untruncated** (no
  markdown tables, no shortened links).

A GCS URL looks like:
`https://storage.googleapis.com/audos-images/workspace-media/<folder>/<file>.json`

> **2026-08-13 addendum — a third and better way.** Asking Otto for untruncated
> URLs does not reliably work: the Audos chat renderer truncates the anchor's
> *link text* while leaving the `href` complete. Reading the page's accessibility
> tree returns the full URL directly, with no Otto round trip. Only URLs where
> Otto typed the ellipsis into the markdown itself (they resolve to
> `https://%E2%80%A6/...`) are genuinely lost.

## 3. What you already have (no need to build)

- **Supabase project id:** `nsvefcvpvwwwhuqyuqmp`
- **A deployed edge function called `otto-loader`** that does the whole job. Two
  modes: `dry_run=true` (reports what *would* load, writes nothing) and
  `dry_run=false` (actually inserts). It is idempotent — safe to re-run; it skips
  rows already loaded.
- **Loader access token:** stored as the `OTTO_LOADER_TOKEN` secret on the edge
  function, and sent in the **`x-otto-token` header** — never as a query
  parameter, because query strings land in Supabase's request logs and in every
  proxy between here and there.
  The previous token was hardcoded in the function source and passed as
  `?token=…`; it is **burned** and now rejected. Ask Romain for the current value;
  do not paste it into a document, a ticket, or a chat.
- The loader handles Otto's **messy, inconsistent file formats** automatically
  (different runs name the same thing `fact_text` vs `body` vs `requirement`,
  `name` vs `vendor_name`, sometimes omit `topic_key`, etc.).

## 4. How to call the loader (the key trick)

You **cannot** call the function with WebFetch — Anthropic's web proxy blocks the
Supabase functions endpoint (403). Instead, call it **from inside the database**
using the `pg_net` extension (already installed), then read the reply. Use the
Supabase `execute_sql` tool for every step below.

### Step A — DRY RUN first (no writes)

Replace `<MANIFEST_URL>` with the real, complete manifest URL.

```sql
SELECT net.http_get(
  url := 'https://nsvefcvpvwwwhuqyuqmp.supabase.co/functions/v1/otto-loader',
  params := jsonb_build_object(
    'dry_run','true',
    'manifest','<MANIFEST_URL>'
  ),
  headers := jsonb_build_object(
    'x-otto-token','<OTTO_LOADER_TOKEN>'
  ),
  timeout_milliseconds := 120000
) AS req_id;
```

This returns a number (`req_id`). Wait a few seconds, then read the result:

```sql
SELECT id, status_code, timed_out, error_msg, content
FROM net._http_response WHERE id = <REQ_ID>;
```

`content` is a JSON report: how many files were fetched, and per table how many
rows **would** be inserted (`mapped_new`), how many are duplicates, and anything
skipped. If `content` is empty, wait a few more seconds and re-run the read (the
job is still running). Sanity-check that `files_fetched` matches `files_total` and
`unrouted.seen` is 0.

### Step B — check prerequisites the report flags

The dry-run report has a `prerequisites` block. In almost all cases it's already
handled. The only thing to watch: `widen_domain_area` — if it lists a domain
**not** in the list below, run this once (add the new value at the end):

```sql
ALTER TABLE public.requirement_entities DROP CONSTRAINT requirement_entities_domain_area_check;
ALTER TABLE public.requirement_entities ADD CONSTRAINT requirement_entities_domain_area_check
  CHECK (domain_area = ANY (ARRAY[
    'immigration','registration','tax','social_security','healthcare','housing','other',
    'vehicle','vehicle_import','domestic_move','financial','employer_compliance','pet'
    -- , '<new_domain_from_report>'
  ]));
```

(The country limit was already removed, so new destination countries just load —
no action needed.)

### Step C — LOAD FOR REAL (dry_run=false)

Same call, `dry_run` set to `false`:

```sql
SELECT net.http_get(
  url := 'https://nsvefcvpvwwwhuqyuqmp.supabase.co/functions/v1/otto-loader',
  params := jsonb_build_object(
    'dry_run','false',
    'manifest','<MANIFEST_URL>'
  ),
  headers := jsonb_build_object(
    'x-otto-token','<OTTO_LOADER_TOKEN>'
  ),
  timeout_milliseconds := 150000
) AS req_id;
```

Then read `net._http_response` for the same `req_id` and look at the `inserted`
counts per table. Re-running is safe — it will just skip what's already there.

**Optional:** to load only some tables, add
`'tables','vendor_candidates,pet_import_rules'` to the params. To test on a few
files first, add `'limit_files','10'`.

### Step D — verify

```sql
SELECT
 (SELECT count(*) FROM requirement_facts)           AS facts,
 (SELECT count(*) FROM requirement_entities)        AS entities,
 (SELECT count(*) FROM vendor_candidates)           AS vendors,
 (SELECT count(*) FROM pet_import_rules)            AS pets,
 (SELECT count(*) FROM staged_resource_candidates)  AS resources;
```

> **2026-08-13 addendum — verify by shape, not just by total.** A rising total can
> hide a half-load. Also run the entities-vs-facts join per country; any
> `domain_area` with entities and **zero** facts means the facts file did not land
> and must be re-loaded.

## 5. Where the data lands

Everything is inserted as **`status='pending'` candidates** (a review-then-promote
staging area — nothing is published to the live product automatically):

- **Providers / vendors / advisors** → `vendor_candidates`
- **Immigration + vehicle + domestic facts** → `requirement_facts` (+ their
  `requirement_entities`), keeping `applies_to`, `fact_key`, and `evidence_quote`
- **Pet import rules** → `pet_import_rules` (origin-group variants merged into one
  row per country+species)
- **Guides / neighbourhoods / crisis / how-to content** → `staged_resource_candidates`

## 6. Gotchas (learned the hard way)

- **Truncated URLs** are the #1 blocker — insist on complete URLs or attachments
  (see §2, and the addendum for the DOM route).
- **Call via `pg_net`, not WebFetch** — the functions endpoint is proxy-blocked (§4).
- **Otto's file formats are inconsistent across runs** — the loader already
  tolerates this; if something new slips through it shows up as `skip_*` or
  `unrouted` in the report, so read those counts.
- **Never run Otto's raw SQL scripts** against the database — it writes them blind
  and they hit constraints. Only use this loader.
- **Duplicates:** if you accidentally load the same run twice with different
  settings, de-duplicate `vendor_candidates` by keeping one row per
  `(lower(trim(name)), city, source_url, service_category)` — but keep rows that
  share a name across **different** source URLs (those are legit multi-country
  providers, e.g. global shippers).
- After loading, the data still needs a **human review pass** to promote
  candidates to live records.

## 7. If the `otto-loader` function is missing

If a future project doesn't have it, redeploy it from the accompanying source file
(`otto-loader-index.ts`) using the Supabase `deploy_edge_function` tool with
`verify_jwt=false` and name `otto-loader`. Then continue from §4.

---

### Quick request template to send Otto

> "Give me the **manifest file(s)** for the run — a JSON index listing every data
> file with its `target_table`, `record_count`, and **complete** `gcs_url`. Deliver
> as attachments, or paste the GCS URLs as plain text, one per line, untruncated.
> Also confirm every record has a `dedupe_key` and a `source_url`."
