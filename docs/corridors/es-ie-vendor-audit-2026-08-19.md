# ES→IE vendor audit — 2026-08-19

Audit of the Spain→Ireland (Madrid→Dublin) supplier layer.

> **Scope note.** As with the NO→FR audit of the same date, the task brief described a
> `supabase/seed/vendors/` tree and a `vendor_providers` table that **do not exist** in this
> repository or in production. See the NO→FR report §6 for the full absence list. This audit was
> run against the supplier layer that does exist.

## 1. The finding

**The ES→IE corridor has no supplier layer at all.**

| measure | IE | ES |
|---|---|---|
| rows in `suppliers` | **0** | **0** |
| rows in `supplier_service_capabilities` | **0** | **0** |
| categories with ≥1 supplier | **0 of 6** | **0 of 6** |

Every category is empty on both sides, including both compliance-critical ones
(`legal_admin`, `tax_finance`).

There was consequently nothing to dedup, nothing to recategorise, and nothing to reconcile. The
brief's dedup pass, its superseded-key rejection list (`savills-ireland-cork-dsp-ie`,
`crown-relocations-cork-mover-international-ie`, the five general insurers miscategorised as
`healthcare_navigation`, and the rest) and its `index.json` reconciliation all describe rows that
are **not present in this system**. None were actioned, and no rows were created so that they
could be.

## 2. The 19 `vendor_candidates` — triaged, and they do not help

> **Correction.** An earlier revision of this report called the 19 IE/ES candidates a
> "promotion-pipeline gap, not a research gap" and judged it materially cheaper than sourcing.
> **That was wrong.** Triage shows promoting all 19 would add nothing to this corridor's
> shortlist. The original text is replaced rather than annotated, because a recommendation that
> sends someone down the wrong path is worse than no recommendation.

### Zero of them are in a live category

| | |
|---|---|
| candidate categories | `customs_broker`, `pet_relocation`, `vehicle_registration`, `vehicle_shipping` |
| live categories | `legal_admin`, `movers`, `housing_agencies`, `tax_finance`, `schools`, `banks` |
| **overlap** | **0 of 19** |

Promoting every one of them leaves ES→IE at **0 of 6** categories and **0 of 2**
compliance-critical ones. They belong to the pets/vehicles product surface, not to a corridor
vendor shortlist.

### They are not ES→IE research

All 19 carry `run_id = NULL` and sit inside a single **480-row global harvest** spanning 25
countries and 18 categories. The source names are dominated by US-outbound vehicle shipping and
IPATA pet-transport directories — several of the Irish rows come from pages titled *"Schumacher
Cargo — Shipping a Car to Ireland from USA"*, *"ShipNEX — International Car Shipping to Ireland"*
and *"BR Logistics — Ship a car to Ireland"*.

These rows exist for IE and ES because a global scrape happened to cover those countries, **not
because anyone researched the Madrid→Dublin corridor**. Two of the five Irish pet entities are
US-based (Tampa, Chicago) and reach Ireland only as a destination market. For a Spain→Ireland
move — two EU states — a US RoRo car shipper is not a corridor supplier in any useful sense.

### The dedup defect — root-caused, and it is table-wide

> **Correction, twice.** I first reported this as "the `dedupe_key` is not preventing
> duplicates", then as "the executor's pre-check is scoped `WHERE corridor = :corridor`, which is
> NULL on these rows, so the check is dead". **Both were wrong**, and the second was wrong in a
> way that would have produced a fix for a bug that does not exist. What follows is what the code
> and the data actually show.

**The in-repo dedup is sound.** `vendor_harvester.existing_dedupe_keys()` reads
`SELECT dedupe_key FROM vendor_candidates` **unscoped** — it sees every prior key regardless of
corridor. The corridor-scoped `_staged_keys()` in `imports/suppliers/executor.py` is a second,
narrower guard added after a real incident (2026-08-11, `--apply` then `--promote` left 62
candidates where there should have been 31); in that flow `corridor` is always populated, because
the executor groups by `(corridor, category)`. Neither is broken.

**The duplicates come from a writer outside this repo.** No in-repo code produces the observed
key format. `vendor_harvester` emits a registrable domain, or `name:{slug}@{corridor}` as a
fallback. The rows in the table are keyed `pet_relocation|IE|dublin|pets on board` — a fourth
format, written by the Otto-side harvest that produced all 480 corridor-NULL rows on 2026-08-13.

**And that writer's key changed between two runs on the same day**, six hours apart:

```
10:09   "|IE|dublin|pets on board"                ← category segment EMPTY
16:51   "pet_relocation|IE|dublin|pets on board"  ← category segment populated
```

Same company, same website, same source — a different identity. No uniqueness constraint could
have caught it, because the two keys genuinely differ. This is why the column's documented
contract matters: it says *"Normalised registrable domain (lowercase, no scheme, no www)"*, and a
domain key (`pets-on-board.ie`) would have been identical across both runs. The implementation
that wrote these rows ignored the contract, and the instability followed.

**Scale, measured across the whole table — not just this corridor:**

| measure | value |
|---|---|
| rows in `vendor_candidates` | 534 |
| duplicate groups by (category, country, normalised domain) | **52** |
| redundant rows | **97** (18% of the table) |
| rows with no website at all | 83 |
| duplicate groups by the stored `dedupe_key` | 0 |

The stored key catches **none** of it. A writer-agnostic identity catches 97 rows. The five Irish
pairs are a visible slice of a table-wide problem.

**Why the fix is not a constraint I can just add.** A `UNIQUE` on
`(service_category, country_code, normalised_domain)` would reject all 97 today, so it cannot be
applied before a dedupe pass — and that pass deletes production rows, which is a founder decision,
not an audit one. The 83 domainless rows also need a second identity rule. Sequence:
**agree the survivor rule → dedupe → then constrain**, so the constraint is what keeps it clean
rather than what discovers the mess.

### The corridor-level duplicates

- **IE: 10 rows, 5 distinct entities.** Every Irish candidate is present exactly twice — Air
  Animal Pet Movers, K International Freight, Multi Cargo, Pets in Transit, Pets on Board. Every
  one of those rows has a populated `dedupe_key`, so **the key is not preventing duplicates**.
  That is a pipeline defect, not a data-entry accident, and it will repeat on the next harvest.
- **ES: `Relomar Relocation Services, SL` and `Relopet (Relomar Relocation Services, SL)` are the
  same legal entity** — the second name says so. 9 rows, 8 distinct entities.

Flagged, not merged — per the dedup rules, divergent-key duplicates go to the founder.

### What is good about them

Traceability, unusually: **all 19 carry both a website and a `source_url`**, which is better than
the NO→FR suppliers (30% of those have no `source_url`). Whatever pipeline produced them records
provenance properly. `corridor` is NULL on all 19 and `source_tier` is unset on all 19, so even
after promotion they would be corridor-agnostic — the same defect class as `SIRVA Worldwide`.

## 3. So the corridor is empty, and stays empty

ES→IE has no supplier layer and no candidate pool that can become one. Closing it requires
**actual sourcing against the six live categories** — the dossier-scale work the brief assumed
already existed. There is no cheaper path hiding in `vendor_candidates`.

The one genuinely useful thing the 19 provide is a negative result delivered in minutes rather
than after a promotion run that would have added US car shippers to a Madrid→Dublin shortlist.

## 3. Competitor (RMC) check

Not applicable — the corridor lists no suppliers, so no RMC can be corridor-tagged on it.

`Cartus` and `Crown World Mobility` are absent from the supplier table entirely. See the NO→FR
report §4 for the `SIRVA Worldwide` finding, which is uncountried and therefore corridor-agnostic
— **if ES→IE suppliers are promoted, that row can surface here too.** Resolve it before promoting.

## 4. Corridor context this audit does not cover

The brief supplies real corridor mechanics — DETE employment permit via EPOS before travel, Burgh
Quay IRP within 90 days against a 6–8 week queue, the PPSN→RPN sequence before first payroll to
avoid 40% emergency tax, the proof-of-address bank catch-22, Lifetime Community Rating loading
after nine months, and the two-sided Beckham/SARP tax exposure.

Those are **requirement-layer** facts. They are recorded here only to note that they shape which
categories matter for this corridor — bridge housing is a compliance dependency because PPSN needs
an Irish address first, so `housing_agencies` is arguably critical here even though the shared
category table does not mark it so. The requirement rule-engine was not touched, per the brief.

## 5. Recommended next actions

1. **Do not promote the 19.** They add zero coverage and would put US-outbound car shippers in a
   Madrid→Dublin shortlist.
2. **Dedupe `vendor_candidates`, then constrain it.** 97 redundant rows (18%) table-wide. The
   in-repo harvester is not the cause and needs no change; the durable fix is a writer-agnostic
   uniqueness rule, which can only be added after a founder-approved dedupe pass. Raise the key
   format with whoever owns the Otto-side writer — it ignores the column's documented
   domain contract, which is what made its key unstable between runs.
3. **Source ES→IE properly** against the six live categories. This is the real cost, and nothing
   in the data avoids it.
4. Resolve `SIRVA Worldwide` before any promotion into this corridor — it is uncountried, so it
   would surface here too.

No seed file was touched. One database change was made — see the appendix.

---

## 6. Customer readiness — the go/no-go for a waiting ES→IE case

Added 2026-08-19 on hearing a real ES→IE customer is waiting. **No real ES→IE case exists in
production** — every ES or IE case in `public.cases` belongs to an `@probe.test` E2E fixture,
which the campaign purges on every push to `main`. So this is a readiness assessment, not a case
review.

### The binding constraint is the calendar, not the vendors

Run through the product's own `assess_feasibility()`:

| | |
|---|---|
| corridor | `ES_IE_CSEP_2026` |
| arrival anchor | `TRAVEL_TO_IE` |
| **pre-arrival lead time required** | **104 days (~15 weeks)** |
| verdict at 88 days' runway | **`critical`** |

The pre-arrival chain is serial and authority-gated:

```
JOB_OFFER_CONTRACT → EMPLOYMENT_PERMIT_APPLICATION → EMPLOYMENT_PERMIT_GRANTED (DETE)
                   → D_VISA_APPLICATION → D_VISA_GRANTED (ISD) → TRAVEL_TO_IE
```

Nothing in it can be parallelised or bought — two of the six steps are decisions by Irish
authorities. **If the employee is non-EEA and the move date is under ~15 weeks out, the CSEP route
cannot make it**, whatever the vendor shortlist looks like.

### Two questions decide everything, and both are free to ask

1. **Is the employee an EEA national?** If yes, none of the permit chain applies — free movement,
   and the corridor is feasible at any notice. If no, the 104-day floor binds.
2. **What is the target move date?** Compare to today + 104 days. Inside that window, the honest
   answer to the customer is that the date is not achievable on this route — and saying so early
   is the product working, not the product failing.

### What is genuinely missing, ranked for this customer

| gap | state | impact |
|---|---|---|
| **SPAIN requirements** | **0** (IRELAND has 14 approved) | **largest hole.** This corridor is two-sided — Beckham exclusion on ceasing Spanish residence, modelo 030/247, exit-year IRPF. Half the compliance surface is invisible, and it is the half that surprises people months later |
| ES→IE vendors | 0 both sides | shortlist is empty; the customer can be served manually |
| `housing_agencies` for Dublin | 0 | PPSN needs an Irish address first, so bridge housing is a compliance dependency, not a comfort item |

**Requirement coverage is the bigger gap than vendors.** A missing vendor means the customer finds
their own mover. A missing Spanish exit requirement means nobody tells them about an exit-year tax
exposure until it is too late to act on it.

### Recommended sequence for this customer

1. Ask the two questions above. They are a five-minute call and they determine whether anything
   else matters.
2. If non-EEA and inside 15 weeks: say so now, and discuss a later start date or an EEA-national
   alternative. Do not let a shortlist gap hide a calendar problem.
3. Source the **SPAIN exit requirements** before the vendor shortlist. Higher compliance value per
   hour of research.
4. Serve the first case with a manually assembled vendor list, and let it tell you which
   categories actually got used before investing in all six.

---

## Appendix — dedupe pass executed 2026-08-19

**Done.** 97 redundant `vendor_candidates` rows were marked `status = 'duplicate'`.

**Nothing was deleted.** The repo's own convention is to mark rather than drop —
`vendor_harvester.classify()` states it directly: *"Duplicates are INSERTED with
status='duplicate' rather than dropped: a silently skipped row is invisible, and the run report
has to be able to show what was."* This follows that, so the rows stay auditable and the change
is reversible.

### Survivor rule

Within each `(service_category, country_code, normalised domain)` group:

1. **a promoted row always survives** — it is referenced by a `suppliers` row downstream;
2. otherwise the **most recently created** row survives — the later Otto run carries the
   corrected key format and fresher source data;
3. ties broken by `id`, so the outcome is deterministic and replayable.

Only unpromoted, currently-`pending` rows were touched.

### Result

| | before | after |
|---|---|---|
| `pending` | 530 | **433** |
| `duplicate` | 4 | **101** (97 added) |
| promoted rows still `pending` | 50 | **50** — none demoted |
| groups with >1 unpromoted pending row | 52 | **0** |
| IE candidate rows pending | 10 | **5** — the 5 distinct entities |

Validated inside `BEGIN … ROLLBACK` before applying. The first validation run **failed its own
assertion**, revealing that 50 pending rows are already promoted — which forced the survivor rule
to prefer promoted over newest. Applied blind, the update would have left promoted candidates
competing with fresher unpromoted ones.

### Reversal

Every touched row carries a stamped note. To undo the whole pass:

```sql
UPDATE public.vendor_candidates
   SET status = 'pending', updated_at = NOW()
 WHERE status = 'duplicate'
   AND notes LIKE '%corridor vendor audit%';   -- exactly the 97
```

### Still to do — the constraint

With zero residual duplicate groups a partial unique index is now *possible*:

```sql
CREATE UNIQUE INDEX vendor_candidates_identity_uq
    ON public.vendor_candidates (
        service_category, country_code,
        lower(regexp_replace(regexp_replace(website_url,'^https?://(www\.)?',''),'/.*$',''))
    )
 WHERE status = 'pending' AND website_url IS NOT NULL AND website_url <> '';
```

**Deliberately not applied.** It would make the next Otto harvest *fail* rather than duplicate —
correct behaviour, but a behaviour change on a writer outside this repo, and that owner needs to
adopt `ON CONFLICT DO NOTHING` first. The 83 domainless rows also need a second identity rule
before coverage is complete. Sequence: tell the Otto-side owner, then apply.
