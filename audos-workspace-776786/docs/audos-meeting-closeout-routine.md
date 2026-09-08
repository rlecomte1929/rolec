# Audos meeting close-out routine

A repeatable pass over the open meetings in the ReloPass Audos space that decides,
per meeting, whether it is finished — and closes it only when the *result* is
verifiable outside Audos.

**Cadence:** run it whenever the open list passes ~20 meetings, or after any
research wave completes. It took one session to do 66; a weekly run should take
20 minutes.

**Standing rule — the one that makes this worth doing:**
> A meeting is finished when a row count in ReloPass moved, or a file landed in
> the repo. Not when Otto says the task completed, and not when the meeting shows
> "Awaiting review". Both of those have been wrong in this workspace.

---

## Step 0 — Snapshot ReloPass before you look at Audos

Take the ground truth first, so you are never reading the meeting list for clues
about what landed.

```sql
-- run via the Supabase connector on project nsvefcvpvwwwhuqyuqmp
SELECT 'requirement_entities' t, count(*) n, max(created_at) last FROM public.requirement_entities
UNION ALL SELECT 'requirement_facts',   count(*), max(created_at) FROM public.requirement_facts
UNION ALL SELECT 'service_catalog_items',count(*), max(created_at) FROM public.service_catalog_items
UNION ALL SELECT 'vendor_candidates',   count(*), max(created_at) FROM public.vendor_candidates
UNION ALL SELECT 'pet_import_rules',    count(*), max(created_at) FROM public.pet_import_rules
UNION ALL SELECT 'staged_resource_candidates', count(*), max(created_at) FROM public.staged_resource_candidates;
```

Then the two breakdowns that catch partial loads:

```sql
-- immigration/vehicle by country — an entity count with 0 facts is a broken load
SELECT e.destination_country, e.domain_area,
       count(DISTINCT e.id) entities, count(f.id) facts, max(e.created_at)::date last
FROM public.requirement_entities e
LEFT JOIN public.requirement_facts f ON f.entity_id = e.id
GROUP BY 1,2 ORDER BY 1,2;

-- providers by city — compare against the cities the last wave researched
SELECT city, count(*) n, count(DISTINCT category) cats, max(created_at)::date last
FROM public.service_catalog_items GROUP BY 1 ORDER BY 2 DESC;
```

**Two failure signatures to look for every single time:**

- *Entities with zero facts* — the entities file loaded, the facts file did not.
- *A researched city with no rows, or rows older than the research* — the file was
  produced and never loaded at all.

---

## Step 1 — Pull the open meeting list

Open `https://audos.com/workspace/d0c29613-9cb5-4652-9c6a-494eeed352e5` and read
the page's accessibility tree rather than screenshotting the sidebar — the tree
carries the **full** meeting titles, which the sidebar truncates at ~28
characters, plus each row's status badge and age.

Record per meeting: title · age · badge · the "TASKS KICKED OFF HERE" count.

---

## Step 2 — Harvest deliverable URLs from the DOM, not from the chat text

The Audos chat renderer truncates link *text* to `...494......` but leaves the
`href` intact. Reading the accessibility tree returns complete, working GCS URLs.
**Do not ask Otto to re-print them untruncated — it cannot, and it will loop.**

Exception: where Otto typed the ellipsis into the markdown itself, the href
resolves to `https://%E2%80%A6/...` and that URL is genuinely unrecoverable. Look
for a superseding corrected file before treating it as a loss.

Save the recovered URLs to `audos-workspace-776786/data/gcs-deliverable-index.json`
so the next run starts from a diff, not from scratch.

---

## Step 3 — Classify each meeting

| bucket | test | action |
|---|---|---|
| **CLOSE** | Result present in Supabase, or artefact committed to `rolec` | Mark as complete |
| **HARVEST FIRST** | Meeting holds deliverable URLs or manifests not yet captured | Harvest → load → then close |
| **KEEP OPEN** | Linked Notion task is `Ready for AI` / `Blocked` / `Human Review` | Leave; it is a live thread |
| **VERIFY** | Title truncated, or no linked artefact | 30-second check, then re-bucket |
| **STALE** | Older than ~3 weeks with no artefact | Close; restart fresh when the work resumes |

For code-fix meetings, the check is Notion + `git log`, not Supabase:

```bash
cd ~/mnt/rolec && git log --since="<date of the wave>" --pretty=format:"%ad|%h|%s" --date=short
```

Notion AI Work Queue: `7adc643a-c448-4a1a-ba80-e27e417f42d6`. `Status = Done`
**and** `Final Validation Result = Passed` → the meeting can close.

---

## Step 4 — Load what is loadable before closing anything

For every HARVEST FIRST meeting, run the loader per
`docs/otto-to-relopass-loading-playbook.md`: dry run → read `prerequisites` →
real load → verify counts. Only then close the meeting.

Loading before closing matters because the meeting is the only durable pointer to
its GCS files. Close it first and the URLs are archived with it.

---

## Step 5 — Close in approved batches

Close by group, never one at a time and never all at once:

1. Immigration corridors verified in the DB
2. Shipped fixes (Notion Done/Passed)
3. Stale meetings older than 3 weeks
4. Harvested meetings, after their load is verified

In Audos: each sidebar row has its own **Mark as complete** button. After each
batch, re-read the list and confirm the count dropped by exactly the number you
closed. Closed meetings remain reachable under **View completed meetings**.

---

## Step 6 — Write the register

Append this run to `audos_meeting_register_<date>.csv` with one row per meeting:

```
meeting_title,age,audos_badge,group,action_taken,result_landed_in_relopass,
evidence,verdict,reason
```

`evidence` must be a *number or a commit*, never a sentence — "SG 21 entities /
77 facts" or "commit d13bf80a", not "looks complete". The register is what makes
the next run a diff instead of a repeat.

---

## Step 7 — Report the yield

Three numbers, every run:

- **Volume** — meetings closed, rows landed, countries/cities covered.
- **Yield** — what fraction of completed research actually reached ReloPass.
  (2026-08-13 baseline: ~⅔ — immigration ~100%, providers 0% for the last two
  waves, vehicle 6/24 countries.)
- **Handoff failures** — count of entity-without-facts and researched-city-with-no-rows.
  This number should trend to zero; it is the health metric for the whole loop.

---

## Quick checklist

- [ ] Supabase snapshot taken **before** reading Audos
- [ ] Both partial-load signatures checked
- [ ] Meeting list read from the accessibility tree (full titles)
- [ ] GCS URLs harvested from `href`, not from link text
- [ ] Everything loadable loaded and verified
- [ ] Closes approved by group, count confirmed after each batch
- [ ] Register updated with numeric evidence
- [ ] Yield + handoff-failure count recorded
