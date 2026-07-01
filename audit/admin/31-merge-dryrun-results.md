# July 1 Merge Train — DRY RUN Results & Conflict-Resolution Playbook

> Executed: 2026-06-30 in a scratch worktree off `origin/main` (HEAD `0f14c760`).
> Nothing was pushed. This validates (and corrects) `30-july1-merge-plan.md` against
> the **actual** current `origin/main`, which has advanced since the plan was written.
> 26 open PRs total: 20 in the plan + 6 newer PRs the plan does not cover (#1228–#1233).

## TL;DR verdict — NOT fully mechanical

| Outcome | Count | PRs |
|---|---|---|
| Clean merge (no conflict) | 16 | #1163 #1207 #1210 #1215 #1217 #1218 #1219 #1220 #1221 #1213 #1214 #1216 #1222 #1228 #1229 #1230 |
| Conflict — MECHANICAL (scripted union, safe to automate) | 4 | #1200 #1231 #1232* #1233 |
| Conflict — SEMANTIC, NEEDS HUMAN | 4 | #1209 #1224 #1225 #1226 |
| Conflict — SEMANTIC, resolvable with provided recipe | 1 | #1223 |

\*#1232 only conflicts if #1231 isn't merged first (it's stacked on #1231); merge p1→p2→p3 in order and #1232 is clean.

**Bottom line:** Waves 1–3, Wave 8, and the post-plan infra PRs are mechanical
(two of them need a scripted "keep-both" union). **Two areas need a human:**
(1) #1209 EU Blue Card ground-truth fixtures, and (2) the assistant slice chain
#1223–#1226, which the plan wrongly assumed stacks cleanly.

---

## Conflict hotspots (files touched by 2+ conflicting PRs)

| File | Conflicting PRs | Nature | Resolution |
|---|---|---|---|
| `backend/app/services/rag_eval_reports.py` (`METRIC_SPECS` list + mock data dict) | #1200, #1230, #1233, **+ main #1212/#1205** | Each appends new `MetricSpec(...)` rows + mock series at the same list location | MECHANICAL — keep **all** blocks (union). Scriptable. |
| `frontend/src/features/immigration/ImmigrationAnswerPanel.tsx` | #1222, #1224, #1225, #1226 | Each **redefines the same `export function ImmigrationAnswerPanel({...})` signature** differently (`{caseContext}` vs `{caseId}` vs policy-bridge's expanded form) | SEMANTIC — human must build the **union prop signature** `{ caseContext, caseId, ... }` and merge each slice's body/request-wiring |
| `frontend/src/pages/employee/ImmigrationAssistantPage.tsx` | #1222, #1223, #1224, #1226 | Each rewrites the whole component (caseContext resolution / MoveAtAGlance / caseId / policy routing) | SEMANTIC — interleave all features (recipe below) |
| `frontend/src/App.tsx` + `frontend/src/navigation/routes.ts` | #1227 vs #1231 | Both add an admin lazy-import + `ROUTE_DEFS` entry + `<Route>` at the same spot (`adminAiControls` vs `adminMissionControl`) | MECHANICAL — keep both lines (union) |
| `backend/tests/fixtures/eligibility/{br_pt,us_fr}/ground_truth.json` | #1209 vs **main #1211** | Disagree on the eligibility verdict: main = `ELIGIBLE_WORK_PERMIT` (national permit citations); #1209 = `ELIGIBLE_BLUE_CARD` (`EU_DIR_2021_1883`) | SEMANTIC — **NEEDS HUMAN** domain decision |

---

## Why the plan is stale

The plan (written 2026-06-30) assumed Wave 1 is "fully isolated, any order." It is
not, because `origin/main` advanced **after** the plan with PRs that touch the same
files the Wave-1 branches do:

- **#1211** (`curate FR/PT eligibility citations`) rewrote the two eligibility
  `ground_truth.json` fixtures to `ELIGIBLE_WORK_PERMIT` — directly colliding with
  #1209's `ELIGIBLE_BLUE_CARD`.
- **#1212 / #1205 / #1194 / #1197** added metrics to `rag_eval_reports.py`'s
  `METRIC_SPECS` — colliding with #1200 (and later #1230, #1233).

These are conflicts with **main itself**, not between Wave-1 siblings — so they fire
no matter the intra-wave order.

---

## Per-PR results (in dry-run merge order)

### Wave 1
| PR | Branch | Result | Detail |
|---|---|---|---|
| #1163 | feat/aiq-945-corrections-digest | CLEAN | — |
| #1200 | eval-deepen | **CONFLICT — mechanical (RESOLVED)** | `rag_eval_reports.py`: both added `MetricSpec` rows (`answer_grounding`,`calibration_score`) at the list end vs main's `outcome_accuracy`/`structuring_accuracy`/`roadmap_completeness`. → **keep both blocks**. `test_admin_rag_eval.py`: main asserts metrics dynamically `{s.key for s in svc.METRIC_SPECS}`, eval-deepen hardcodes the set. → **take main's dynamic assertion** (auto-covers the union). |
| #1207 | frontend-hygiene | CLEAN | — |
| #1209 | feat/immigration-blue-card-regime | **CONFLICT — NEEDS HUMAN** | `…/eligibility/br_pt/ground_truth.json` & `…/us_fr/ground_truth.json`: verdict disagreement vs main #1211 (WORK_PERMIT vs BLUE_CARD). Domain call required — both PT and FR are EU so Blue Card is plausible, but #1211 deliberately curated WORK_PERMIT after #1209 branched. **Skipped in dry run.** |
| #1210 | frontend-ui-p0 | CLEAN | — |
| #1215 | fix/test-p3-xfail-db-layer | CLEAN | — |
| #1217 | feat/h3-corpus-coverage | CLEAN | — |
| #1218 | feat/h1-pii-mask-llm-egress | CLEAN | — |
| #1219 | feat/h4-test-evidence | CLEAN | — |
| #1220 | feat/aiq-515-extraction-harness | CLEAN | — |
| #1221 | docs/admin-profile-audit | CLEAN | — |

### Wave 2
| #1213 | frontend-ui-comp2 | CLEAN | (antigravity barrel, applied first) |
| #1214 | frontend-ui-shell | CLEAN | (applied after #1213, as plan specifies) |

### Wave 3
| #1216 | feat/h2-provider-portal | CLEAN | backend/main.py + app/main.py |
| #1222 | frontend-assistant-mvp | CLEAN | adds `caseContext` prop to the panel |

### Wave 4 — #1223 assistant-snapshot — **CONFLICT, SEMANTIC (RESOLVED with recipe)**
`ImmigrationAssistantPage.tsx`. #1222 added corridor `caseContext` resolution +
passes `caseContext` to the panel; #1223 adds `<MoveAtAGlance caseId={primaryCaseId}/>`
and passes the panel **with no props** (clobbering #1222). The plan said #1223 "needs
#1222's prop plumbing" — true, but git can't compose them. **Resolution (validated,
compiles against the context API which exposes both `assignmentId` and `primaryCaseId`):**
keep #1222's `useEffect`/`caseContext`/`resolved` gating, add #1223's `MoveAtAGlance`
above the gated panel, destructure `{ assignmentId, primaryCaseId }`, render
`<MoveAtAGlance caseId={primaryCaseId}/>` then the `resolved ? <ImmigrationAnswerPanel caseContext={caseContext}/> : <loading>`.

### Waves 5–7 — assistant slice chain — **CONFLICT, SEMANTIC, NEEDS HUMAN**
Root cause (the plan's biggest miss): #1222/#1223/#1224/#1225/#1226 are each branched
**from main independently — they are NOT stacked on each other.** Verified by diffing
each against main: each one *only* contains its own feature and re-expresses the same
function signature / JSX. So every merge after #1222 collides on the same 1–2 files
and **cannot be mechanically unioned** — the panel's single `function` signature has
three incompatible forms.

| PR | Branch | Adds (vs main) | Conflict |
|---|---|---|---|
| #1224 | assistant-context-injection | panel signature → `{ caseId }`, adds `case_id` to request body; page passes `caseId` | Collides with #1222's `{ caseContext }` signature + #1223's MoveAtAGlance page. **NEEDS HUMAN:** union signature `{ caseContext, caseId }`. |
| #1225 | assistant-suggested-questions | +24 lines inside the panel (suggested-question chips) + test | Rides on the union panel; insertion point overlaps. **NEEDS HUMAN** (small). |
| #1226 | assistant-policy-bridge | panel +149/−27 (immigration↔policy routing) + page +5/−1 + 2 new api files | Largest rewrite of the panel. **NEEDS HUMAN.** |

**Playbook for the assistant chain:** do **not** `git merge` them slice-by-slice.
Instead, treat #1222–#1226 as one feature and hand-build a single reconciled
`ImmigrationAnswerPanel.tsx` + `ImmigrationAssistantPage.tsx`:
- Panel props: `{ caseContext?, caseId?, ... }` (union of all slices).
- Panel body: corridor prefill (#1222) + `case_id` in request (#1224) + suggested
  questions (#1225) + immigration/policy routing (#1226).
- Page: `MoveAtAGlance` (#1223) above a panel that receives **both** `caseContext`
  and `caseId`.
Then commit once. The api files in #1226 (`assistantRoute.ts`, `policyAssistantQuery.ts`)
are new/single-owner — no conflict.

### Wave 8 — #1227 feat/admin-hardening — **CLEAN** (plan over-predicted)
The plan called this the riskiest (3-way `backend/main.py`). In reality it merged
**clean**: #1224/#1225/#1226 don't touch the backend, and with #1216 + #1223 already
in the tree there is no 3-way `main.py` collision. `backend/main.py` and
`backend/app/main.py` both pass `ast.parse` after the merge. Migrations
(`20260817…`, `20260818…`) are above main's watermark — no collision.

### Post-plan PRs (#1228–#1233 — NOT in the merge plan; add a Wave 9)
| PR | Branch | Result | Detail |
|---|---|---|---|
| #1228 | fix/support-triage-keyerror | CLEAN | isolated backend fix |
| #1229 | feat/admin-bug-routine | CLEAN | stacked on #1227 — merge **after** #1227 |
| #1230 | assistant-routing-eval | CLEAN | adds `routing_accuracy` metric (but see #1233 — same list) |
| #1231 | mission-control-p1 | **CONFLICT — mechanical** | `routes.ts` + `App.tsx`: `adminMissionControl` route/import collides with #1227's `adminAiControls` at the same spot → **keep both** (validated: union resolved, p2 then merged clean). |
| #1232 | mission-control-p2 | CLEAN\* | Stacked on #1231 (`p1 ⊂ p2`). Clean once #1231 is merged first. |
| #1233 | mission-control-p3 | **CONFLICT — mechanical** | Stacked (`p2 ⊂ p3`); App.tsx/routes.ts already resolved via p1. Only real conflict: `rag_eval_reports.py` `METRIC_SPECS` — adds `triage_accuracy` colliding with #1200/#1230 additions → **keep both** (same union pattern as #1200). |

---

## Ordering corrections vs the plan

1. **Wave 1 is not order-free.** #1200 and #1209 conflict with **main** (post-plan
   commits #1211, #1205/#1212). Resolve #1200 with the scripted metric-list union;
   route #1209 to a human before its wave.
2. **Assistant slices do NOT stack.** #1223–#1226 are independent branches off main;
   merging them sequentially produces a cascade of signature conflicts on the same
   two files. Reconcile the whole chain by hand into one commit (recipe above), not
   five `git merge`s.
3. **#1227 is safe, not risky.** Downgrade it from "critical 3-way main.py" to clean,
   given #1216 + #1223 precede it.
4. **Add Wave 9 for #1228–#1233.** Order: #1228 (any), #1230 (any), #1229 (after
   #1227), then mission-control **#1231 → #1232 → #1233 strictly in sequence** (they
   are stacked). Apply the route-union (#1231) and metric-union (#1233) resolutions.

---

## Scriptable resolutions (safe to automate)

**A. `rag_eval_reports.py` METRIC_SPECS union** (covers #1200, #1233, and any future
metric PR): on conflict, drop only the `<<<<<<<`/`=======`/`>>>>>>>` marker lines —
keep both sides of each hunk (the lists are additive). Then in
`test_admin_rag_eval.py` always prefer the dynamic `{s.key for s in svc.METRIC_SPECS}`
assertion over any hardcoded set.

**B. `routes.ts` + `App.tsx` admin-route union** (covers #1227 vs #1231): drop only
the marker lines — both the `ROUTE_DEFS` entry and the lazy-import + `<Route>` are
additive at distinct keys.

Both A and B were applied in the dry run and left zero conflict markers; backend
files passed `ast.parse`.
