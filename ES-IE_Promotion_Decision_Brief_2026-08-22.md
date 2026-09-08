# ES→IE Promotion Decision Brief

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Purpose:** one go/no-go artifact for landing the ES→IE third-country batch into serving. Everything below is **staged and verified; nothing is promoted.** Read §3, make the eight calls, and the exact promotion prompt writes itself.

---

## 1. Where we are

- **CT-1 — staged.** 38 facts / 6 entities in `otto_staging` (batch `es-ie-thirdcountry-requirements-2026-08-22`). Idempotent; serving untouched. Ledger: 38 new / 0 dup-in-batch / 6 entities.
- **CT-3 — reconciliation report** (`RECONCILIATION_REPORT.md`). The key correction: promotion dedupes on **`(country_code, purpose, title)`** with `title = entity.title` — **not `topic_key`**. Promoting as-staged creates 6 new served rows beside the 42 existing, **content-duplicating 11 facts**, colliding on none — and would **overwrite reviewed rows** if a title collides. **23 of 38 facts are genuinely new.**
- **Pillar fix — PR #1973** (open, not merged). Honors `applies_to.pillar`, normalizes `TAX → EMPLOYMENT` (the batch's `TAX` isn't a catalog pillar and would have written a silent, unrenderable 8th pillar), refuses unknown/conflicting pillars. 11/11 new tests, 144 no-regression, serving-isolation green.
- **Health fact — verified by Otto.** Claim is solid (corroborated by Citizens Information); the HSE source URL is **dead and unarchived** → hold on source, not accuracy.
- **90-day timing — adjudicated.** The staged batch is **correct** (90 days from arrival/landing) — it matches both the structured `requirement_facts` and the **approved, served** item. The wrong wording (`"within 90 days of ISD granting permission"`) lives in **one `requirement_items` row, `acdddd42`, which is `pending` (not served)** — a leftover from an earlier ES→IE attempt.

## 2. Promotion readiness by topic

| Staged topic | CT-3 recommendation | new | dup | Promote now? |
|---|---|---|---|---|
| immigration_work_authorization | MERGE → csep | 3 | 5 | ✅ append 3 new; drop 5 dups; **don't overwrite reviewed csep rows** |
| isd_irp_registration | MERGE → irp_registration | 7 | 2 | ⏸ after `acdddd42` fixed (D4) |
| revenue_rpn_emergency_tax | MERGE → emergency-tax pair | 5 | 2 | ⏸ after PR #1973 merged (D2) |
| taxation | KEEP-AS-NEW | 2 | 1 | ⏸ after PR #1973 merged (D2) |
| ppsn | MERGE → PPS (non-EEA) | 4 | 1 | ⏸ pillar decision (D3) |
| health_entitlements | MERGE → Public Health (non-EEA) | 2 | 1 | ⏸ source relocation (D5) + pillar (D3) |

## 3. The eight decisions (recommendation in **bold**)

- **D1 — Merge strategy.** **Append-only:** promote genuinely-new facts into existing purposes, **drop the 11 content-duplicates**, and **never overwrite a reviewed row** (the CSEP-fee and IRP-card rows are the tripwires — `create_requirement_item` rewrites description + citations on the natural key).
- **D2 — PR #1973.** **Review + merge.** It's the prerequisite for correct tax/pillar filing; the code is correct. The two ⚠️ it flags (below) are downstream data decisions, not merge-blockers.
- **D3 — PPS & health pillar.** Live has both at `RESIDENCE` (confirmed) — almost certainly the pillar-bug artifact, not intent (all `representative`, `purpose=employment`). **Recommend: `health → HEALTHCARE`; PPSN is genuinely cross-cutting — pick `EMPLOYMENT` or keep `RESIDENCE`, but align the new facts AND the ~5 existing rows so one concept isn't split across pillars.** Implies a small, gated backfill.
- **D4 — Wrong pending timing row `acdddd42`.** **Reject or correct it** — the staged batch is authoritative (90 days from arrival). Not served today; fix before it can be.
- **D5 — Health fact.** **Hold + relocate source.** Find the current HSE Medical-Card Assessment Guidelines URL; **do not cite the third-party Scribd scan.** Accuracy is fine; the source is the problem.
- **D6 — topic_key convention.** **Adopt bare snake_case** (report §B): a destination requirement isn't corridor-specific, audience is already in `applies_to`/`purpose`, and it matches the live majority. Re-key in place **or** re-stage once — never both (it changes all 38 dedupe keys).
- **D7 — Pre-existing debt.** **Defer to a separate cleanup task.** 8 misfiled vehicle entities (0 facts) + 7 underscore/hyphen duplicate pairs, **two reviewed to opposite outcomes** — worse than anything this batch adds, but not ES→IE's job to fix. Don't let it block the landing.
- **D8 — Concurrent Ireland work.** Another agent moved `main`'s HEAD to `fix/aiq-1845-ireland-verified-batch-1` mid-session. **Check it isn't landing overlapping Ireland content before you promote**, so two efforts don't collide.

## 4. Recommended sequence (once the calls are made)

1. Review + **merge PR #1973** (D2).
2. **Fix `acdddd42`** — the wrong pending timing row (D4).
3. **Append-only promote the clean subset** — immigration_work_auth (3) + isd_irp (7, after step 2) + revenue (5) + taxation (2) ≈ **17 genuinely-new facts** — pillars honored, reviewed rows untouched (D1).
4. Resolve **D3** pillar + backfill; then promote **ppsn**.
5. **Hold health** until the source is relocated (D5); **drop the 11 duplicates**.
6. Queue the **pre-existing debt cleanup** (D7) as its own task.

## 5. What this run already proved

The tandem — Otto (research) + Claude Code (ingest/code/DB) across the bridge — took a real corridor from files to a fully-audited, promotion-ready state and caught, **before anything reached a user**: content duplication, a reviewed-row overwrite risk, a pillar-mapping bug (plus a latent 8th-pillar defect), a wrong deadline sitting in a pending row, and a dead source. Promotion is the *only* step left that touches a mover — and it's correctly gated behind your eight calls above.
