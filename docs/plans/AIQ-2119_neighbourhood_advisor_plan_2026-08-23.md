# AIQ-2119 — plan: the advisor exists; its commute score is inert

**The card asks to BUILD a neighbourhood advisor. It is already built.** The useful work is
one defect that makes its headline feature do nothing.

---

## 1. Dependency check — every claim on the card is true

Rare, and worth saying: all five stated dependencies are real.

| card claim | verified |
|---|---|
| `backend/agents/recommendation_engine.py` | exists |
| Dublin neighbourhoods dataset (AIQ-1882) | `datasets/living_areas.json` — 46 areas, **8 in Dublin** |
| geocoder (AIQ-1607) | `recommendations/geo.py`, `routers/geocoding.py`, `services/geocoding_service.py` |
| `cases.commute_preference` | present in `db/cases.py`, `schemas.py`, `routers/cases_write.py` |
| `recommendation_slates` | `recommendations/router.py`, `weight_learner.py` |

## 2. What already exists

`backend/app/recommendations/plugins/living_areas.py` — `LivingAreasPlugin` — already:

- accepts `office_lat` / `office_lng` on its criteria model, with the comment *"commute is
  computed for real instead of read from a static estimate"*
- carries weighted scoring (`commute` weight 0.25, plus budget / space / lifestyle / rating /
  availability)
- returns `summary`, `rationale`, `pros`, `cons`, `breakdown`
- refuses a wrong-city item (`"Area is in X, not Y"`) and a data-less item (`"No housing data"`)
- is wired into `recommendations/router.py`, gated on destination, with school-age interplay
  from AIQ-1550
- `criteria_builder.py` already lifts `office_address` out of the case context

Run against the card's own scenario (Grand Canal Dock office, transit, 40-min max):

```
   88.70  Rathmines                  EUR 2850/mo, ~9 min commute
   88.50  Dun Laoghaire              EUR 2609/mo, ~30 min commute
   88.44  Stoneybatter / Smithfield  EUR 2444/mo, ~12 min commute
   88.44  Grand Canal Dock           EUR 2609/mo, ~0 min commute
   88.25  Drumcondra                 EUR 2444/mo, ~12 min commute
```

So four of the five Validation Criteria are already met: ≥5 Dublin areas, per-area rationale with
commute and rent (the dataset even carries `rent_basis`, a real sourcing string naming the Daft.ie
report and admitting where a figure is Dublin-wide rather than area-specific), and the order does
change when the office moves.

## 3. The defect — commute does not actually rank

Look at the list again. The office is **in** Grand Canal Dock, and Grand Canal Dock ranks
**fourth**, below Dun Laoghaire — 0 minutes losing to 30.

The breakdown says why:

| area | commute mins | **commute score** | space | lifestyle |
|---|---:|---:|---:|---:|
| Grand Canal Dock | 0 | **100.0** | 84.6 | 85 |
| Dun Laoghaire | 30 | **100.0** | 100.0 | 70 |
| Rathmines | 9 | **100.0** | 92.3 | 79 |

`commute` is scored as a **pass/fail against `max_minutes`**, not as a gradient. Every area inside
the 40-minute limit scores a flat 100, so the component contributes exactly zero differentiation in
the ordinary case, and the ranking is decided by `space`, `lifestyle` and `rating` instead.

The whole spread across the eight areas is **1.35 points** (88.70 → 87.35). The advisor looks like
it is ranking by commute and is not.

**Validation Criterion 3 passes for the wrong reason.** The order does change when the office
moves — but only because `max_minutes` starts excluding distant areas, not because near ones win.
A test asserting merely "the order changed" would go green over this defect, which is why the fix
needs the stricter assertion below.

## 4. Proposed change

Small and contained — `living_areas.py`, the commute component only.

**Score commute as a decreasing function of minutes**, not a threshold:
- 100 at 0 minutes, tapering to 0 at `max_minutes`, and 0 beyond it
- keep the existing hard exclusion above `max_minutes` — a gradient must not readmit a
  commute the employee said was too long

Nothing else changes: no new endpoint, no new dataset, no router registration, no migration. The
card's "BUILD an endpoint" and "Register routers per the both-router rule" are already satisfied
and should be struck from its scope.

## 5. Tests

The discriminating one, which fails today:

```
an area 0 minutes from the office must outrank an otherwise-comparable area 30 minutes away
```

Plus:
- commute sub-scores must **differ** between a 0-minute and a 30-minute area (today both are 100)
- an area beyond `max_minutes` stays excluded (guards against the gradient readmitting it)
- the top-ranked area must change when the office moves across the city — stricter than "the list
  changed"
- empty state: with no office address the response asks for one and does not return a silent `[]`
  (Validation Criterion 5 — **not yet verified**, see below)

## 6. Not yet verified

**Criterion 5 (the empty state).** I exercised `score()` directly, not the HTTP path, so I have not
confirmed what the endpoint returns when no office address is set. `DESTINATION_REQUIRING` in
`router.py` gates `living_areas` on a destination, but that is not the same check. Verify against
the real endpoint before closing the card.

## 7. Recommendation

Rewrite the card. It is not an AI/ML build (there is no LLM here, and there must not be — the
serving path is covered by `check_serving_llm_isolation.py`); it is a scoring bug fix in an
existing deterministic plugin. Retitle to something like *"Neighbourhood advisor ranks by
everything except commute"*, keep Validation Criteria 1–2 as regression checks, replace 3 with the
stricter assertion above, and keep 5.

Estimated change: ~10 lines plus tests.
