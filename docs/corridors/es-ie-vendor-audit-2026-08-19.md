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

## 2. But the corridor is not empty — it is unpromoted

`vendor_candidates` holds **19 rows for IE/ES**.

This is the actionable part of the finding. The candidates exist; nothing has promoted them into
`suppliers`, which is why every coverage query reads zero. The gap is a **promotion-pipeline gap,
not a research gap** — a materially cheaper problem than sourcing 36 suppliers from scratch, and a
different one than the brief assumed.

Whether those 19 are sufficient for a shortlist (≥3 usable per critical category, with a
defensible recommended pick) cannot be answered until they are examined against the category
vocabulary. That is the recommended next step, and it is deliberately **not** performed here: a
promotion writes customer-adjacent rows, and this audit is read-only.

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

1. **Triage the 19 IE/ES `vendor_candidates`** against the six live categories. That single step
   determines whether this corridor needs promotion, research, or both.
2. **Resolve `SIRVA Worldwide` before any ES→IE promotion**, or the promotion will inherit an
   uncountried RMC.
3. Only then decide whether the dossier-scale sourcing the brief assumed is actually required.

Nothing was written to the database or to any seed file.
