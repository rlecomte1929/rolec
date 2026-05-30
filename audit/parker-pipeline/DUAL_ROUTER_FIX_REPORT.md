# Dual-Layer Router Registration — Fix Report

**Scope:** Parker framework audit pipeline PRs #197–#206
**Driver:** Pre-merge audit [PR #207](https://github.com/rlecomte1929/rolec/pull/207) §9 — "Dual-layer router compliance"
**Date:** 2026-05-30
**Author:** automated fix pass (one branch per PR, no merges)

---

## Problem

`CLAUDE.md` defines a hard rule for the backend's dual-layer FastAPI architecture:

> Routers must be registered in **BOTH** `backend/main.py` **AND** `backend/app/main.py`. Render boots
> `uvicorn backend.main:app`, so a router registered only in `backend/app/main.py` returns **405 in
> production** — the modular app instance is never the one serving traffic.

The pre-merge audit (§9) found that **all 9 router-bearing Parker PRs** registered their router only in
the modular sub-app `backend/app/main.py`. Each would have shipped a route that 405s in production.

`backend/main.py` does **not** mount the modular app wholesale; it includes each modular router
individually (`from .app.routers import X as X_router` + `app.include_router(X_router.router)`). So the
fix is a mechanical 2-line mirror per PR.

## Fix

For each affected PR, on its own branch, two lines were added to `backend/main.py`:

1. An import, placed immediately after the existing `ai_decisions_router` import anchor:
   ```python
   from .app.routers import <mod> as <mod>_router  # [Parker-<X>] dual-layer registration (PR #207 §9)
   ```
2. An `include_router` call, placed immediately after the existing `ai_decisions_router` include anchor:
   ```python
   app.include_router(<mod>_router.router[, prefix="..."])  # [Parker-<X>] PR #207 §9 — dual-layer registration
   ```

The `prefix=` argument is added only where the modular registration used one (PR #200 / step D).

Each change is **+2 lines, `backend/main.py` only**. Mounting was verified for every PR by importing the
real production app and listing the new route(s):

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"
```

No tests, migrations, or other files were touched. **No PR was merged or rebased.**

---

## Per-PR results

| PR | Step | Branch | Module | Commit | Lines added | Mount-check output |
|----|------|--------|--------|--------|-------------|--------------------|
| [#197](https://github.com/rlecomte1929/rolec/pull/197) | A | `audit/parker-step-A-cox-survival` | `predictions` | `5d4a1908` | +2 | `['/api/cases/{case_id}/predicted-duration']` |
| [#198](https://github.com/rlecomte1929/rolec/pull/198) | B | `audit/parker-step-B-benefit-optimizer` | `benefit_optimizer` | `31dd5f8a` | +2 | `['/api/hr/{company_id}/optimize-benefit-mix']` |
| #199 | C | `audit/parker-step-C-cluster-tiering` | — | — | — | **SKIPPED — no router in this PR** |
| [#200](https://github.com/rlecomte1929/rolec/pull/200) | D | `audit/parker-step-D-prompt-registry` | `admin_prompts` | `7ac7fce8` | +2 | `['/api/admin/prompts', '/api/admin/prompts/{task_key}', '/api/admin/prompts/{task_key}/canary-share', '/api/admin/prompts/{version_id}/promote']` |
| [#201](https://github.com/rlecomte1929/rolec/pull/201) | E | `audit/parker-step-E-rlhf-lite` | `ai_feedback` | `c68b5a74` | +2 | `['/api/ai/feedback']` |
| [#202](https://github.com/rlecomte1929/rolec/pull/202) | F | `audit/parker-step-F-passport-ocr-oss` | `admin_ocr_shadow` | `ebb47d70` | +2 | `['/api/admin/ocr-shadow-comparison']` |
| [#203](https://github.com/rlecomte1929/rolec/pull/203) | G | `audit/parker-step-G-carbon-tco` | `admin_ai_unit_economics` | `bfc777ae` | +2 | `['/api/admin/ai-unit-economics']` |
| [#204](https://github.com/rlecomte1929/rolec/pull/204) | H | `audit/parker-step-H-conjoint` | `conjoint` | `e326e35f` | +2 | `['/api/hr/{company_id}/conjoint/studies', '/api/hr/{company_id}/conjoint/studies/{study_id}/fit', '/api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set', '/api/hr/{company_id}/conjoint/studies/{study_id}/responses', '/api/hr/{company_id}/conjoint/studies/{study_id}/results']` |
| [#205](https://github.com/rlecomte1929/rolec/pull/205) | I | `audit/parker-step-I-translation` | `translation` | `8027da6d` | +2 | `['/api/translate']` |
| [#206](https://github.com/rlecomte1929/rolec/pull/206) | J | `audit/parker-step-J-nlg-variety` | `nlg` | `4581221e` | +2 | `['/api/hr/{company_id}/exec-summary', '/api/policies/{policy_id}/tldr']` |

**Note on #200 (D):** the include line carries `, prefix="/api/admin"` because the modular registration
in `backend/app/main.py` used that prefix (the router's own `APIRouter(prefix="/prompts")` makes the full
path `/api/admin/prompts`). All other PRs needed no prefix argument.

---

## Verification method

For each PR the mount check imports `backend.main` — i.e. the exact module Render serves
(`uvicorn backend.main:app`) — and asserts the new route path(s) appear in `app.routes`. A successful,
non-empty result proves the router is now reachable in the production app instance, not only in the
modular sub-app. The import itself also exercises the whole monolith's import graph, so an import error
introduced by the new line would have surfaced here; none did.

## Out of scope (deliberately not done here)

Per the task definition, the following were **not** addressed in this pass and remain open:

- **D×G conflict resolution** — PRs #200 and #203 both touch `ai_trace_logger.py` and `database.py`
  (audit §5). Not resolved here.
- **Integration branch / merge order** — no integration branch was created (audit §8 recommendation).
- **Merging** — no PR was merged. Each branch now carries an independently-correct registration so it can
  be merged on its own once conflicts and ordering are handled separately.

Each affected PR has a comment linking back to PR #207 §9 and citing its fix commit.
