
# Pets Service Category & Vendor-Curation Hardening — Implementation Plan

Status: draft for review · Owner: Romain · Prepared: 2026-07-01
Covers two related but independent workstreams surfaced while investigating the
employee Pets flow and the HR Service Providers page:

1. **Bug fix** — "Internal server error" on the HR vendor-curation page.
2. **Feature** — promote Pets from a bolted-on intake question + standalone card
   into a first-class, HR-curated service category like Movers/Banks/Insurance.

Part 2 depends on nothing in Part 1; they can ship independently and in either order.

---

## Part 1 — Fix: "Internal server error" in vendor curation

### Scope

`POST /api/hr/catalog/populate-destination-with-ai` (`backend/app/routers/hr_catalog.py`,
the handler behind the "Populate all services with AI" button). Also apply the
same defensive pattern to the single-category sibling,
`POST /api/hr/catalog/populate-with-ai`, as cheap insurance.

### Root cause (best available diagnosis — see caveat)

The destination-level handler loops over all 14 registered categories
(`hr_catalog.py:585-639`) and, for each one, calls
`catalog_scraper.populate_destination_catalog(...)` and, later, in a second loop,
`catalog_scraper.backfill_service_types(...)`. Neither loop has a per-iteration
`try/except`. The LLM-calling internals of both functions are already
well-guarded (`_call_llm`, `_parse_vendors`, `_parse_tags` all catch and degrade
gracefully), but nothing protects the surrounding loop against any *other*
unexpected exception (a DB hiccup in `service_catalog.count_by_category_city`,
`service_catalog.merge_attributes`, an edge case not covered by the existing
`isinstance` guards, etc.). One bad category aborts the entire batch and the
whole request 500s with no detail — exactly the raw "Internal server error"
banner in the screenshot, most likely triggered by clicking "Populate all
services with AI" for Melbourne, Australia.

**Caveat:** this is a static-analysis diagnosis, not a confirmed stack trace —
I don't have access to the Render application logs to see the actual exception.
The fix below is worth doing regardless of the exact trigger, because the
current design lets any single category's failure take down the whole batch
action with zero visibility into what succeeded. If this recurs, pulling the
Render log line for the failing request's timestamp would confirm the exact
line and let us close the loop with certainty.

### Fix

In both loops inside `populate_destination_with_ai`:
- Wrap the `populate_destination_catalog(...)` call (and the `count_by_category_city`
  pre-check) per category in `try/except Exception`.
- On failure: `logger.exception(...)` with category/city/country context, append
  `{"category": cat, "status": "error", "inserted": 0}` to `results`, and continue
  the loop instead of propagating.
- Do the same around the final `backfill_service_types` loop.
- Endpoint must always return HTTP 200 with a per-category breakdown — never let
  one category's exception surface as a raw request-level 500.
- Apply the identical `try/except` shape to `populate_with_ai` (single-category
  path) around its `populate_destination_catalog` + `backfill_service_types` calls.

### Verification

- New test `backend/tests/test_hr_catalog_router.py` (no existing test file for
  this router today): mock `catalog_scraper.populate_destination_catalog` to
  raise for one category in a multi-category run; assert the endpoint returns
  200, the failing category shows `status: "error"` in `per_category`, and the
  other categories still show `populated`/`skipped_existing` as expected.
- Manual QA: re-run "Populate all services with AI" against a destination with
  mixed populated/unpopulated categories (e.g. Melbourne again) and confirm no
  red error banner appears even if one category fails — the success alert
  should render with a partial-failure note instead.
- Metric: zero raw 500s logged against `/api/hr/catalog/populate-*` in Render
  over the following week of use (spot-check via Render logs or Sentry if wired
  up — worth confirming whether error tracking exists for this route at all;
  if not, that's a small separate follow-up).

### Tools/access needed

None beyond normal dev workflow. If we want to *confirm* root cause before
writing the fix, Render log access (or Sentry, if configured) for the exact
request timestamp would remove the caveat above.

---

## Part 2 — Pets as a first-class service category

### Current state (confirmed in code + prod data)

- `has_pets` is a required yes/no question in intake Step 1
  (`frontend/src/features/platform-v2/intake/EmployeeIntakePage.tsx`), feeding
  nothing else — no backend consumer (roadmap, requirements engine) reads it.
- A standalone `PetRelocationCard` (`frontend/src/features/services/PetRelocationCard.tsx`)
  renders on the Preferences step (`ServicesQuestions.tsx`) whenever
  `has_pets === true`, independent of the normal service-tile selection.
- `serviceConfig.ts` already defines a `pets` tile (`enabled: false`), so it
  never appears in the "Select services" grid.
- Pets does **not exist** as a vendor-curation category: it's absent from
  `HrVendorCuration.tsx`'s `CATEGORY_OPTIONS`/`CATEGORY_LABELS` and from the
  backend plugin registry (`backend/app/recommendations/registry.py` lists 14
  plugins — Living Areas, Movers, Schools, Banks, Insurance, Electricity,
  Medical, Telecom, Childcare, Storage, Transport, Language/Integration, Legal
  & Admin, Tax & Finance — no Pets). HR has no way to curate pet vendors today,
  by destination or otherwise.

### Goal

Retire the special-cased intake question + bolted-on card. Make Pets behave
exactly like Movers: a selectable tile in "Select services," HR curates vendors
per destination, the employee sees recommendations once HR has approved them —
and until then, the tile is visibly **locked** rather than silently producing
an empty result three steps later.

### Design decision needed before implementation

There is no existing "locked before you even select it" pattern anywhere in the
app today. The current empty-state handling (the yellow "Your HR is finalizing
providers for this category" box) only appears *after* you've selected a
service and reached Recommendations — it doesn't block selection up front.
Two ways to deliver what you described, trading effort against fidelity to
"leave it locked":

**Option A — true pre-selection lock (new pattern, more work).**
Add a lightweight employee-facing check — "does my destination have at least
one curated pets vendor?" — and use it to render the Pets tile as visibly
disabled (lock icon, tooltip: "Not available for your destination yet — check
back soon") before the employee can even select it. Requires a new endpoint
(read-only, employee-scoped) and new tile-level UI state in the Select
Services grid.

**Option B — reuse the existing empty-state machinery (minimal diff).**
Enable the `pets` tile now. Selecting it behaves like any other category: if
HR hasn't curated vendors yet, the employee sees the same "HR is finalizing
providers for this category" box at Recommendations that Movers/every other
category already shows. No new endpoint, no new tile state — 100% reuse.
Downside: it's discoverable-but-not-literally-locked; the employee can select
it and only learns it's empty one step later.

My recommendation: ship **Option B** first — it's the same effort as any other
new category and ships the moment vendor data exists — and revisit Option A
only if the one-step-later empty state proves confusing in practice. Flagging
this as a decision point rather than assuming; happy to build A directly if
you'd rather have the tile literally locked from day one.

### Implementation steps

**1. Backend — register Pets as a real category**
- Add `PetsPlugin` in `backend/app/recommendations/plugins/` following the
  shape of `movers.py` (title, `CriteriaModel`, key `"pets"`).
- Register it in `registry.py`'s `_init_registry()` plugin list.
- This alone makes `pets` show up everywhere that reads `list_categories()`,
  including the "Populate all services with AI" batch loop and
  `AdminCatalogQueuePage.tsx` (which is data-driven off actual demand/coverage,
  not a hardcoded list — no manual edit needed there).

**2. HR curation UI**
- Add `pets: 'Pets'` to `CATEGORY_LABELS` and `CATEGORY_OPTIONS` in
  `frontend/src/pages/HrVendorCuration.tsx` so HR can pick "Pets" in the
  category dropdown and curate vendors per destination exactly like Movers.

**3. Employee service catalog**
- Flip `enabled: true` for the `pets` entry in
  `frontend/src/features/services/serviceConfig.ts`.
- (Option A only) add the availability check + locked tile rendering.

**4. Migrate the pet-detail questions into the standard per-category flow**
- Locate the source of the existing per-category dynamic questions (the ones
  driving "Origin city / Move type / Current accommodation type / …" under
  Movers in `ServicesQuestions.tsx` — `DynamicQuestion` records keyed by
  `service_category`). Add a `pets` question set there with the three fields
  `PetRelocationCard` collects today: species, number of pets, specific needs.
- Delete `PetRelocationCard.tsx` and its import/usage in `ServicesQuestions.tsx`
  once the equivalent questions exist in the standard flow.
- Preserve the existing `pet_relocation` answers key if reasonably possible, to
  avoid a data migration for in-flight cases that already saved pet details
  under the old card.

**5. Remove the intake question**
- Delete the "Will you be relocating with pets?" field from
  `EmployeeIntakePage.tsx` (question block, `has_pets` state, the step-1
  validation check at line ~731, and the `has_pets` mention in the
  international-move banner copy).
- Leave the `has_pets` column/key alone in existing `intake_draft` JSON blobs
  (no backend consumer reads it — safe to strand it) rather than writing a
  cleanup migration for a field with no downstream effect.

**6. Seed data**
- Vendor data for `pets` won't exist until HR curates it or runs "Populate all
  services with AI" for a destination. Confirm the Pets LLM-scrape prompt
  (`catalog_scraper._build_prompt`) produces sane categories for the new plugin
  key before relying on it in a demo.

### Files touched (summary)

Backend: `backend/app/recommendations/plugins/pets.py` (new),
`backend/app/recommendations/registry.py`.
Frontend: `frontend/src/pages/HrVendorCuration.tsx`,
`frontend/src/features/services/serviceConfig.ts`,
`frontend/src/pages/services/ServicesQuestions.tsx`,
`frontend/src/features/platform-v2/intake/EmployeeIntakePage.tsx`.
Removed: `frontend/src/features/services/PetRelocationCard.tsx`.

### Verification / metrics

- `cd frontend && npx tsc --noEmit` clean (removing `has_pets` will orphan
  types/state — expect to touch `EmployeeIntakePage.tsx`'s data model too).
- New/updated tests: intake wizard no longer requires or renders the pets
  question (update `frontend/e2e/intake-persistence.spec.ts`, which currently
  clicks `intake-has_pets-no`); `PetRelocationCard` tests removed; a new test
  covering the `pets` dynamic questions rendering under Movers-style flow.
- Manual QA: full loop — HR curates a Pets vendor for a destination → employee
  with `pets` selected sees it in Recommendations; employee at a destination
  with no curated Pets vendor sees the same "HR is finalizing" empty state
  Movers shows today.
- Product metric worth tracking post-launch: % of employees who select the
  Pets tile vs. the historical % who answered "yes" to the old intake
  question — sanity-checks that removing the forced yes/no didn't just make
  pets relocation invisible to people who need it.

### Open questions for you

1. Option A (true lock) or Option B (reuse existing empty-state, ship faster)?
2. Should the Pets tile go live before HR has curated any vendors anywhere
   (so the category exists but is empty for everyone at first), or should it
   stay `enabled: false` until you've pre-seeded at least a few destinations?

---

## Suggested sequencing

1. Part 1 (bug fix) — small, isolated, no design decision blocking it.
2. Part 2, steps 1–3 (register category, HR curation, enable tile) — get the
   plumbing in place.
3. Part 2, step 4 (migrate question fields) and step 5 (remove intake question)
   together, so there's never a window where pets details can't be captured
   anywhere.
4. Seed a couple of destinations so the category isn't empty everywhere on day one.
