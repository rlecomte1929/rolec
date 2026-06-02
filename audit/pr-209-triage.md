# PR #209 triage — `audit(parker): integration of steps A–J`

**Captured:** 2026-06-01, daytime interactive run. Decision: **skip for now**, revisit with hands-on involvement.
**Branch:** `audit/parker-integration` · head `7ee91bd` (last pushed 2026-05-30 21:17Z) · 75 commits · +15,315 / −98.
**Divergence from main:** 68 ahead, 9 behind. Merge-base `81d98bc8` (2026-05-30 14:01Z), i.e. before the #179 / #211 chain landed.

---

## 1. What do the 8 "stale duplicate-named migrations" duplicate?

On 2026-05-30, main's commit `e22e6202` ("resolve 8 duplicate-version collisions; drop stale exception_requests lineage", part of the #179 chain) **renamed** 8 migrations from `*100000` → `*100001/*100002` to fix duplicate-version collisions. #209 predates this and still carries the **old `*100000` filenames**. Byte-comparison of the 8 pairs (#209 `*100000` vs main's renamed version):

| Logical migration | #209 file | main file | Content |
|---|---|---|---|
| policy_benefit_jurisdiction_overrides | `20260502100000` | `20260502100001` | **byte-identical** |
| s3_contract_move_type | `20260502100000` | `20260502100002` | **byte-identical** |
| s4_family_details | `20260502110000` | `20260502110001` | **byte-identical** |
| policy_assistant_chunks | `20260503100000` | `20260503100001` | **CONTENT-CONFLICTING** ⚠️ |
| completion_pct_trigger | `20260521070000` | `20260521070001` | **byte-identical** |
| policy_versions_publish_columns | `20260522130000` | `20260522130001` | **byte-identical** |
| policy_feedback_and_review_queue | `20260522140000` | `20260522140001` | **byte-identical** |
| support_drafts | `20260523020000` | `20260523020001` | **byte-identical** |

- **7 of 8 are byte-identical.** Merging #209 leaves *both* timestamps on main → the same `CREATE TABLE`/DDL runs twice → `supabase db push` / replay fails. This re-introduces exactly the collision #179 just fixed.
- **1 is content-conflicting — `policy_assistant_chunks`.** main's `*100001` has the `::uuid` cast fix (`where id::uuid = auth.uid()`, `company_id::uuid`); #209's `*100000` has the **pre-cast, broken** RLS policy. Merging #209 would re-introduce an uncast (incorrect) RLS policy at an *earlier* timestamp than the fix.
- **Plus exception_requests lineage diverged.** main's `e22e6202` "dropped stale exception_requests lineage" and `5c58177e` made `20260427100000_exception_requests` replayable. #209 still carries the old `20260427100000_exception_requests.sql` + `20260522150000_fix_exception_requests_rls_uuid_cast.sql`. This is the third lineage area to reconcile.

**Note:** #209's *net-new* Parker migrations (`20260601020000`–`20260601100000`: ml_models, benefit_optimizer, supplier_cluster_cache, prompt_registry, ai_human_feedback, ocr_shadow_comparison, ai_unit_economics, conjoint, translation_cache) do **not** collide with main's `20260531*_rls_*` / `20260601000000_rls_cases_domain` files. Those 9 are clean and additive.

## 2. What does "CI fully red" decompose into?

**100% GitHub Actions billing failure — zero code signal.** The red run (`26695080443`) is **stale, from 2026-05-30 21:13Z**. Every job fast-failed in 1–3s with the GitHub annotation:

> "The job was not started because recent account payments have failed or your spending limit needs to be increased."

So the runners never started — there is **no information** about real test/build health on #209. This is **not** pre-existing flakes, **not** failures from main moving, **not** code regressions. Billing has since recovered: main's CI ran **green at 06:56Z on 2026-06-01**, and the #179 branch at 06:44Z. #209 simply has not been re-pushed since the billing-outage window, so its checks were never re-run. **A fresh run after rebase/branch is required to learn anything about actual code health.**

## 3. Cleanest fix path

Three candidates, in increasing order of cleanliness:

- **(a) Rebase + reapply manually.** `git rebase origin/main`, then explicitly `git rm` the 7 byte-identical stale `*100000` files, delete #209's `policy_assistant_chunks *100000` (keep main's cast-fixed `*100001`), and reconcile the exception_requests lineage to match main. Risk: a naive rebase replays #209's "add `*100000`" commits with **no textual conflict** (different filenames), silently re-adding the duplicates — so the dedup deletions must be done as an explicit follow-up commit, file-by-file. Error-prone; 8+ files to babysit.

- **(b) Branch-from-current-main + replay the 10 step merges.** Recreate the integration by re-merging steps A–J on top of today's main. Faithful to original structure but re-incurs every per-step migration-lineage decision; highest effort.

- **(c) Branch-from-current-main + squash-cherry-pick the unique commits.** ⭐ **Recommended.** The Parker work is overwhelmingly **additive** — 9 net-new migrations (`20260601020000`–`100000`), new routers/services (cox-survival, benefit-optimizer, cluster-tiering, prompt-registry, RLHF feedback, OCR shadow, unit-economics, conjoint, translation, NLG variety), and their dual-layer registrations. Branch fresh from current main, cherry-pick only those additive commits, and **drop the stale migration-lineage commits entirely** (main already has the deduped + `::uuid`-cast-fixed versions). This sidesteps all 8 duplicates and the exception_requests divergence in one move. Then run the 10-route-family mount-check + a fresh CI run for real signal, and smoke the 10 prefixes post-deploy (expect 401/403/404, never 405).

**Recommendation:** path (c). Pair on it rather than auto-merge — the cherry-pick selection (which of the 68 commits are "additive Parker" vs "stale lineage") is a judgment call worth a human eye, and it's the highest-leverage merge in the queue.

---

## Close-batch EXECUTED 2026-06-01 late — Parker step PRs #197–206 all CLOSED

_(executed end-of-session; all 10 verified CLOSED. #209 kept open. Original ready-to-paste block retained below for reference.)_

These are the 10 individual Parker step PRs (A–J), all superseded by the #209 integration. **Do NOT run until #209 is reconciled + merged** (or its successor lands) — the close comment references it. Paste the block once that decision is made:

```bash
gh pr close 197 --comment "Superseded by #209 (Parker integration, steps A–J). Cox-survival (step A) is folded into the integration branch. Closing the standalone step PR."
gh pr close 198 --comment "Superseded by #209 (Parker integration, steps A–J). Benefit-optimizer (step B) is folded into the integration branch. Closing the standalone step PR."
gh pr close 199 --comment "Superseded by #209 (Parker integration, steps A–J). Cluster-relative supplier tiering (step C) is folded into the integration branch. Closing the standalone step PR."
gh pr close 200 --comment "Superseded by #209 (Parker integration, steps A–J). Prompt registry + canary A/B (step D) is folded into the integration branch. Closing the standalone step PR."
gh pr close 201 --comment "Superseded by #209 (Parker integration, steps A–J). RLHF-lite preference dataset (step E) is folded into the integration branch. Closing the standalone step PR."
gh pr close 202 --comment "Superseded by #209 (Parker integration, steps A–J). Passport-ocr-oss (step F) is folded into the integration branch. Closing the standalone step PR."
gh pr close 203 --comment "Superseded by #209 (Parker integration, steps A–J). Carbon-TCO (step G) is folded into the integration branch. Closing the standalone step PR."
gh pr close 204 --comment "Superseded by #209 (Parker integration, steps A–J). Conjoint (step H) is folded into the integration branch. Closing the standalone step PR."
gh pr close 205 --comment "Superseded by #209 (Parker integration, steps A–J). Neural translation layer (step I) is folded into the integration branch. Closing the standalone step PR."
gh pr close 206 --comment "Superseded by #209 (Parker integration, steps A–J). NLG-variety (step J) is folded into the integration branch. Closing the standalone step PR."
```

Reports #207/#208 and hold-marker #210 were already closed on 2026-06-01 (see daytime-run-summary). After running this batch + resolving #209, the Parker stream is fully drained.
