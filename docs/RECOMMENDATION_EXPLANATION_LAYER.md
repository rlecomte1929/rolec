# Recommendation Explanation Layer

Explains why each recommended supplier was chosen, with structured metadata for users and admins.

## 1. Explanation schema

```json
{
  "explanation": {
    "match_reasons": ["Within budget", "Near office", "Family-friendly area"],
    "destination_fit": "match",
    "service_fit": "strong",
    "budget_fit": "within",
    "family_fit": "strong",
    "policy_fit": "within",
    "coverage_fit": "adequate",
    "warning_flags": [],
    "explanation_summary": "Matches: Within budget; Near office; Family-friendly area.",
    "score_dimensions": {
      "budget": 92.0,
      "commute": 88.0,
      "service_fit": 85.0,
      "cost": 90.0,
      "rating": 82.0
    }
  }
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `match_reasons` | `string[]` | Top reasons this supplier matches (from pros, budget fit, etc.) |
| `destination_fit` | `string` | `match` \| `mismatch` (based on score_raw > 0) |
| `service_fit` | `string` | `strong` \| `adequate` \| `weak` \| `unknown` |
| `budget_fit` | `string` | `within` \| `partial` \| `above_budget` \| `unknown` |
| `family_fit` | `string` | `strong` \| `adequate` \| `weak` \| `unknown` |
| `policy_fit` | `string` | `within` \| `near_limit` \| `above_policy` \| `unknown` |
| `coverage_fit` | `string` | `strong` \| `adequate` \| `weak` \| `unknown` |
| `warning_flags` | `string[]` | `above_budget`, `above_policy`, `low_availability`, `wrong_destination`, `waitlist` |
| `explanation_summary` | `string` | Short human-readable summary |
| `score_dimensions` | `Record<string, number>` | Normalized breakdown (dimension → score 0–100) |

---

## 2. Files changed

| Path | Change |
|------|--------|
| `backend/app/recommendations/types.py` | Added `RecommendationExplanation`, `explanation` on `RecommendationItem` |
| `backend/app/recommendations/explanation.py` | **New** – `build_explanation()` |
| `backend/app/recommendations/engine.py` | Integrated `build_explanation()` into `recommend()` |
| `frontend/src/features/recommendations/types.ts` | Added `RecommendationExplanation`, `explanation` on `RecommendationItem` |
| `frontend/src/features/recommendations/RecommendationResults.tsx` | Display match_reasons, warning_flags, explanation_summary, scoring details toggle |
| `frontend/src/pages/services/ServicesRecommendations.tsx` | Added `?debug=1` support for admin view |

---

## 3. Backend scoring / explanation changes

- **Engine** (`engine.py`): For each top-ranked item, calls `build_explanation(item, scored_result, criteria, category)` and attaches the result to `RecommendationItem.explanation`.
- **Explanation builder** (`explanation.py`):
  - Derives fit dimensions from plugin `breakdown`, `pros`, `cons`, `metadata`.
  - Uses `_policy_cap_*` in criteria (from `criteria_builder`) vs `metadata.estimated_cost_*` for `policy_fit`.
  - Maps cons to `warning_flags` (above_budget, above_policy, low_availability, wrong_destination, waitlist).
  - Builds `explanation_summary` from match_reasons and warning_flags.
- **Plugins**: No changes; explanation is built from existing `score()` output.

---

## 4. Frontend rendering changes

- **RecCard**:
  - Primary text: `explanation_summary` (fallback: `item.summary`).
  - Match badges: `match_reasons` (fallback: `pros`), max 5.
  - Warning badges: `warning_flags` with amber styling.
  - Expanded: rationale, "Show scoring details" toggle → `score_dimensions` / `breakdown`.
- **Debug mode**: `?debug=1` in URL → first card’s scoring details shown by default.

---

## 5. Example API output

```json
{
  "category": "living_areas",
  "generated_at": "2025-03-04T12:00:00Z",
  "criteria_echo": {
    "destination_city": "Oslo",
    "destination_country": "NO",
    "budget_min": 2000,
    "budget_max": 4000,
    "office_address": "Sentrum, Oslo, Norway"
  },
  "recommendations": [
    {
      "item_id": "oslo-frogner-001",
      "name": "Frogner area",
      "score": 87.5,
      "tier": "best_match",
      "summary": "Family-friendly area with good schools.",
      "rationale": "Frogner matches your budget and office commute preferences.",
      "breakdown": {"budget": 92, "commute": 88, "service_fit": 85},
      "pros": ["Within budget", "Near office", "Family-friendly"],
      "cons": [],
      "metadata": {"availability_level": "high", "estimated_cost_usd": 3200},
      "explanation": {
        "match_reasons": ["Within budget", "Near office", "Family-friendly"],
        "destination_fit": "match",
        "service_fit": "strong",
        "budget_fit": "within",
        "family_fit": "strong",
        "policy_fit": "unknown",
        "coverage_fit": "unknown",
        "warning_flags": [],
        "explanation_summary": "Matches: Within budget; Near office; Family-friendly.",
        "score_dimensions": {"budget": 92.0, "commute": 88.0, "service_fit": 85.0}
      }
    }
  ]
}
```

---

## 6. Verification steps

1. **Backend**
   - Run recommendation flow: `POST /api/recommendations/batch` or `POST /api/recommendations/{category}`.
   - Confirm each `recommendations[].explanation` is present and non-null.
   - Confirm `match_reasons`, `warning_flags`, `explanation_summary` and `score_dimensions` are populated as expected.

2. **Frontend**
   - Open Services → Questions → answer and run recommendations.
   - Open `/services/recommendations` and verify:
     - Match reasons appear as badges.
     - Warning flags show for above-budget / above-policy / low-availability items.
     - Expand "Why this?" and use "Show scoring details" to see dimensions.

3. **Admin / debug**
   - Visit `/services/recommendations?debug=1`.
   - Confirm the first recommendation has scoring details expanded by default.

---

## 7. Deferred items

- **match_score**: Reuse existing `score` (0–100); no separate `match_score` field.
- **API debug param**: Backend always returns full explanation; `?debug=1` is frontend-only for auto-expanding scoring.
- **Policy fit refinement**: Currently uses `_policy_cap_monthly`, `_policy_cap_annual`, `_policy_cap_one_time` from criteria; may need expansion for more policy types.
- **Localization**: `explanation_summary` and `match_reasons` are in English; i18n deferred.
