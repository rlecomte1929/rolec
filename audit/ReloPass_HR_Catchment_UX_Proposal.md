# Proposal — HR Vendor Catchment: "Where should these vendors come from?"
**Companion to** Addendum A · **Date:** 2026-08-13 · **Status:** design proposal, pre-implementation

This proposal refines Addendum A §A.7 into something concrete enough to build. It changes three things from the addendum, all in the direction of less work for HR: a **three-tier cascade** so the choice is made once rather than per corridor, **structured reason codes** instead of free text, and **vendor counts on every country chip** so nobody walks into an empty list.

---

## 1. The design principle

**HR should never have to learn the word "sourcing side."**

That is our taxonomy, not their mental model. An HR manager opens this screen thinking *"who can move Amélie from Paris to Oslo?"* — not *"is this category origin-anchored or destination-anchored?"*

So the UI **explains the default rather than asking HR to choose it**:

> ℹ️ **Movers are sourced from France** — the country your employees are moving from.
> International moves are quoted by the origin agent, who surveys and packs at origin and arranges delivery through their destination network.

Then it offers exactly one lever: *add neighbouring countries*. That is the flexibility you asked for, and it is the only degree of freedom HR actually needs. Everything else is derived.

The corollary matters as much: **for destination-sourced categories (housing, schools, banks), the neighbour control does not appear at all.** Nobody opens a German bank account for an Oslo move. Offering the option would be a bug in the UX, not flexibility.

---

## 2. Three-tier cascade — set it once

Addendum A scoped the catchment per corridor. That is wrong at scale: 10 categories × N corridors is a lot of identical decisions, and a company with border-based employees will make the same choice every time.

| tier | scope | who sets it | example |
|---|---|---|---|
| **3 — Corridor override** | (company, category, origin→destination) | HR, on this screen | *"For FR→NO movers only, also allow Germany"* |
| **2 — Company policy** | (company, category) | HR, via "Apply to all routes" | *"For movers, always include neighbouring countries"* |
| **1 — System default** | (category) | ReloPass | **Origin country + land neighbours that have eligible vendors**, for origin-sourced categories; destination only otherwise |

> **DECIDED 2026-08-13 — `include_neighbours` defaults to `true` for movers.** Neighbours are in the base catchment, not an opt-in. Strasbourg works with zero HR action. Two guards keep it from becoming noise: `country_adjacency.default_included` excludes short-sea and cross-bloc pairs, and a neighbour with **zero eligible vendors never renders**. HR keeps the opposite lever — switching neighbours off restricts to origin-country only.

Resolution is most-specific-wins: **corridor override → company policy → system default.** The same cascade shape as `policy_configs`, so it will feel familiar to anyone who has worked in this codebase.

In the UI this is one checkbox under the country chips:

> ☐ Apply to all routes for Movers

Tick it once and the choice propagates to every corridor the company runs. That single checkbox is the difference between a feature HR uses and a feature HR abandons after the second corridor.

With neighbours default-on, tier 2 now serves the **opt-out** case as much as the opt-in: a company that wants France-only movers switches neighbours off once, for all routes, rather than deselecting German vendors corridor by corridor.

---

## 3. Reason codes, not free text

Addendum A required a free-text reason ≥10 characters. That is friction that produces `"asdf asdf asdf"`.

Replace with presets plus optional detail:

| `reason_code` | label |
|---|---|
| `border_employees` | Employees are based near the border |
| `pricing_availability` | Better pricing or availability |
| `existing_relationship` | We already work with a provider there |
| `insufficient_local_coverage` | Not enough coverage in {base country} |
| `other` | Other *(free text becomes required)* |

Three benefits over free text:

1. **Faster for HR** — one click instead of composing a sentence.
2. **Analysable** — you can now answer *"why do HR teams extend?"* directly. If `insufficient_local_coverage` dominates, that is a supply problem you should be fixing, not a feature HR should be working around. This is the signal behind the 5–15% health band in Addendum A §A.11.
3. **Still fully auditable** — eval C5 checks `reason_code IS NOT NULL` rather than a character count, which is a stronger assertion.

---

## 4. Vendor counts on every chip

The single most important detail on this screen.

With neighbours default-on, counts do two jobs.

**In the base chip row** they explain what HR is already getting:

```
Vendors from   [🇫🇷 France · 3]  [🇩🇪 Germany · 6]  [🇪🇸 Spain · 2]  [🇨🇭 Switzerland · 2]
                base              neighbour           neighbour         neighbour
```

Belgium, Italy and Luxembourg are absent — not greyed out, **absent**. Zero eligible vendors means the chip never renders. A country chip that yields nothing is worse than no chip: it implies coverage that isn't there.

**In the "+ Add country" picker** they gate the click:

```
🇬🇧 United Kingdom (3)   🇳🇱 Netherlands (4)   🇵🇹 Portugal (0)   🇦🇹 Austria (1)
```

Zero-count countries render **disabled** with the tooltip *"No verified movers in Portugal yet."* Without counts, HR adds Portugal, sees nothing change, and concludes the product is broken.

Counts everywhere reflect the **full** eligibility predicate — in catchment **and** `vendor_reaches(destination)` — not just vendors present in the country. A count that overstates what HR will actually get is worse than no count.

This bites immediately: France has **4 mover capabilities today, all unvetted**, so on day one the France chip reads `(0)` and the whole category falls to the empty state. Honest, and it routes HR somewhere useful instead of into a silent dead end.

---

## 5. Screen anatomy

```
┌────────────────────────────────────────────────────────────────────────┐
│  Vendor curation                                                        │
│  Choose which providers your employees can request quotes from.         │
├────────────────────────────────────────────────────────────────────────┤
│  🇫🇷 France → 🇳🇴 Norway · Oslo          176 employees on this route  ▾  │
├────────────────────────────────────────────────────────────────────────┤
│  Movers │ Housing │ Schools │ Banking │ Immigration │ Tax               │
├────────────────────────────────────────────────────────────────────────┤
│  ℹ️  Movers are sourced from France — where your employees are moving   │
│      from. The origin agent surveys, packs, and arranges delivery       │
│      through their destination network.                    [Why?]  [✕]  │
├────────────────────────────────────────────────────────────────────────┤
│  Vendors from   [🇫🇷 France]   [🇩🇪 Germany  ✕]   [ + Add country ▾ ]   │
│                  base           extended · near-border                  │
│                                                                         │
│  ☐ Apply to all routes for Movers                                       │
├────────────────────────────────────────────────────────────────────────┤
│  3 of 8 selected            ●●●○○  3–5 recommended for a good RFQ       │
├────────────────────────────────────────────────────────────────────────┤
│  ☑  AGS Déménagement Int'l   🇫🇷 Paris    FIDI FAIM · Reaches NO ✓  4.6 │
│  ☑  Demeco                   🇫🇷 Lyon     IAM · Reaches NO ✓        4.3 │
│  ☐  Déménagements Delahaye   🇫🇷 —        ⚠ No reach evidence       4.1 │
│  ☑  Hasenkamp     [extended] 🇩🇪 Cologne  FIDI FAIM · Reaches NO ✓  4.7 │
│                                                                         │
│  + Add a provider we already work with                                  │
└────────────────────────────────────────────────────────────────────────┘
```

### The five states that need designing

| state | trigger | treatment |
|---|---|---|
| **Default** | origin-sourced category, vendors exist | Origin chip **plus neighbour chips that have vendors**, all in base styling. Vendors from neighbours carry a quiet `neighbouring country` badge — informational, not exceptional |
| **Neighbours off** | HR unticked "Include neighbouring countries" | Origin chip only; neighbour vendors drop out of the list with an undo toast |
| **Extended** | HR added a non-adjacent / short-sea / cross-bloc country | Extended chip with removable ✕ and the reason; matching vendors carry an `extended` badge |
| **Destination-sourced** | housing, schools, banks, immigration | **Neighbour control hidden entirely.** Explainer reads "sourced from Norway — where your employees are moving to." |
| **Empty catchment** | zero verified vendors in scope | Coverage-request empty state (below) |
| **Over-selected** | >8 selected | Soft nudge: *"More than 8 providers can slow the quote process."* Never blocking. |

### Empty state — the one that will fire first

Reuse `catalog_destination_requests` (18 rows) and `catalog_employee_demand` (42 rows). Both tables already exist with working services.

> **No verified movers in France yet**
> 4 French movers are awaiting verification. We'll notify you when they're ready.
>
> `[Request coverage for France]`  `[Add a provider we work with]`  `[Include neighbouring countries]`

Three exits, no dead end. `ConversationalEmptyState` already exists in `antigravity/` — use it.

### Reach badges

The difference between a real international mover and a local Paris removals firm is invisible from a name. Surface it:

- **`FIDI FAIM` / `IAM` / `OMNI`** — verified accreditation from `supplier_accreditations` (27 rows; the table's CHECK already guarantees a verified row carries `evidence_url + verified_at`)
- **`Reaches Norway ✓`** — destination reach evidenced
- **`⚠ No reach evidence`** — origin-country presence only. Selectable, but flagged.

This turns Addendum A's `vendor_reaches()` predicate into something HR can see and reason about, rather than an invisible filter.

### Selection guidance

`3–5 recommended` as a dot meter, not a hard limit. Industry practice for a household-goods RFQ is three to five quotes: fewer gives no price tension, more overwhelms the employee and drops the supplier response rate — which is already **6.7%** in production. Guidance, never a block.

---

## 6. Backend

### 6.1 Schema — one addition to Addendum A §A.5

Everything in Addendum A stands. Add the tier-2 policy table:

```sql
CREATE TABLE IF NOT EXISTS public.company_vendor_catchment_policy (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  category           text NOT NULL,
  include_neighbours boolean NOT NULL DEFAULT false,
  extra_countries    text[] NOT NULL DEFAULT '{}',
  reason_code        text NOT NULL CHECK (reason_code IN (
                       'border_employees','pricing_availability','existing_relationship',
                       'insufficient_local_coverage','other')),
  reason_text        text,
  created_by_user_id uuid NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, category),
  CHECK (reason_code <> 'other' OR (reason_text IS NOT NULL AND length(trim(reason_text)) > 0))
);
ALTER TABLE public.company_vendor_catchment_policy ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_vendor_catchment_policy FROM anon;
-- tenant-scoped policies, mirroring company_vendor_selections
```

Apply the same `reason_code` / `reason_text` columns to `company_vendor_catchment` (tier 3) and to `company_vendor_selections`, replacing Addendum A's free-text-only `extension_reason`.

### 6.2 One endpoint returns everything the screen needs

```http
GET /api/hr/catalog/curation
    ?category=movers&origin_country=FR&destination_country=NO&destination_city=Oslo
```

```jsonc
{
  "sourcing": {
    "side": "origin",
    "anchor_country": "FR",
    "explanation": "Movers are sourced from France — the country your employees are moving from.",
    "neighbours_offered": true          // false for destination-sourced categories
  },
  "catchment": {
    "base": ["FR", "DE", "ES", "CH"],   // origin + default-included neighbours WITH vendors
    "extended": ["GB"],                 // HR-added: short-sea, needs a reason
    "include_neighbours": true,         // the default; HR can switch off
    "resolved_from": "system_default",  // corridor_override | company_policy | system_default
    "base_detail": [
      { "code": "FR", "name": "France",      "vendor_count": 3, "role": "origin"    },
      { "code": "DE", "name": "Germany",     "vendor_count": 6, "role": "neighbour" },
      { "code": "ES", "name": "Spain",       "vendor_count": 2, "role": "neighbour" },
      { "code": "CH", "name": "Switzerland", "vendor_count": 2, "role": "neighbour" }
    ],
    // BE / IT / LU are default-included neighbours with 0 eligible vendors — omitted
    // entirely, not returned with a zero count. The client must not render an empty country.
    "addable": [
      { "code": "GB", "name": "United Kingdom", "vendor_count": 3,
        "excluded_by_default": "short_sea", "reason_code": "border_employees" },
      { "code": "NL", "name": "Netherlands",    "vendor_count": 4,
        "excluded_by_default": "not_adjacent" },
      { "code": "PT", "name": "Portugal",       "vendor_count": 0,
        "excluded_by_default": "not_adjacent" }
    ]
  },
  "vendors": [
    {
      "master_item_id": "…", "name": "AGS Déménagement International",
      "country": "FR", "city": "Paris",
      "selected": true, "selection_basis": "in_catchment",
      "reach_verified": true,
      "accreditations": ["FIDI FAIM"],
      "rating": 4.6, "rfq_reachable": true
    }
  ],
  "counts": { "in_scope": 8, "selected": 3, "recommended_min": 3, "recommended_max": 5 }
}
```

**One round trip, zero client-side derivation.** The frontend renders; it does not compute catchment. That is what keeps the HR screen and the employee engine from drifting apart — which is exactly how audit finding F-3 happened.

`available_neighbours[].vendor_count` counts vendors that would pass the **full** eligibility predicate (in catchment **and** `vendor_reaches(destination)`), not just vendors present in the country. A count that overstates what HR will actually get is worse than no count.

### 6.3 Writes

```http
PUT    /api/hr/catalog/catchment          { category, origin_country, destination_country,
                                            extra_countries[], reason_code, reason_text?,
                                            apply_to_all_routes: bool }
DELETE /api/hr/catalog/catchment/{code}   // remove one extended country
POST   /api/hr/catalog/curation/select    // existing — extended with origin_country + selection_basis
```

`apply_to_all_routes: true` writes tier 2 (`company_vendor_catchment_policy`); `false` writes tier 3 (`company_vendor_catchment`). One flag, two tables, no separate endpoint.

**Register all of these in both `backend/main.py` and `backend/app/main.py`** — the `CLAUDE.md` dual-registration rule. A router only in the modular app 405s in production; that has bitten this codebase three times.

### 6.4 The invariant that must not break

`resolve_catchment()` is called by **both** the recommendation engine and this endpoint. Not two implementations that agree — one function, two callers. Enforce it with a test that asserts the vendor set from `GET /api/hr/catalog/curation` is exactly the candidate set the engine produces for the same corridor. When they diverge, F-3 is back in a new costume.

---

## 7. What HR actually experiences

**Day 1, Acme SARL, first corridor.** HR opens Movers for FR→NO. The explainer tells them movers come from France. The list is empty — France has 4 movers pending verification. They click **Request coverage for France**, which writes a `catalog_destination_requests` row, and move on to Housing, which is populated because Norway has 4 approved housing agencies.

**Day 14, coverage lands.** Three French movers are verified. HR selects three, sees the meter turn green at `3–5`, and is done.

**Day 30, the Strasbourg case — now a non-event.** An employee near the German border asks about a Kehl mover. HR looks at the list and Hasenkamp is *already there*, under a `neighbouring country` badge, because Germany was in the default catchment from the start. No feature to discover, no modal, no reason code. This is what the default-on decision buys.

**Day 45, the genuine exception.** HR wants a UK mover — the company has a London entity and an existing contract. UK is `short_sea`, so it is not default-included. They click **+ Add country → United Kingdom (3)**, pick *"We already work with a provider there"*, and tick **Apply to all routes**. The selected UK vendors carry an `extended` badge.

**The audit trail.** German vendors pass C1 as `in_catchment` — nothing to justify, because nothing exceptional happened. UK vendors pass C1 as `hr_extended` with `reason_code` set and attributed, C5 passes, and C6 passes because a `short_sea` relation exists in `country_adjacency` even though `default_included` is false.

**Meanwhile**, the 177 companies with a Sydney mover approved for Norway still fail C1 and C6 — AU has no adjacency row to NO at all. The escape hatch does not launder them, which was the whole point, and default-on does not widen it: **`default_included` only ever admits countries that are already in the adjacency table.**

---

## 8. What the employee sees

One line, because trust is the product. Two variants now, and the distinction matters:

**Default-catchment neighbour** — no HR decision to attribute, so don't imply one:

> **Hasenkamp** · Cologne, Germany
> *Neighbouring country — can collect from your address in France*

**HR extension** — a real decision, so name it:

> **Britannia Movers** · London, United Kingdom
> *Added by your HR team — existing provider relationship*

The employee does not need the catchment model. They need to understand why a German mover appears in a France→Norway move without wondering whether the app is broken. Attributing the German one to "your HR team" would be a small lie — HR never touched it — and small lies in provenance copy are exactly what erodes trust in a recommendation surface.

---

## 9. Build order

| step | work | why here |
|---|---|---|
| 1 | `resolve_catchment()` + `country_adjacency` + `sourcing_side` | Addendum A P1–P2. Nothing renders without it. |
| 2 | `GET /api/hr/catalog/curation` returns the full envelope | Unblocks frontend; can be built against a stub |
| 3 | Read-only UI: explainer, **base chips incl. neighbours**, vendor list with reach + `neighbouring country` badges | Ship this alone — already a large improvement over today, and with default-on it delivers the border case by itself |
| 4 | `+ Add country` with counts + reason modal | For the genuine exceptions (short-sea, non-adjacent) |
| 5 | "Apply to all routes" (tier 2), including the **neighbours-off** opt-out | The thing that makes it survive corridor #2 |
| 6 | Employee-side attribution line | Trust |

Steps 1–3 are shippable on their own and worth shipping on their own.

---

## 10. Open questions

1. ~~**Should `include_neighbours` default to `true` for movers?**~~ **DECIDED 2026-08-13: yes.** The noise objection is answered by never rendering a country with zero eligible vendors — so France's four empty neighbours simply do not appear. What remains is that the common European border case works without HR discovering a feature. Consequences are folded through §2, §4, §5, §6 and Addendum A §A.5.4/§A.6/§A.11.
2. **Per-category or per-category-group policy?** Setting tier 2 for movers, storage and pets separately is three identical clicks. A "Moving & logistics" group would collapse them. Probably premature until storage and pets are live categories.
3. **Should HR see unvetted vendors at all?** Currently hard-filtered to `platform_vetting_status='approved'`. A greyed *"4 pending verification"* row would explain the empty state better than any copy — but it also exposes pipeline state to customers. Product call, not an engineering one.
