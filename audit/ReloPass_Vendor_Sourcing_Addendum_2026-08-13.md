# Addendum A — Vendor Sourcing Sides & HR Catchment Override
**Companion to** `ReloPass_Data_Integration_Audit_2026-08-13.md` · **Date:** 2026-08-13 · **Status:** spec, ready for implementation
**Resolves:** F-1 (geo leak), F-2 (invalid HR approvals), F-3 (country never filtered) — and adds the border-case capability that none of those fixes alone would give you.

---

## A.0 Why this addendum exists

The audit's fix for F-1 was "filter candidates by destination." That is wrong for movers, and the code already half-knows it.

`criteria_builder.py:249` deliberately prefills origin for movers:

```python
# Prefill origin from case for movers
if svc_key == "movers" and not criteria.get("origin_city") and origin_city:
    criteria["origin_city"] = origin_city
```

`MoversPlugin.CriteriaModel` declares `origin_city: str = ""`. And then nothing consumes it — `_service_area_score(c.destination_city, ...)` scores destination only, and `search_by_service_destination()` (`supplier_registry.py:286`) has **no origin parameter at all**, for any category.

So origin is collected, threaded through the criteria builder, and discarded at the matching layer. Someone understood the domain and the wiring was never finished. This addendum finishes it.

---

## A.1 The domain rule

An international household-goods move is contracted **once**, from the **origin agent**:

1. The pre-move survey happens in the employee's home — origin.
2. The origin agent packs, loads, and clears export customs — origin.
3. The origin agent subcontracts the destination agent through their network (FIDI FAIM, IAM, OMNI — all three already listed in `supplier_service_categories.accrediting_bodies` for `movers`).
4. The quote is door-to-door and the invoice is issued by the origin agent.

An RFQ for movers therefore goes to **movers based in the origin country who can reach the destination**. Origin presence alone is not enough: a Paris mover with no Nordic network cannot quote Paris→Oslo.

**This is a movers-specific rule, not a global one.** Most categories are destination-sourced. Two are genuinely both.

---

## A.2 Sourcing side — canonical mapping for all 11 categories

Values: `origin` · `destination` · `both` · `either`

| code | display_name | `sourcing_side` | rationale |
|---|---|---|---|
| `movers` | Household Goods / Moving | **`origin`** | Survey, pack, load, export customs all origin-side; origin agent subcontracts destination through FIDI/IAM/OMNI. **Requires destination reach.** |
| `tax_finance` | Tax Advisory & Shadow Payroll | **`both`** | Exit-tax/de-registration at origin *and* arrival tax/shadow payroll at destination are genuinely two engagements. `compliance_critical = true` — do not collapse to one side. |
| `rmc` | Relocation Management Company | **`either`** | Global account, contracted wherever the mobility budget sits. |
| `healthcare_ipmi` | Healthcare & International Insurance | **`either`** | IPMI policies are portable by design; the underwriter's domicile is not the employee's. |
| `dsp` | Destination Service Provider | `destination` | The name is the spec. |
| `housing_agencies` | Housing & Temporary Accommodation | `destination` | Nothing to let until they arrive. |
| `schools` | School Search & Education | `destination` | |
| `banks` | Banking & Account Opening | `destination` | Account is opened in the destination jurisdiction. |
| `legal_admin` | Immigration / Legal Counsel | `destination` | The destination jurisdiction's rules govern the permit. `compliance_critical = true`. *Open question for counsel: whether origin-side exit formalities (e.g. FR de-registration) justify `both` — spec'd as `destination` until someone qualified says otherwise.* |
| `language_cultural` | Language & Cultural Training | `destination` | Target language is the destination's, even when delivered pre-departure and remotely. |
| `partner_family` | Partner & Family Support | `destination` | Spousal career support is destination-labour-market work. |

**Storage and pets** are not yet in `supplier_service_categories` but exist as recommendation plugins. When promoted, both are **`origin`** (storage-in-transit and pet export both start origin-side).

Home for this column: `public.supplier_service_categories` — it already exists as the reference taxonomy (11 rows) and already carries `is_live` and `compliance_critical` policy flags. One column, one source of truth.

---

## A.3 The structural blocker

`company_vendor_selections` today is:

```
(company_id, category, destination_city, country, master_item_id, custom_item_json,
 selected, display_order, created_at, updated_at, created_by_user_id)
```

**There is no origin column and no corridor.** For your 176 FR→NO cases, `country='NO'` means *destination*.

So HR cannot currently express "these are my approved French movers for outbound-France moves." The base case you described is **not representable in the schema.** Everything below follows from fixing that.

Confirming the shape — 6,301 of 6,335 rows (99.5%) are `destination_city NULL / country set`, and `list_curation()` filters on neither:

```python
sql = ("SELECT * FROM company_vendor_selections "
       "WHERE company_id = :co AND category = :cat "     # ← country absent
       "ORDER BY display_order ASC, created_at ASC")
...
return [r for r in rows
        if not r.get("destination_city") or _canon_city(r.get("destination_city")) == want]
```

---

## A.4 Supply reality check — read this before scheduling

Flipping movers to origin-sourcing **today** returns zero movers for FR→NO:

| origin country | movers capabilities | `platform_vetting_status = 'approved'` |
|---|---|---|
| **FR** | 4 | **0** |
| **DE** | 11 | **0** |
| NO | 6 | 2 |
| SG | 10 | 10 |

France and Germany have real mover capability rows in the registry. All 15 are unvetted, and `search_by_service_destination` hard-filters `platform_vetting_status == 'approved'`, so all 15 are invisible to employees.

**Vetting those 15 rows is a hard prerequisite, not a follow-up.** Ship the sourcing logic without it and FR→NO movers goes from "wrong vendors" to "no vendors" — which is more honest but not better. Sequenced as Phase 0 below.

---

## A.5 Schema changes

Three changes. All additive; no drops. Every new table gets RLS + policy + `REVOKE ALL FROM anon` per the `CLAUDE.md` hard gate.

### A.5.1 `supplier_service_categories.sourcing_side`

```sql
ALTER TABLE public.supplier_service_categories
  ADD COLUMN IF NOT EXISTS sourcing_side text NOT NULL DEFAULT 'destination'
    CHECK (sourcing_side IN ('origin','destination','both','either'));

UPDATE public.supplier_service_categories SET sourcing_side = 'origin' WHERE code = 'movers';
UPDATE public.supplier_service_categories SET sourcing_side = 'both'   WHERE code = 'tax_finance';
UPDATE public.supplier_service_categories SET sourcing_side = 'either' WHERE code IN ('rmc','healthcare_ipmi');
-- all others keep the 'destination' default
```

`DEFAULT 'destination'` is deliberate: a new category added without thought behaves like the majority, and the only categories that deviate are the ones someone explicitly reasoned about.

### A.5.2 `company_vendor_selections` — origin + provenance

```sql
ALTER TABLE public.company_vendor_selections
  ADD COLUMN IF NOT EXISTS origin_country char(2),
  ADD COLUMN IF NOT EXISTS selection_basis text NOT NULL DEFAULT 'in_catchment'
    CHECK (selection_basis IN ('in_catchment','hr_extended')),
  ADD COLUMN IF NOT EXISTS extension_reason text,
  ADD COLUMN IF NOT EXISTS extended_by_user_id uuid;

-- An extension must be justified and attributed. This is the whole point of the flag.
ALTER TABLE public.company_vendor_selections
  ADD CONSTRAINT cvs_extension_requires_reason CHECK (
    selection_basis = 'in_catchment'
    OR (extension_reason IS NOT NULL AND length(trim(extension_reason)) >= 10
        AND extended_by_user_id IS NOT NULL)
  );
```

`country` keeps its current meaning (**destination**) — do not repurpose it, that would silently reinterpret 6,301 live rows. `origin_country` is new and nullable; NULL means "not origin-scoped", which is correct for every destination-sourced category.

### A.5.3 `company_vendor_catchment` — HR's per-corridor policy

```sql
CREATE TABLE IF NOT EXISTS public.company_vendor_catchment (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id                  uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  category                    text NOT NULL,
  origin_country              char(2),
  destination_country         char(2),
  extra_origin_countries      text[] NOT NULL DEFAULT '{}',
  extra_destination_countries text[] NOT NULL DEFAULT '{}',
  reason                      text NOT NULL,
  created_by_user_id          uuid NOT NULL,
  created_at                  timestamptz NOT NULL DEFAULT now(),
  updated_at                  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, category, origin_country, destination_country)
);
ALTER TABLE public.company_vendor_catchment ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_vendor_catchment FROM anon;
-- policies: tenant-scoped on company_id, mirroring company_vendor_selections
```

### A.5.4 `country_adjacency` — the default border expansion

```sql
CREATE TABLE IF NOT EXISTS public.country_adjacency (
  country_a        char(2) NOT NULL,
  country_b        char(2) NOT NULL,
  relation         text NOT NULL DEFAULT 'land_border'
    CHECK (relation IN ('land_border','short_sea','schengen_metro')),
  -- DECIDED 2026-08-13: neighbours are in the DEFAULT catchment for origin-sourced
  -- categories. This column is the carve-out for pairs that are geographically
  -- adjacent but not operationally equivalent — see the seeding rule below.
  default_included boolean NOT NULL DEFAULT true,
  PRIMARY KEY (country_a, country_b)
);
```

Symmetric rows both ways. ~80 rows covers EEA + UK + CH. `schengen_metro` is for pairs that are functionally adjacent without a shared border in the relevant place (Øresund DK↔SE).

**Seeding rule for `default_included`:**

| pair type | `default_included` | why |
|---|---|---|
| `land_border`, both countries in the same customs/regulatory bloc (EU/EEA/CH) | `true` | A German mover doing a Strasbourg pickup is routine single-market work |
| `short_sea` (UK↔FR, IE↔UK, DK↔SE) | **`false`** | Adjacent on a map, a ferry booking in practice. One-click HR extension instead |
| `land_border` across a bloc edge (ES↔MA, PL↔UA, FI↔RU, IN↔PK…) | **`false`** | Different customs and regulatory reality; some are politically fraught. Never a silent default |

One boolean, seeded explicitly, reviewable in a diff. No clever runtime logic inferring blocs — the seed data *is* the policy.

---

## A.6 Catchment resolution algorithm

One function, called by both the recommendation engine and the HR curation view, so they cannot disagree:

```python
def resolve_catchment(category, origin_country, destination_country, company_id) -> Catchment:
    """
    Returns the set of countries a vendor may be based in to be eligible for this
    (category, corridor). Single source of truth — the engine and the HR curation
    screen MUST both call this, or F-3 reappears in a new shape.
    """
    side = sourcing_side(category)          # supplier_service_categories.sourcing_side

    base: set[str] = set()
    if side in ("origin", "both"):        base.add(origin_country)
    if side in ("destination", "both"):   base.add(destination_country)
    if side == "either":                  base |= {origin_country, destination_country}

    # DECIDED 2026-08-13: neighbours are IN the default catchment, not an opt-in.
    # Strasbourg/Kehl works with zero HR action. Origin-sourced only — a neighbouring-
    # country *mover* is plausible; a neighbouring-country *bank* or *school* is not
    # (you do not open a German account for an Oslo move).
    #
    # Two filters keep the default from becoming noise:
    #   1. default_included — excludes short-sea and cross-bloc pairs (§A.5.4)
    #   2. has_eligible_vendors — a neighbour with zero vendors that can reach the
    #      destination adds nothing but a chip. Never surface an empty country.
    if side in ("origin", "both") and policy.include_neighbours:      # default True
        for nb in neighbours_of(origin_country, default_included=True):
            if has_eligible_vendors(nb, category, destination_country):
                base.add(nb)

    # HR's explicit widening — now genuinely exceptional: NON-adjacent countries,
    # short-sea pairs, and cross-bloc neighbours. Requires a reason_code.
    ext = catchment_override(company_id, category, origin_country, destination_country)
    return Catchment(
        base=base,
        extended=set(ext.extra_origin_countries) | set(ext.extra_destination_countries),
        all=base | extended,
    )
```

**What the default-on decision changes downstream.** A neighbour-country vendor is now `in_catchment`, not `hr_extended` — so it needs no reason code and no HR action. `hr_extended` narrows to what it should always have meant: *"beyond the default catchment."* That makes the flag a stronger signal, not a weaker one — every `hr_extended` row is now genuinely a deliberate exception rather than routine border admin.

HR retains the opposite lever: `include_neighbours = false` on the tier-2 policy restricts to origin-country only, for a company that wants it.

**Eligibility for a vendor is then:**

```
vendor.based_in ∈ catchment.all
  AND (side != 'origin' OR vendor_reaches(destination_country))
```

### Destination reach for origin-sourced categories

Origin presence is necessary, not sufficient. Reach is satisfied by **any** of:

1. `supplier_service_capabilities.coverage_scope_type = 'global'`, or
2. a `supplier_service_area_coverage` row for this supplier + category with `area_id` = destination ISO2 or a region containing it, or
3. an accreditation in `supplier_accreditations` from a network with global reciprocity (`FIDI FAIM`, `IAM`, `OMNI`) with `status = 'verified'`.

Rule 3 is the pragmatic one — it is exactly what those accreditations *mean*, `supplier_accreditations` already exists with 27 rows, and its `CHECK` constraint already guarantees a verified row carries `evidence_url + verified_at`. It saves you hand-maintaining a reach matrix for every FIDI member.

**Delete `_service_area_score`'s role as a filter proxy.** Once reach is a hard predicate, the function reverts to what a score should be: ranking among already-eligible vendors. Its Asia-only regional tier bug (`"Europe"` → 20, `"Asia-Pacific"` → 75) becomes a ranking nuisance rather than a correctness bug, and should still be fixed by making the tiers continent-complete.

---

## A.7 HR experience

**Default state.** HR opens vendor curation for a corridor and sees vendors already scoped to the resolved catchment: for FR→NO movers, French movers with Nordic reach, plus movers from France's land-neighbours (BE, DE, ES, IT, LU, CH, AD, MC) as an expandable secondary group.

**The border case.** HR clicks *"Extend catchment"*, picks additional countries, and types a reason — *"Employees based in Strasbourg; Kehl movers are 5 km away and cheaper."* That writes a `company_vendor_catchment` row. Vendors approved as a result carry `selection_basis = 'hr_extended'` with the reason attached.

**Why the reason field is load-bearing.** It is not bureaucracy — it is the only thing that lets the eval suite distinguish a deliberate border approval from a data leak. Without it, the escape hatch simply relabels F-2 and the harness goes quiet. See A.9.

**Copy.** Route the strings through the `ux-copy` skill before shipping; the empty state for a category with an empty catchment matters more than the happy path. Current `hr_pending` copy — *"Your HR is finalizing providers for {category}"* — is right for the employee side and should be reused, not reinvented.

---

## A.8 Migration of the 6,335 existing rows

Backfill, do not guess:

| rows | current shape | action |
|---|---|---|
| ~6,301 | `country` set, `destination_city` NULL, destination-sourced category | `origin_country = NULL`, `selection_basis = 'in_catchment'`. Correct as-is. |
| all `movers` rows | `country` = destination | **Cannot be auto-migrated** — origin was never captured. Set `origin_country = NULL` and `selected = false`, then require HR re-confirmation. |
| **325** | selection country ≠ item country (incl. 177 companies approving a Sydney mover for Norway) | `DELETE`. These are seeding defects, not decisions. Log the deletion. |
| **14** | orphan `company_id` | `DELETE`. |
| 2 | custom vendors | `selection_basis = 'in_catchment'`, manual review. |

The movers decision is the uncomfortable one. Auto-migrating `country='NO'` to `origin_country='NO'` would assert that every company's approved movers are Norwegian, which is false and unrecoverable once written. Deactivating and asking HR to re-confirm is honest, and given the evidence that these were auto-select-all at signup (avg 19.4 rows/company, max 24, 320 companies, 17 days) rather than deliberate choices, you are not discarding real decisions.

---

## A.9 Revised evals

### Changed — C1 must stop failing legitimate border approvals

Current C1 fails any row where selection country ≠ item country. Under this spec that would flag every intentional Strasbourg approval. New logic:

```python
def c1_curation_geo_validity(row) -> Verdict:
    catchment = resolve_catchment(row.category, row.origin_country,
                                  row.country, row.company_id)
    vendor_country = item_country(row.master_item_id)

    if vendor_country in catchment.base:
        return PASS                                  # in the default catchment
    if (vendor_country in catchment.extended
            and row.selection_basis == 'hr_extended'
            and row.extension_reason):
        return PASS                                  # deliberate, justified, attributed
    return FAIL                                      # leak
```

A vendor outside the catchment that is *not* flagged as an extension still fails — which is exactly the Sydney-mover case, and it stays failing.

### New — C5: extensions are justified and attributed

Every `selection_basis = 'hr_extended'` row has `extension_reason` ≥ 10 chars and a non-null `extended_by_user_id`. Enforced by the DB constraint in A.5.2; the eval catches rows that predate it or arrive by direct SQL.

### New — C6: extension plausibility (the anti-rubber-stamp guard)

**This is the eval that stops the escape hatch becoming the new bug.** An extension is plausible when the extended country is in `country_adjacency` with the base country, *or* the vendor holds a verified global-network accreditation. `hr_extended` rows failing both are reported as **warnings requiring human review**, not hard failures — HR may have a real reason the adjacency table does not model, and a false failure here trains people to ignore the suite.

Without C6, relabelling the 177 Sydney-for-Norway rows as `hr_extended` with the reason "approved by HR" would make C1 green while the product stayed broken. C6 catches AU↛NO as non-adjacent and surfaces it.

### New — C7: sourcing side is applied

For each category, the vendors appearing in served slates are based in the resolved catchment for that corridor's sourcing side. Directly asserts A.2. **Baseline: fails for movers on FR→NO** (currently sourced from destination + Singapore static data).

### New — D6: RFQ recipients respect sourcing side

Every `rfq_recipients.vendor_id` on an origin-sourced item resolves to a supplier based in the origin catchment. Closes the loop — a vendor could pass the slate filter and still be dispatched wrongly through a stale shortlist.

### Amended — B1

Slate geo-precision must resolve against `resolve_catchment(...)`, not against `dest_country` alone. Otherwise the corrected origin-sourced movers behaviour reads as a B1 regression on day one.

### Unchanged

A1–A3, B3, C2–C4, D1–D5, E1–E2, F1–F5.

**Revised baseline: 8 of 25.** Three of the four new evals fail at introduction, which is correct — they are describing behaviour that does not exist yet.

---

## A.10 Plan

| phase | work | gate |
|---|---|---|
| **P0 — Unblock supply** *(prerequisite)* | Vet the 15 FR/DE mover capability rows: set `platform_vetting_status='approved'`, `vetted_by`, `vetted_at`. Add `supplier_service_area_coverage` or accreditation rows proving destination reach. | ≥3 FR-based movers with verified NO reach. **Without this, P2 ships an empty list.** |
| **P1 — Taxonomy** | `sourcing_side` column + values. `country_adjacency` seeded for EEA+UK+CH **with `default_included` set per the §A.5.4 rule**. Both read-only additions. | A2 mapping matches this doc; adjacency symmetric; `default_included` false for every short-sea and cross-bloc pair; no behaviour change yet |
| **P2 — Resolution** | `resolve_catchment()`; `search_by_service_destination` → `search_by_service_corridor(origin, destination)`; hard destination-reach predicate; hard geo gate in `_load_dataset_with_registry`. | C7, B1 pass for FR→NO, DE→FR, IN→DE |
| **P3 — Curation schema** | `company_vendor_selections` columns + constraint; `company_vendor_catchment`; backfill and deletions per A.8; `list_curation()` calls `resolve_catchment()`. | C1, C2, C5 pass; 325 + 14 rows gone; movers rows deactivated |
| **P4 — HR UI** | Catchment display, "Extend catchment" flow with mandatory reason, extension badges on approved vendors. | C6 clean or warnings triaged; `tsc --noEmit` clean |
| **P5 — RFQ** | RFQ creation validates recipients against the catchment; `was_recommended` + `recommendation_snapshot` written. | D6, D5 pass |

**Sequencing note.** P1 and P2 are safe to run in parallel with P0 as long as nothing ships to prod until P0 lands — the code can be correct while the data is still thin.

---

## A.11 Metrics

| metric | definition | now | target |
|---|---|---|---|
| **Sourcing-Side Compliance** | slate items based in the resolved catchment ÷ total, per category | movers FR→NO: **0%** | 100% |
| **Origin Supply Depth** | origin countries with ≥3 approved movers holding destination reach | **0** | ≥3 for every live corridor |
| **Catchment Extension Rate** | `hr_extended` selections ÷ total | n/a | **2–8%** — *see note* |
| **Neighbour Contribution** | selected vendors from a default-included neighbour ÷ total selected | n/a | monitor; no target |
| **Extension Plausibility** | `hr_extended` rows passing C6 ÷ total extended | n/a | ≥95% |
| **Curation Geo-Validity** (revised) | selections passing revised C1 ÷ total | 39.7% (movers) | 100% |
| **HR Curation Engagement** | companies with ≥1 deliberate toggle (not signup default) ÷ total | ~0% | >50% |

**On the extension rate.** The band drops from 5–15% to **2–8%** because neighbours are now default-included — the common border case no longer counts as an extension. A health band, not a target. **Above ~15% means the default catchment is too narrow** and `country_adjacency.default_included` needs widening rather than every HR team working around it. Near 0% is now *expected and fine* — it means the defaults are doing their job.

**Neighbour Contribution** is the replacement signal for "is the border case being served." If it sits at 0% across companies with border-adjacent employees, the default is not actually surfacing neighbour vendors and something upstream (vetting, reach evidence, `has_eligible_vendors`) is filtering them out.

---

## A.12 Validation process

1. **Unit** — `resolve_catchment()` table-driven across all 11 categories × {origin, destination, both, either} × {adjacent, non-adjacent, extended, not-extended}. Pure function, no DB; this is where the sourcing logic is actually proven.
2. **Integration** — `pytest` against the FR→NO fixture. Mount `backend.main:app` and import auth deps from `backend.app.auth_deps` (per `CLAUDE.md` — the second `get_current_user` in `backend/main.py` makes `dependency_overrides` silently no-op otherwise; that bug sank AIQ-567's tests).
3. **Eval harness** — `evals/relopass_integration_evals.py --baseline evals/evals_baseline.json` against a staging clone. Regressions block.
4. **Manual, one corridor** — HR curates FR→NO movers, extends to DE with a reason, employee sees French + German movers and no Singaporeans, RFQ dispatches to a French mover.
5. **Prod canary** — 24h read-only watch on Sourcing-Side Compliance across all live corridors before widening.

---

## A.13 Open questions for a human

1. **`legal_admin` — `destination` or `both`?** Spec'd `destination`. If origin-side exit formalities are material for any live corridor, it is `both`. `compliance_critical = true`, so this needs a qualified opinion rather than a default.
2. ~~**Adjacency semantics for `short_sea`.**~~ **RESOLVED 2026-08-13.** With neighbours default-included, the bar for the default rose: `short_sea` pairs (UK↔FR, IE↔UK, DK↔SE) are **excluded** via `default_included = false` and offered as a one-click HR extension. Adjacent on a map, a ferry booking in practice.
3. **Does any current customer contract movers at destination?** Some corporates do when the destination entity holds the budget. If yes, `movers` may need `origin` as a *default* with a per-company override rather than a fixed taxonomy value. Worth one question to a pilot HR team before P1 hardens the column.
4. **The 15 unvetted FR/DE movers** — who vets them, against what criteria, by when? P0 blocks everything and has no owner in this document.
