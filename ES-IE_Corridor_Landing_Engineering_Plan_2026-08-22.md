# ES→IE Corridor — Landing & Activation Engineering Plan

**Author:** Claude (Cowork) · **Date:** 2026-08-22 · **Owner:** Romain
**Scope:** Take the Andrea (Madrid → Dublin, non-EEA professional) corridor research from *verified files in hand* all the way to *correctly served product behaviour*, reusing everything already built.
**Repo:** `rlecomte1929/rolec` · **Target branch:** `fix/td-qa-services-batch-0719` (never `main`)

---

## 1. Where we are (assets in hand)

Everything below is done, verified, and on disk unless marked otherwise.

| Asset | State | Location |
|---|---|---|
| **ES→IE destination batch** (thirdcountry, 38 records) | ✅ verified, placed | `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/` |
| **Delivery gate** `check_otto_batches.py` (27,074 B) | ✅ placed, runs clean | `scripts/check_otto_batches.py` |
| **Independent collision checker** (`verify.py`) | ✅ built, run — *not yet committed* | scratch (`/tmp/tdbatch/verify.py`) |
| **ES→IE origin batch** (es-departure, 28 records) | ⏳ files pending from you | — |
| **Production loader knowledge** | ✅ read + diffed | `supabase/functions/otto-loader/index.ts` |
| **DB export** (collision ground truth, 2026-08-18) | ✅ used | `data/workspace-db-export/2026-08-18/` |
| **Loader playbook** (GCS → otto-loader, proven 2026-08-13) | ✅ read | `audos-workspace-776786/docs/otto-to-relopass-loading-playbook.md` |

**Verification already banked:**
- Real gate on the destination batch: **PASS — 54 checks, 0 failed, 0 skipped**, run from inside the clone.
- My independent reproduction: **PASS — 52/52**, including the one check the offline gate *cannot* do — `dup_existing = 0` against the real DB export (zero pre-existing `ES-IE:thirdcountry:*` entities; the 6 topic entities are genuinely new).
- NDJSON is byte-identical to otto's gate copy (`sha256 188028d6…beacb7`, 78,040 B, 38 lines).
- Production loader vs. the Audos copy otto simulated against: **byte-identical on every promotion path** (routing, `ALLOWED_DOMAINS`, `FACT_TYPES`, both dedup keys). The simulation is faithful to production.

**The gap that makes this worth doing:** the batch carries `applies_to.nationality_scope_basis` (the S1 audit) and `assertion_mode: conditional` (the A3 dependency). **Neither field is read by a single backend or frontend file today.** Landing the data without wiring these is how a Spanish (EEA) mover gets wrongly told they're exempt from Irish Emergency Tax — the exact failure the S1 audit exists to prevent. So the plan runs past "land the files" to "serve them correctly."

---

## 2. The full-stack arc & trust invariants

```
Otto research ─▶ NDJSON batch ─▶ [GATE] ─▶ PR (files only) ─▶ human + lawyer review
                                                                        │
                          ┌─────────────────────────────────────────────┘
                          ▼
             GCS upload + manifest ─▶ otto-loader (dry_run ▶ real) ─▶ requirement_facts / _entities
                                                                        │
                                                                        ▼
                                   serving layer (requirement_facts.py + services)
                                        · filter on nationality_scope_basis, NOT nationality
                                        · render assertion_mode=conditional as conditional
                                        · surface non_obvious "traps"
                                        · never let an LLM touch the serving path
                                                                        │
                                                                        ▼
                                                            mover roadmap / HR views
```

**Invariants to hold throughout (they already exist in this repo as CI guards):**
1. **Files-first, promote-later.** Precedent: B3 landed "as artifacts, not database rows." Nothing promotes until human/lawyer sign-off.
2. **Generation/serving split.** `check_serving_llm_isolation` / `check_route_auth` guards must stay green — the serving path can never reach an LLM.
3. **Human-only status transitions.** `representative → expert_verified` is a human flip (already guarded). This batch is `review_status: pending`, `verification_status: representative`, `assurance_status: not_started`.
4. **Nationality scope ≠ nationality.** Filter applicability on `nationality_scope_basis`; `nationality: non-EEA` is the batch's *audience*, not a legal restriction on the 17 `audience_scope` records.

---

## 3. Phased plan

Each phase: **objective · steps · acceptance · owner · autonomy tier · depends-on.** Tiers use your rubric (🟢 auto / 🟡 batched approval / 🔴 full human gate).

### Phase 1 — Land the artifacts (PR) 🔴
**Objective:** Both batches + the gate on `fix/td-qa-services-batch-0719`, files-only, PR opened, not merged.

**Steps**
1. Verify es-departure the same way (Phase 0 dependency below) so both batches are green before the commit.
2. From your Mac terminal, land via an **isolated worktree** so your `feat/aiq-1854` working state is never disturbed (exact commands in Appendix A). The branch is **3 commits behind origin** and forked from an **older main**, so catch it up to `origin/<branch>` first.
3. Commit the 4–7 files; push to `fix/td-qa-services-batch-0719`; open PR with `--base main`.
4. PR body (Appendix B) must: paste both gate outputs; flag that `scripts/check_otto_batches.py` is **new in this diff** (review it as code, not as trusted tooling); surface the `destination_country: IE` + `ES-IE:exit:*` namespace judgement call for es-departure; carry over the honest limits.

**Acceptance:** `python3 scripts/check_otto_batches.py --all` is green for both batch ids; PR open against `main`; `main` untouched; not merged.
**Owner:** Romain (git/push/PR — the bridge has no GitHub creds). **Depends on:** Phase 0.

### Phase 0 — Verify & place es-departure ⏳🔴 (blocks Phase 1)
**Objective:** Bring the origin half to the same bar as the destination half.
**Steps:** you upload `es_departure_exit_requirements.ndjson` + `manifest.json` + `README.md`; I confirm byte counts (80,297 B / 28 records / 16,199 B manifest), run `check_otto_batches.py es-departure-2026-08-22` (expect **60/0/0**), run the collision check against the export, place the files on disk.
**Acceptance:** gate 60/0/0; `dup_existing = 0`; byte counts match. **Owner:** me, on your upload.

### Phase 2 — Make the gate a standing control 🟡
**Objective:** Stop relying on anyone remembering to run the gate.
**Steps**
1. Add a `docs/imports` job to `ci.yml`: on any change under `docs/imports/**` or `scripts/check_otto_batches.py`, run `python3 scripts/check_otto_batches.py --all` (stdlib-only, no deps, fast).
2. Add the same to `.githooks/pre-commit` (guarded to only fire when a batch dir is touched).
3. **Drift guard:** the gate hard-codes `LOADER_FACT_TYPES` / `LOADER_DOMAIN_AREAS` mirroring the edge function. Add a tiny test that parses `ALLOWED_DOMAINS` / `FACT_TYPES` out of `supabase/functions/otto-loader/index.ts` and asserts equality with the gate's sets — so a loader allow-list change can never silently outdate the gate.

**Acceptance:** CI fails a deliberately-mutated batch; drift test fails if the two allow-lists diverge. **Owner:** me (code) → your review. **Depends on:** Phase 1 (gate on branch).

### Phase 3 — Close the offline-gate gap (collision tool) 🟡
**Objective:** Promote `verify.py`'s DB-collision check into committed, repeatable tooling — the gate is deliberately offline and can't do it.
**Steps**
1. Productionize as `scripts/check_otto_promotion.py <batch-id> --export data/workspace-db-export/<date>/`: rebuilds the loader's existing-key sets (`dest|topic_key` for entities, `dest|topic_key|fact_key` for facts) and reports `mapped_new / dup_in_batch / dup_existing / entities_created`, exactly mirroring `otto-loader` v6.
2. Make "run this against a **fresh** export" a required step in the promotion runbook (Phase 4), since a 4-day-old export can miss newly-loaded keys.

**Acceptance:** on the destination batch, reports `38 mapped_new, 0 dup_existing, 6 entities`. **Owner:** me → your review.

### Phase 4 — Promote into the DB (loader run) 🔴
**Objective:** Turn reviewed files into `requirement_facts` / `requirement_entities` rows — **only after Phase 1 review sign-off.**
**Steps** (per the proven playbook)
1. Upload each batch's NDJSON + a loader manifest to GCS (`storage.googleapis.com` — the loader's only allow-listed fetch host).
2. **Dry run:** call `otto-loader` with `dry_run=true`; confirm the response matches the sim — `mapped_new = 38` (and 28), `unrouted = 0`, `dup_existing = 0`, `requirement_entities` auto-created = 6 (+ es-departure's topics).
3. **Real run:** `dry_run=false` with the founder-held `OTTO_LOADER_TOKEN` (`x-otto-token` header). Idempotent — safe to re-run.
4. Confirm the 6 auto-created entities have correct `title` / `domain_area`; spot-check inserted rows keep `status: pending`.

**Acceptance:** dry-run counts == sim; real-run inserts == dry-run; rows land `pending`; re-run inserts zero (idempotency).
**Owner:** Romain / you-with-token. **Depends on:** Phase 1 sign-off, Phase 3 (fresh collision check), **and Phase 5 ready** (so promoted data is served correctly, not wrongly).

### Phase 5 — Wire the serving layer (the S1 + A3 payoff) 🔴
**Objective:** Make the serving layer *use* the fields the batch went to such trouble to carry. **This is the highest-value code work.**
**Steps** (targets confirmed by grep)
1. `backend/app/routers/requirement_facts.py` + `backend/app/services/requirements_sufficiency.py`: when deciding whether a requirement applies to a mover, key on `applies_to.nationality_scope_basis`:
   - `nationality_determined` → gate by nationality as today;
   - `audience_scope` → **applies to everyone on the corridor** (do not hide from an EEA mover).
2. Render `assertion_mode: conditional` records with their `conditional_on` wording (the A3 visa-required question stays conditional; never assert a nationality *is* visa-required).
3. Surface the 16 `non_obvious: true` records via the existing "easy-to-miss trap" pattern (precedent already in the branch's CSEP roadmap commits).
4. TDD against `docs/esie-andrea-golden-fixture.md`; keep `check_serving_llm_isolation` green (no LLM in the serving path).

**Acceptance:** golden-fixture test proves an EEA mover still sees the 17 `audience_scope` rules (Emergency Tax, PPSN, etc.); no record asserts unconditional visa-required; serving-isolation guard green.
**Owner:** me (Claude Code / dev-queue) → your review. **Depends on:** Phase 1 (schema of the fields is fixed).

### Phase 6 — Editorial reconciliation (dedup the representations) 🔴
**Objective:** Decide which representation a corridor actually serves. ES→IE now exists in **four** places: this `docs/imports` NDJSON (namespace `ES-IE:thirdcountry:*`), the 08-21 `data/corridor-facts/*.jsonl` batches already on the branch, the curated `data/corridor-facts/es-ie.json`, and ~52 live `requirement_facts` rows at lower nationality precision.
**Steps**
1. Extend the Phase 3 tool into an **overlap auditor**: cross-reference all four sources by `(destination, topic, fact)` and emit a KEEP / SUPERSEDE / MERGE report.
2. Resolve the concrete conflict: existing `ES-IE:entry-visa:venezuela_visa_required` **asserts** visa-required, which this batch deliberately keeps conditional (A3). Decide which wins.
3. Apply the S1 lens to the ~52 live rows carrying `employee_profile: "all"` on requirements this batch shows are nationality-determined (otto's filed follow-up).

**Acceptance:** a signed-off canonical-source decision per topic; no double-serving of the same real-world requirement. **Owner:** Romain (curation) with my auditor. **Depends on:** Phase 3 tool.

### Phase 7 — Governance & workflow integration 🟢/🔴
**Objective:** Route the above through your normal pipeline and honour the review gate.
**Steps**
1. Intake Phases 2–6 as Notion AI Work Queue tasks with the tiers above (🟢 the CI/tooling, 🔴 promotion/serving/curation); fold in otto's two filed follow-up drafts.
2. **Lawyer gate:** nothing here may be served as legal/tax advice until review clears — `review_status: pending`, 6 records `needs_lawyer_review`, `assurance_status: not_started`. The 6 flagged records (permit/residence interaction, two-EU-permits, worldwide-income, post-departure tax) are the priority queue for a reviewer.

**Acceptance:** tasks exist and are tiered; a documented lawyer-review checkpoint gates promotion-to-advice. **Owner:** Romain.

---

## 4. Sequencing

```
Phase 0 (es-departure verify)
        └─▶ Phase 1 (land PR) ──┬─▶ Phase 2 (CI gate)
                                ├─▶ Phase 3 (collision tool) ──▶ Phase 6 (editorial audit)
                                └─▶ Phase 5 (serving wiring)  ──┐
                                                                ├─▶ Phase 4 (promote)  ← needs review sign-off + fresh collision check + serving ready
Phase 7 (Notion + lawyer gate) wraps all of it.
```
Critical path to *value* is **0 → 1 → 5 → 4**. Phases 2, 3, 6 harden and de-risk in parallel. Promotion (4) is deliberately last of the code phases: serving must be correct *before* the data goes live, or you promote a mis-served correctness bug.

## 5. Risks & mitigations
- **Branch divergence / old-main fork** → worktree off `origin/<branch>`, catch up before commit (Appendix A); rebase onto current main is a separate pre-merge task.
- **Stale export for collision check** → always re-export before a real loader run (Phase 3 note).
- **Gate ≠ loader drift** → allow-list equality test (Phase 2.3).
- **Two README versions in the wild** (19,936 vs 19,227 B) → ship the corrected 19,227-B one (already placed); it's the version that correctly says the gate now exists.
- **Serving mis-scope** → golden-fixture test is the gate on Phase 5, not code review alone.
- **Promotion is irreversible-ish** → dry-run + idempotency + `pending` status + human review before `expert_verified`.

## 6. Immediate next actions
1. **You:** upload the three es-departure files → I run Phase 0.
2. **You:** run the Appendix A landing sequence (or say the word and I'll place es-departure and hand you the finished commands + PR body).
3. **Me, in parallel, on your go:** build the Phase 2 CI job + Phase 3 collision tool as reviewable PRs; draft the Phase 5 serving change against the Andrea fixture.

---

## Appendix A — Landing sequence (worktree, non-destructive)

```bash
cd ~/Documents/GitHub/rolec
git fetch origin
# isolated worktree on the branch; your feat/aiq-1854 working tree is untouched
git worktree add /tmp/rolec-0719 fix/td-qa-services-batch-0719
cd /tmp/rolec-0719
git pull --ff-only origin fix/td-qa-services-batch-0719      # catch up the 3 commits

# files are already on disk in your main clone — copy them in:
mkdir -p docs/imports/es-ie-thirdcountry-requirements-2026-08-22
cp ~/Documents/GitHub/rolec/docs/imports/es-ie-thirdcountry-requirements-2026-08-22/* \
   docs/imports/es-ie-thirdcountry-requirements-2026-08-22/
cp ~/Documents/GitHub/rolec/scripts/check_otto_batches.py scripts/check_otto_batches.py
# + docs/imports/es-departure-2026-08-22/* once Phase 0 is done

python3 scripts/check_otto_batches.py --all      # expect both batches PASS, 0 failed

git add docs/imports/es-ie-thirdcountry-requirements-2026-08-22 \
        docs/imports/es-departure-2026-08-22 \
        scripts/check_otto_batches.py
git commit -m "feat(imports): land ES→IE destination + origin Otto batches + delivery gate (files only)"
git push origin HEAD:fix/td-qa-services-batch-0719
gh pr create --base main --head fix/td-qa-services-batch-0719 \
  --title "ES→IE corridor: destination + origin research batches + delivery gate (files only)" \
  --body-file /tmp/PR_BODY.md   # from Appendix B

cd ~/Documents/GitHub/rolec && git worktree remove /tmp/rolec-0719   # cleanup
```
> Do **not** `git stash -u` first — that would sweep the placed (untracked) batch files. The worktree avoids touching your current working tree at all.

## Appendix B — PR description skeleton
- **Summary:** ES→IE destination (38) + origin (28) fact batches, files only. Gate: destination 54/0, origin 60/0. *(paste both gate outputs)*
- **New in this diff:** `scripts/check_otto_batches.py` — the gate did not exist when the batches were built; review it as code. Mitigations: it rejects deliberately mutated batches; it is not tuned to one batch.
- **Reviewer judgement calls:** (es-departure) `destination_country: IE` with `ES-IE:exit:*` namespace though the facts are Spanish — rationale in README; (both) editorial overlap with `data/corridor-facts` + live rows is deferred to Phase 6, not resolved here.
- **Honest limits:** nothing lawyer-reviewed (`review_status: pending`, `verification_status: representative`); needs_lawyer_review on 6 (dest) + 11 (origin) records; 5 sede.madrid.es quotes couldn't be second-fetched (403 to bots); padrón records are Madrid-only.
- **Do not:** merge; promote to `requirement_facts` (files only).

## Appendix C — Loader dry-run (Phase 4, from the playbook)
```
POST https://<project>.supabase.co/functions/v1/otto-loader
  header  x-otto-token: <OTTO_LOADER_TOKEN>          # founder-held; not in this workspace
  body    { "manifest": "https://storage.googleapis.com/<bucket>/<path>/manifest.json",
            "dry_run": true, "tables": "requirement_facts,requirement_entities" }
# expect: requirement_facts.mapped_new = 38 (then 28), unrouted = 0, dup_existing = 0
# then re-issue with "dry_run": false
```
