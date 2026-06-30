# 36 — Ranking Gold Worksheet

**Purpose:** Independent supplier ranking gold standard for `golden_rankings.json` to replace the
self-seeded, vacuous NDCG gate.  Romain: review each grade inline; change any cell you disagree
with before committing the updated fixture.

**Date:** 2026-06-30  
**Author:** Claude (engine-independent, criteria-driven)  
**Fixture file (worktree):** `.claude/worktrees/eval-quality-flywheel/backend/tests/fixtures/ranking/golden_rankings.json`  
**Dataset files (worktree):** `backend/app/recommendations/datasets/{banks,insurance,movers}.json`

---

## Vacuity Confirmation

The engine's `recommend_debug()` output (via `run_ranking_eval.py`) was compared against the
fixture's `ideal_order` for all three cases.  All three match exactly:

| Case | Engine order | Fixture ideal_order | Match? |
|------|-------------|---------------------|--------|
| banks SG-SG | b-1,b-9,b-10,b-4,b-2,b-5,b-6,b-3,b-7,b-8 | b-1,b-9,b-10,b-4,b-2,b-5,b-6,b-3,b-7,b-8 | **YES — vacuous** |
| insurance SG-SG | i-4,i-3,i-9,i-1,i-5,i-8,i-2,i-6,i-10,i-7 | i-4,i-3,i-9,i-1,i-5,i-8,i-2,i-6,i-10,i-7 | **YES — vacuous** |
| movers SG-JP | m-8,m-2,m-6,m-1,m-3,m-4,m-5,m-7,m-9,m-10 | m-8,m-2,m-6,m-1,m-3,m-4,m-5,m-7,m-9,m-10 | **YES — vacuous** |

The gate scores 1.0 on all cases and cannot fail. The fixture was seeded by running the engine and
copying its output as gold.

---

## Engine Structural Issues Found

Before grading, the following bugs make the engine's output diverge from user intent:

### Banks
1. `fee_sensitivity` in criteria is **ignored** — the plugin scores `item.fee_level` with a fixed map
   and does not adjust weights based on the user's stated fee priority.
2. `expat_friendliness_priority` (9/10) and `digital_priority` (9/10) are **ignored** — fixed
   weights 0.15 each, regardless of user priority.
3. `branch_need` is **ignored** — fixed weight 0.10 regardless; a user who says "medium" gets the
   same branch weighting as one who says "none".
4. Consequence: Wise/Revolut (zero branches) rank #2/#3 despite `branch_need=medium`.

### Insurance
5. 8 of 10 providers score within 1.2 raw points (97.9–99.1) because all share full criteria
   compliance.  Ranking within this cluster is determined solely by rating (0.15 weight, ~0.4-pt
   differences) → practically arbitrary tie-breaking.
6. No distinction between expat-specialized insurers (Cigna, Allianz, Bupa, GeoBlue) and
   local/regional ones (AIA, Prudential, Manulife, AXA) that may lack global network coverage.

### Movers
7. `service_areas` is stored in the dataset but **never scored** — the plugin does not check whether
   a mover actually covers the SG→JP corridor.
8. `international_capable=False` movers receive a 0.3× capacity penalty but are not excluded.
   m-3 (Shalom, SG-only) ranks #5 for an international move.
9. Pacific Relocations (m-8) ranks #1 despite `max_volume_m3=35 < 38 m³ estimate` and
   service_areas listing only Singapore+Australia+NZ (no Japan).
10. Asian Tigers (m-1) ranks #4 despite being the only mover with Tokyo explicitly in service_areas.

---

## Case 1 — Banks SG-SG

### Criteria
```json
{
  "destination_country": "SG",
  "preferred_languages": ["en"],
  "fee_sensitivity": "low",
  "expat_friendliness_priority": 9,
  "digital_priority": 9,
  "branch_need": "medium"
}
```

`fee_sensitivity: low` = user has low sensitivity to fees (fees matter less).  
`expat_friendliness_priority: 9` = very high priority.  
`digital_priority: 9` = very high priority.  
`branch_need: medium` = moderate need for physical branches.

### Supplier Attribute Table
Source: `backend/app/recommendations/datasets/banks.json`

| ID | Name | fee_level | expat_friendly | digital_features | branch_availability | rating | lang_support | Engine raw |
|----|------|-----------|---------------|-----------------|--------------------|---------|--------------|----|
| b-1 | DBS | low | 9 | 9 | high | 4.5 | en,zh,ms | 94.00 |
| b-2 | OCBC | low | 8 | 8 | high | 4.4 | en,zh | 89.80 |
| b-3 | UOB | **medium** | 8 | 8 | high | 4.3 | en,zh | 85.85 |
| b-4 | Citibank | **medium** | **10** | 9 | medium | **4.6** | en,zh,ja | 90.45 |
| b-5 | HSBC | **medium** | **10** | 9 | medium | 4.5 | en,zh | 89.25 |
| b-6 | Standard Chartered | **medium** | 9 | 8 | medium | 4.4 | en,zh | 86.05 |
| b-7 | Maybank | low | 6 | 7 | high | 4.2 | en,zh,ms | 83.90 |
| b-8 | CIMB | low | 6 | 7 | medium | 4.1 | en,zh | 81.20 |
| b-9 | Wise | low | **10** | **10** | **none** | **4.7** | en | 91.40 |
| b-10 | Revolut | low | **10** | **10** | **none** | 4.6 | en | 91.20 |

### Independent Grade Proposal
Grading key: 3 = ideal / 2 = strong / 1 = acceptable / 0 = irrelevant

**Weighting logic applied:**  Expat (priority 9) and digital (priority 9) are the dominant axes.  
Branch: `medium` need means no-branch banks are penalized but not excluded.  
Fee: `low` sensitivity means fee level is a minor differentiator — medium-fee banks are not heavily penalized.

| ID | Name | Proposed grade | Engine grade | Rationale |
|----|------|:--------------:|:------------:|-----------|
| b-4 | Citibank | **3** | 1 | Highest expat score (10), high digital (9), best rating (4.6), purpose-built global expat bank. Medium fee irrelevant given low sensitivity. Medium branch sufficient. |
| b-1 | DBS | **3** | 3 | Expat 9, digital 9, HIGH branch (essential for medium branch need), low fee, 4.5 rating. Best Singapore local bank for expats needing branch access. |
| b-5 | HSBC | **2** | 0 | Expat 10, digital 9, global expat infrastructure, medium branch. Penalized only by medium fee (low sensitivity makes this minor). |
| b-6 | Standard Chartered | **2** | 0 | Expat 9, digital 8, established SG presence, medium branch. Solid second-tier choice; lower digital than top picks. |
| b-2 | OCBC | **2** | 1 | Expat 8, digital 8, HIGH branch, low fee. Good Singapore local bank; lower expat score vs Citi/HSBC moves it here. |
| b-9 | Wise | **1** | 2 | Expat 10, digital 10, highest rating (4.7), but ZERO physical branches. `branch_need=medium` means a pure digital bank is acceptable but not ideal for an expat doing initial setup. |
| b-10 | Revolut | **1** | 2 | Same profile as Wise; no branches. Slightly lower rating (4.6). |
| b-3 | UOB | **1** | 0 | Expat 8, digital 8, high branch; comparable to OCBC but medium fee. Acceptable if Citi/HSBC full. |
| b-7 | Maybank | **0** | 0 | Expat 6, digital 7 — fails both high-priority criteria. Low fee and high branch are irrelevant when the core priorities aren't met. |
| b-8 | CIMB | **0** | 0 | Expat 6, digital 7 — same issue as Maybank; additionally medium branch. Weakest fit overall. |

**Proposed ideal_order:** `[b-4, b-1, b-5, b-6, b-2, b-9, b-10, b-3, b-7, b-8]`

### Diff vs Engine Fixture
| Change | Current fixture | This proposal | Why it matters |
|--------|----------------|---------------|----------------|
| b-4 moves from #4 to #1 | grade 1 | grade 3 | Engine penalizes medium fee at same weight as expat; with fee_sensitivity=low, Citibank should lead on expat score |
| b-9 (Wise) moves from #2 to #6 | grade 2 | grade 1 | Engine ignores branch_need; Wise has zero branches which fails medium branch need |
| b-10 (Revolut) moves from #3 to #7 | grade 2 | grade 1 | Same as Wise |
| b-5 (HSBC) moves from #6 to #3 | grade 0 | grade 2 | Engine penalizes medium fee equally with low-sensitivity user; HSBC should rank higher |
| b-6 (StanChart) moves from #7 to #4 | grade 0 | grade 2 | Same fee-sensitivity argument |
| b-1 stays #1-#2 | grade 3 | grade 3 | Both agree DBS is top |

> **Romain — edit grades above inline.** The central question for this case: does `branch_need=medium`
> mean Wise/Revolut should be penalized (they have no branches), and does `fee_sensitivity=low` mean
> Citibank/HSBC/StanChart should not be penalized for medium fees?

---

## Case 2 — Insurance SG-SG

### Criteria
```json
{
  "destination_country": "SG",
  "coverage_types": ["health", "travel"],
  "deductible_preference": "medium",
  "family_coverage": true
}
```

### Supplier Attribute Table
Source: `backend/app/recommendations/datasets/insurance.json`

| ID | Name | coverage_types | deductible_options | family | rating | Expat-specialized? | Engine raw |
|----|------|---------------|-------------------|---------|---------|--------------------|---|
| i-1 | AIA Singapore | health,life,travel | low,medium,high | yes | 4.5 | No (local SG) | 98.50 |
| i-2 | Prudential | health,life,travel | low,medium | yes | 4.4 | No (local/regional) | 98.20 |
| i-3 | Allianz Care | health,travel | medium,high | yes | 4.6 | **Yes (global expat)** | 98.80 |
| i-4 | Cigna Global | health,travel | low,medium,high | yes | 4.7 | **Yes (global expat)** | 99.10 |
| i-5 | Bupa Global | health,travel | medium,high | yes | 4.5 | **Yes (global expat)** | 98.50 |
| i-6 | AXA | health,life,travel | low,medium,high | yes | 4.4 | No (general insurer) | 98.20 |
| i-7 | FWD | health,life | low,medium | yes | 4.2 | No | 88.85 |
| i-8 | Manulife | health,life,travel | low,medium,high | yes | 4.5 | No (regional) | 98.50 |
| i-9 | GeoBlue | health,travel | low,medium | yes | 4.6 | **Yes (global expat)** | 98.80 |
| i-10 | Pacific Prime | health,travel | low,medium,high | yes | 4.3 | Broker (not direct) | 97.90 |

Note: i-7 (FWD) misses `travel` coverage — the only hard failure on criteria.

### Independent Grade Proposal

**Grading logic:** Criteria are fully met by 9 of 10 providers.  
The differentiator an independent reviewer applies: **expat-specialized insurers** have global provider
networks and claims experience across borders — critical for someone relocating internationally.
Local/regional insurers (AIA, Prudential, Manulife, AXA) serve SG well but may have gaps in
international coverage continuity.  Pacific Prime is a broker, not a direct insurer.

| ID | Name | Proposed grade | Engine grade | Rationale |
|----|------|:--------------:|:------------:|-----------|
| i-4 | Cigna Global | **3** | 3 | Highest rating (4.7), expat-specialized, full coverage+travel, all deductibles including medium. Globally the leading expat health insurer. |
| i-3 | Allianz Care | **3** | 2 | Expat-specialized, 4.6 rating, health+travel, medium deductible available. Industry-standard for corporate relocations. Engine gives grade 2 only due to marginal rating difference. |
| i-9 | GeoBlue | **2** | 2 | Expat-specialized, 4.6 rating, health+travel, low+medium deductible. Particularly strong for US-connected expats. |
| i-5 | Bupa Global | **2** | 1 | Expat-specialized, 4.5 rating, health+travel, medium deductible available. Engine gives grade 1 only due to tied score at 98.5 with AIA which ranks above due to item_id tie-break. |
| i-1 | AIA Singapore | **2** | 1 | Full coverage+travel, all deductibles, 4.5 rating. Strong local SG brand with wide network in Singapore. Grade 2 not 3 because not expat-specialized for international coverage continuity. |
| i-2 | Prudential | **1** | 0 | Full coverage, 4.4 rating, well-established in SG. Engine gives 0 because of item_id tie-break; an acceptable option. |
| i-8 | Manulife | **1** | 0 | Full coverage, 4.5 rating, all deductibles. Solid but not expat-specialized; same tier as Prudential. |
| i-6 | AXA | **1** | 0 | Full coverage, 4.4 rating, all deductibles. Acceptable general insurer with SG presence. |
| i-10 | Pacific Prime | **1** | 0 | Broker: aggregates policies rather than directly bearing risk. 4.3 rating. Useful for comparison but not a direct insurer. Engine gives 0 due to lowest rating among compliant providers. |
| i-7 | FWD | **0** | 0 | Missing `travel` coverage — fails hard criteria requirement. Both agree. |

**Proposed ideal_order:** `[i-4, i-3, i-9, i-5, i-1, i-2, i-8, i-6, i-10, i-7]`

### Diff vs Engine Fixture
| Change | Current fixture | This proposal | Why it matters |
|--------|----------------|---------------|----------------|
| i-3 (Allianz) grade 2→3 | grade 2 | grade 3 | Allianz is an expat specialist; tied with i-9 at 98.8 raw — engine arbitrarily resolves by item_id |
| i-5 (Bupa) #5→#4, grade 1→2 | grade 1 | grade 2 | Bupa is expat-specialized like Allianz/Cigna; should not be grade 1 |
| i-1 (AIA) #4→#5, grade 1→2 | grade 1 | grade 2 | AIA should be grade 2 (strong local network) not 1; engine's tie-break suppressed it |
| i-8 (Manulife) grade 0→1 | grade 0 | grade 1 | Manulife meets all criteria; engine gives 0 only due to arbitrary tie-breaking |
| i-2 (Prudential) grade 0→1 | grade 0 | grade 1 | Same — meets all criteria |
| i-6 (AXA) grade 0→1 | grade 0 | grade 1 | Same |
| i-10 (Pacific Prime) grade 0→1 | grade 0 | grade 1 | Meets criteria even if a broker; grade 1 is appropriate |
| i-4 and i-7 unchanged | 3 and 0 | 3 and 0 | Both agree on best (Cigna) and worst (FWD) |

> **Romain — edit grades above inline.** Central question: does expat-specialization justify
> distinguishing Cigna/Allianz/Bupa/GeoBlue from AIA/Prudential/Manulife/AXA for a relocation
> product? If yes, the grade 3 tier becomes {i-4, i-3} and grade 2 = {i-9, i-5, i-1}.
> If expat-specialization shouldn't be a criterion (dataset doesn't encode it), then the insurance
> case has fundamental design limitations and grades will remain clustered.

---

## Case 3 — Movers SG-JP

### Criteria
```json
{
  "destination_country": "JP",
  "origin_city": "Singapore",
  "destination_city": "Tokyo",
  "move_type": "international",
  "current_accommodation": {"type": "apartment", "bedrooms": 2, "sqm": 80},
  "people": 2
}
```

**Volume estimate** (from `movers.py::estimate_volume_m3`):  
base(apartment)=25 + (2-1 bedrooms)×8 + (80-60 sqm)/10 + (2-1 people)×3 = **38 m³** → truck class: 40m³

### Supplier Attribute Table
Source: `backend/app/recommendations/datasets/movers.json`

| ID | Name | intl_capable | max_vol_m3 | service_areas (covers Tokyo?) | avg_cost | avail | rating | Engine raw |
|----|------|:------------:|:---------:|-------------------------------|----------|-------|--------|---|
| m-1 | Asian Tigers | **Yes** | 40 | SG, HK, **Tokyo** ✓ | high | medium | 4.7 | 80.00 |
| m-2 | Crown Relocations | **Yes** | 50 | SG, Asia-Pacific | high | high | 4.5 | 81.50 |
| m-3 | Shalom Movers | **No** | 20 | SG only | low | high | 4.3 | 78.08 |
| m-4 | Santa Fe Relocation | **Yes** | 60 | SG, Global | high | **low** | 4.8 | 78.00 |
| m-5 | Leo's Moving | **No** | 12 | SG only | low | high | 4.2 | 76.95 |
| m-6 | Allied Pickfords | **Yes** | 40 | SG, Asia, Europe | medium | medium | 4.4 | 81.50 |
| m-7 | Movers.sg | **No** | 15 | SG only | low | high | 4.1 | 76.68 |
| m-8 | Pacific Relocations | **Yes** | **35** ⚠ | SG, Aus, NZ (**no Japan**) ✗ | medium | medium | 4.6 | 82.50 |
| m-9 | Transworld Relocation | **Yes** | 45 | SG, Asia | high | **low** | 4.5 | 76.50 |
| m-10 | JK Movers | **No** | 20 | SG only | medium | high | 4.4 | 75.58 |

⚠ m-8: max_volume 35 m³ < 38 m³ estimate. Engine's `capacity_fit * 1.1` boost brings it to 100 but the capacity is genuinely insufficient.

### Independent Grade Proposal

**Hard requirements for SG→Tokyo international move:**  
1. `international_capable = True` (SG-only movers cannot serve this move)  
2. `max_volume_m3 ≥ 38` (or very close — engine's 1.1× boost is generous)  
3. Service area covering Japan/Tokyo preferred (strong positive)

**Non-international movers m-3, m-5, m-7, m-10 are grade 0** regardless of other attributes.

| ID | Name | Proposed grade | Engine grade | Rationale |
|----|------|:--------------:|:------------:|-----------|
| m-1 | Asian Tigers | **3** | 1 | **Only mover with Tokyo explicitly in service_areas.** intl-capable, 40m³ (covers 38m³), 4.7 rating. Exactly the corridor. High cost is the only negative; volume and coverage are perfect. |
| m-2 | Crown Relocations | **2** | 2 | intl-capable, 50m³ (ample), high availability (best of international movers), 4.5 rating. Asia-Pacific reach; high cost. Established global network. |
| m-4 | Santa Fe Relocation | **2** | 0 | Global reach, highest capacity (60m³), highest rating (4.8). Penalized for low availability (45-day wait) but remains strong option given premium service level. |
| m-6 | Allied Pickfords | **2** | 2 | intl-capable, 40m³, medium cost (best price among intl movers), Asia+Europe reach. Solid but no specific Japan mention. |
| m-9 | Transworld Relocation | **1** | 0 | intl-capable, 45m³, covers Asia. Doubly penalized: high cost AND low availability (35-day wait). Acceptable as fallback. |
| m-8 | Pacific Relocations | **1** | 3 | intl-capable, 4.6 rating. BUT service_areas = SG+Australia+NZ — **no Japan coverage**. Also max_vol 35m³ < 38m³ estimate. Would require custom Japan routing. Acceptable only if others unavailable. |
| m-3 | Shalom Movers | **0** | 1 | NOT international capable. Cannot execute SG→Tokyo. Low cost irrelevant. |
| m-5 | Leo's Moving | **0** | 0 | NOT international capable AND 12m³ capacity (far below 38m³ estimate). Hard fail. |
| m-7 | Movers.sg | **0** | 0 | NOT international capable. Cannot execute SG→Tokyo. |
| m-10 | JK Movers | **0** | 0 | NOT international capable. Cannot execute SG→Tokyo. |

**Proposed ideal_order:** `[m-1, m-2, m-4, m-6, m-9, m-8, m-3, m-5, m-7, m-10]`

### Diff vs Engine Fixture
| Change | Current fixture | This proposal | Why it matters |
|--------|----------------|---------------|----------------|
| m-8 (Pacific) #1→#6, grade 3→1 | grade 3 | grade 1 | Engine ignores service_areas; Pacific doesn't cover Japan. The most significant single change. |
| m-1 (Asian Tigers) #4→#1, grade 1→3 | grade 1 | grade 3 | Engine ignores that Asian Tigers explicitly covers Tokyo. Biggest underrank. |
| m-4 (Santa Fe) #6→#3, grade 0→2 | grade 0 | grade 2 | Engine penalizes low availability; but global reach+capacity+rating make it grade 2. |
| m-3 (Shalom) #5→#7, grade 1→0 | grade 1 | grade 0 | Not international capable → hard fail for this move type. Engine gives grade 1 because 0.3× penalty still leaves it with a positive score. |
| m-9 (Transworld) #9→#5, grade 0→1 | grade 0 | grade 1 | International-capable with Asian coverage; engine over-penalizes. |

> **Romain — edit grades above inline.** Core questions:  
> (1) Should `service_areas` be a scored field? If Asian Tigers is the only Tokyo specialist, that's a hard data signal.  
> (2) Should `international_capable=False` be a hard exclusion (grade 0) for an international move?  
>     If yes, m-3/m-5/m-7/m-10 must be grade 0.

---

## Summary: Grade Changes Across All 30 Suppliers

| Case | Suppliers regraded | Key direction |
|------|:-----------------:|---------------|
| Banks SG-SG | **5** | Citi/HSBC/StanChart up (fee-sensitivity bug); Wise/Revolut down (branch_need bug) |
| Insurance SG-SG | **7** | Allianz→grade 3; Bupa/AIA→grade 2; Manulife/Prudential/AXA/PacificPrime→grade 1 |
| Movers SG-JP | **5** | Pacific→grade 1; Asian Tigers→grade 3; Santa Fe→grade 2; Shalom→grade 0 |
| **Total** | **17 / 30** | |

---

## Recommended Next Steps

1. **Romain reviews and edits** the grade tables above (change numbers inline).
2. Apply the agreed grades to `golden_rankings.json` (update `relevance` + `ideal_order` for each case).
3. Run `python -m backend.eval.run_ranking_eval --ci` — with an independent gold, the NDCG@k will
   likely be 0.70–0.90 and the gate will now be *challengeable*.
4. To fix the root causes (so the engine can improve toward the gold):
   - Banks: make `fee_sensitivity`, `expat_friendliness_priority`, `digital_priority`, `branch_need`
     affect the scoring weights in `banks.py`.
   - Movers: add `service_areas` to the score function; add a hard zero for
     `international_capable=False` when `move_type=international`.
   - Insurance: no structural fix possible from dataset alone — expat-specialization must be encoded
     as a new field (e.g. `"expat_specialized": true`) in `insurance.json`.
5. Add a 4th golden case covering a domestic move (e.g. movers SG-SG) to test the
   non-international code path where local movers should rank highly.
