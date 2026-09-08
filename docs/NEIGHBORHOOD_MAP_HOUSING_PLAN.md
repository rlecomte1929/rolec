# Neighborhood-First Housing Recommendations — Plan

Status: draft for review · Prepared: 2026-07-01
Vision (your words): employee enters criteria → sees a **map of recommended neighborhoods**
first, driven by office location (and school location if there are kids) → schools available in
those areas layer in → narrowing down neighborhoods produces better-targeted vendor (mover /
real-estate agent) recommendations.

## Think-deeply section: what actually exists today vs. what the vision needs

This matters because the honest starting point is better than it looks in the UI, and worse than
it looks under the hood — worth reading before the phases below.

**Better than it looks:** you already have real, free, keyless geo infrastructure, just stranded
in one place. `frontend/src/components/RichCommuteMap.tsx` (used only in the intake wizard's
commute preview) already does: Nominatim geocoding, a mode-speed-based commute radius model
(walking/bike/transit/car), and free Overpass API queries for real schools/transit/sports near a
point — zero API keys, zero cost, already built. This is most of the "map + schools layer"
machinery the vision needs; it's just never been pointed at the Housing recommendations flow.

**Worse than it looks:** the actual `living_areas` recommendation plugin
(`backend/app/recommendations/plugins/living_areas.py`) does not compute commute at all. Each
neighborhood in the dataset (`datasets/living_areas.json`) carries a single hardcoded
`commute_to_work_minutes_estimate` — e.g. Tiong Bahru is always "~18 min" for every employee,
regardless of where their actual office is. There's no lat/lng anywhere in that dataset, or in
the schools dataset. So today's "Housing" recommendations are not personalized to office location
at all, despite the UI collecting an office address — the vision you're describing (neighborhoods
genuinely driven by *this employee's* office) isn't happening yet, it just looks like it might be.

**A second, smaller but real problem to fix first:** the office address is currently captured
*twice*, in two disconnected places — once in the intake wizard (`EmployeeIntakePage.tsx`, geocoded,
required, has the "Verified" badge) and again as an optional, ungeocoded free-text field inside the
Housing service question set (the one that actually feeds the recommendation engine's criteria
today). Building real commute-aware recommendations on top of the wrong/duplicate input would waste
the effort — this needs to be unified before anything else here matters.

## Goals

**Foundational (must happen first, mostly invisible to the user):** make "commute" in housing
recommendations real — computed from the employee's actual, single, geocoded office address — and
extend that same signal to school-age destinations. Without this, a prettier map is just a
prettier version of a wrong answer.

**Core experience (the actual vision):** replace the flat ranked list as the *first* thing an
employee sees for Housing with a map of recommended neighborhoods, office location pinned, sized/
colored by fit score. Toggle a schools layer scoped to *those* neighborhoods (not a generic
city-wide school list) when the employee has school-age children. Let the employee narrow to a
shortlist of neighborhoods interactively.

**Closing the loop:** feed the narrowed shortlist into vendor recommendations, so movers/agents
suggested afterward are relevant to the specific areas the employee actually cares about, not the
whole city.

## Core components, broken into shippable phases

**Phase 0 — Fix the input, don't build on it broken.**
Unify the office address: pre-fill the Housing question's office-address field from the intake
wizard's already-geocoded value (same person, same move, shouldn't ask twice); ideally hide the
duplicate field entirely once this works. Small, contained, and it's the one piece that would
silently undermine everything after it if skipped.

**Phase 1 — Real commute, still no visible UI change yet.**
Add lat/lng to every neighborhood in `living_areas.json` and every school in the schools dataset —
a one-time data task (~30-40 neighborhoods and however many schools across the ~7 supported
cities), geocoded once offline using the same free Nominatim call already in the codebase, not a
live per-request feature. Then change `LivingAreasPlugin.score()` to compute an actual
straight-line-distance-plus-speed-heuristic commute time between the employee's real office
coordinates and each neighborhood's coordinates — reusing the exact `SPEED` mode-heuristic table
already written in `RichCommuteMap.tsx` — instead of reading the static hardcoded estimate. This
is the single highest-leverage change in the whole plan: it's what makes "based on the office
location" true instead of aspirational.

**Phase 2 — The map itself.**
Adapt `RichCommuteMap` (or a sibling component built the same way) into the Housing
recommendations page: office pin, plus one marker per recommended neighborhood, sized/colored by
the score the engine already computes (budget/commute/lifestyle/rating/availability — this part
already works, it just isn't drawn on a map yet). This is almost entirely a frontend build once
Phase 1 supplies real coordinates and real commute numbers to plot.

**Phase 3 — Schools layer, scoped to neighborhoods.**
For each of the top-N recommended neighborhoods, compute which curated schools
(`schools.json`, now geocoded per Phase 1) fall within an acceptable radius/commute of *that
neighborhood* — a new small join, not a new dataset. Render as a toggleable layer, gated on the
employee having school-age children (already known from the household step of intake). Live
Overpass school queries (already coded in `RichCommuteMap`) are a reasonable fallback for
destinations where the curated schools dataset is thin, clearly labeled as "other nearby schools"
vs. the curated, scored ones.

**Phase 4 — Narrow down → vendor recommendations.**
Let the employee explicitly shortlist neighborhoods from the map. Feed that into
`LivingAreasCriteria.preferred_areas` (this field already exists in the model, just never
populated by the UI) and, as a smaller follow-on, tag vendor curation entries with which
neighborhoods a mover/agent actually serves — mirroring the `service_types` tagging that already
exists on catalog vendors from the AI-populate feature — so the vendor list an employee sees after
narrowing is visibly more relevant, not just cosmetically re-sorted.

## Metrics — this is about answer quality, not just shipping the feature

**Commute accuracy (the metric that validates Phase 1):** sample ~10 real office-address/
neighborhood pairs per supported city, compare the app's estimated commute time against actual
Google Maps transit directions for the same pair. Track mean absolute error in minutes. Set an
explicit bar — e.g. within ±10 minutes for 80% of sampled pairs — and be upfront that the free
straight-line-plus-speed-heuristic model in Phase 1 probably won't clear that bar in every city on
day one; that's the intended trigger for deciding whether a real routing API (Google Distance
Matrix, Mapbox Directions, or a self-hosted OSRM) is worth the cost later, using the same
provider-abstraction pattern from the address-autocomplete plan rather than a one-off integration.

**Geo data completeness:** 100% of neighborhoods and curated schools in the supported destination
cities must have real coordinates before Phase 2 ships — a map with missing pins undermines trust
faster than no map at all.

**School-in-neighborhood precision:** spot-check a sample of "this school is reachable from this
neighborhood" claims against real transit directions, same method as commute accuracy.

**Adoption/usefulness (post-launch, product not accuracy metrics):** share of employees who
interact with the map vs. ignore it if a list view stays available as a fallback; share who use
the narrow-down action rather than abandoning; whether narrowing correlates with faster or more
decisive vendor shortlisting afterward (Phase 4's actual point).

**Vendor relevance after narrowing (validates Phase 4):** track the rate of "no vendors match"
empty states for Housing before vs. after neighborhood-scoped vendor tagging exists — the whole
premise of Phase 4 is that narrowing should reduce dead ends, not just re-order the same list.

## How I'd guide the build

- Phase 0 and Phase 1 are backend/data work, deeply entangled with the recommendation engine and
  the intake/services data flow this session has spent a lot of time mapping — I'd do this one
  directly with you, or hand it to Claude Code with the specific files above named, since it needs
  someone who already has the surrounding context loaded rather than rediscovering it.
- Phase 2's map interaction is a real UX design question before it's a code question — how markers
  read at a glance, what happens on tap/click, how the schools-toggle feels — worth a short design
  pass (sketches grounded in `DESIGN.md`'s navy/teal system) before anyone writes the component, so
  the build isn't guessing at the interaction. That's a good moment to use a design-first tool
  rather than jumping straight to code.
- Phase 3 and 4 are incremental on top of 1-2 and can be scoped for real once you've seen the map
  working and know whether the schools layer and narrowing actually feel useful in practice, rather
  than committing to the full interaction design up front.

## Suggested next step

Start with Phase 0 (fix the duplicate office-address input) and Phase 1 (real coordinates + real
commute math) together — they're the foundation, they're both backend/data, and they're
independently verifiable via the commute-accuracy metric before any UI work begins. Want me to
scope Phase 0/1 into concrete file-level tasks next?
