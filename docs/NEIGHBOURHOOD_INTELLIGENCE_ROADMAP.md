# Neighbourhood Intelligence — differentiation roadmap

**Status:** proposal (memo only — no code beyond the shipped PR1–PR5 core).
**Context:** the "Living Areas = 0" rework (PR1–PR5) turned an empty housing category into a
two-surface advisory experience: ranked **neighbourhoods** (advisory) + gated **housing agencies**
(temp/permanent), a persisted shortlist that re-ranks agencies serving the shortlisted areas, an
optional preference questionnaire with input-cited explainability, and a keyless **multimodal
commute** core (walk/bike/transit/car time·cost·carbon). This memo ranks where to take it next.

Each item is scored **Impact × Effort × DPA-risk** (1–5; Impact high = good, Effort/DPA low = good)
and names the data source + the **existing asset to reuse** so nothing is built from scratch.

## Ranked backlog

| # | Item | Impact | Effort | DPA-risk | Reuse / data source |
|---|------|:------:|:------:|:--------:|---------------------|
| 1 | **Real per-agency area coverage** — a `supplier_service_area_coverage` table (supplier × living_areas_id) replacing the `area:*` tag heuristic behind the Δ2 boost | 4 | 2 | 1 | New table (RLS + policy + REVOKE anon per repo rule); HR curation UI; supersedes PR3's `area:*` tokens |
| 2 | **Multi-destination commute burden** — score office **+ school(s) + partner workplace** together, not office-only | 5 | 2 | 1 | `geo.multimodal_commute` (PR5) + `schools_nearby.py` coords; add partner-workplace to intake |
| 3 | **Cost-of-living normalisation to the package** — rent shown vs the employee's housing cap, FX-normalised | 4 | 2 | 1 | `fx_service.py` + policy caps (`_policy_cap_monthly`); already threaded into criteria |
| 4 | **Carbon commute score** — fold the PR5 per-mode CO₂e into a first-class ranking signal + a package-level footprint | 3 | 2 | 1 | PR5 `CARBON_G_PER_KM`; pattern from `ai_carbon_estimator.py` |
| 5 | **Learned ranking** — replace static weights with weights learned from real neighbourhood reactions | 4 | 3 | 2 | `recommendation_slates` + `weight_learner.py` + `preference_dataset_builder.py` (offline loop exists) |
| 6 | **Origin-analog matching** — "like your old neighbourhood in <origin>" | 3 | 3 | 2 | `embeddings.py`; needs a neighbourhood-embedding corpus |
| 7 | **Conjoint preference elicitation** — trade-off questions instead of flat sliders when signal is weak | 3 | 3 | 1 | `conjoint_service.py` + `conjoint_repo.py` (CBC math already DB-free) |
| 8 | **Collaborative shortlisting** — partner/family react to the shortlist | 3 | 3 | 2 | `collaboration_service.py` (threads/comments) |
| 9 | **Expectation overlays** — climate/daylight/noise/air/safety per neighbourhood | 3 | 3 | 3 | External open datasets → each a new sub-processor/DPA review |
| 10 | **Real routing / isochrone commute** — swap the heuristic for Google/Mapbox/OSRM | 4 | 3 | **5** | `geo.commute_minutes` seam (drop-in); **new sub-processor → DPA + (US vendor) SCC/DPF before shipping** |

## Recommended phase order

- **Phase A (low DPA, high leverage — do first):** #1 real area coverage, #2 multi-destination commute,
  #3 cost-of-living normalisation. All reuse shipped assets, no new sub-processor, and directly deepen
  what PR1–PR5 already surface.
- **Phase B (ranking quality):** #4 carbon score, #5 learned ranking (the slates→weight_learner loop is
  already built and running offline — this is mostly turning it on with guardrails).
- **Phase C (elicitation & social):** #6 origin-analog, #7 conjoint, #8 collaborative shortlisting.
- **Phase D (gated on legal):** #9 expectation overlays and #10 real routing — **each needs a PRIV-004
  sub-processor entry + DPA sign-off before it ships.** Stage the code behind a flag; do not enable
  until legal clears the transfer mechanism.

## Standing gates (bind every item above)
- New public table (#1) ⇒ RLS + tenant policy + `REVOKE ALL … FROM anon`, migration committed (applied
  out-of-band, ledger reconciled). Never `apply_migration` to prod.
- Any new outbound data provider (#9, #10) ⇒ a new **PRIV-004** sub-processor row + DPA before shipping;
  US vendors need SCC/DPF. **Note:** `geo.geocode` already calls `nominatim.openstreetmap.org` with the
  office address — reconcile this against PRIV-004's "only Geoapify" line as part of Phase D groundwork.
- Any LLM call added (e.g. #6 corpus building) ⇒ mask PII first (`pii_masker.mask_pii`) — and note it does
  **not** mask addresses, so office/home addresses need explicit handling.
- All employee-facing copy describes controls/product facts — never an EU AI Act status
  (`check_compliance_claims.py`).
