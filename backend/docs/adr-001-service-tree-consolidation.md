# ADR-001: Consolidate backend/services/ into backend/app/services/

**Status:** Accepted
**Date:** 2026-05-26
**Authors:** AI (AUDIT-A9.2)
**Supersedes:** (none)

---

## Context

The ReloPass backend has two parallel service trees that have diverged over time:

| Tree | File count | Role |
|------|-----------|------|
| `backend/services/` | 155 Python files | Legacy location; created before the `app/` modular layer existed |
| `backend/app/services/` | 25 Python files | Canonical target; part of the intentional `app/` modular refactor |

This split creates several compounding problems:

1. **Import ambiguity.** 85 import lines inside `backend/app/` currently reach *back* into `backend/services/` (the opposite direction of the intended dependency graph). Any reader of the codebase must know both trees exist and must keep both in sync.
2. **Onboarding cost.** The split is not documented anywhere, so new contributors default to the wrong tree (the larger, older `backend/services/`).
3. **Tooling noise.** Static analysis, type checkers, and test coverage reports produce false negatives because they only track one of the two trees.
4. **Refactor drag.** Moving to a sub-package layout (e.g., `app/services/policy/`) is blocked until there is a single canonical tree.

The migration matrix for this consolidation is fully enumerated in
`backend/docs/services-migration-matrix.md` (generated AUDIT-A9.1, 2026-05-26).

---

## Decision

**All 155 Python files in `backend/services/` will be moved into `backend/app/services/`.**
`backend/services/` will be deleted after the migration is validated.

`backend/app/services/` is the canonical and only location for service modules
going forward. No new files should be added to `backend/services/` after this ADR
is accepted.

---

## Migration scope

Source: `backend/services/` — 155 files across 12 subdomains:

| Subdomain | Approx. file count |
|-----------|--------------------|
| `policy` | 69 |
| `analytics` | ~10 |
| `knowledge` | ~10 |
| `mobility` | ~10 |
| `infra` | ~8 |
| `provider/vendor` | ~8 |
| `auth` | ~6 |
| `hr` | ~6 |
| `assignment` | ~6 |
| `employee` | ~6 |
| `recommendations` | ~6 |
| `misc` | ~10 |

Full per-file inventory: see `backend/docs/services-migration-matrix.md`, Part 1.

Import sites that need updating: **85 lines** across `backend/app/` that currently
import from `backend.services.*` — full list in the migration matrix, Part 2.

The top 5 highest-churn modules (most import sites) are:

| Module | Import sites |
|--------|-------------|
| `supabase_client` | 29 |
| `audit_log_service` | 5 |
| `analytics_service` | 4 |
| `events_tracker` | 3 |
| `supabase_auth_sync` | 2 |

---

## Migration plan

Execution is performed in AUDIT-A9.3 on branch `audit/stage-1-security` as a
single atomic commit (no half-state in `main`).

Sequence:

1. **Copy files** — `cp` all 155 files (and the `resources/` sub-package via `cp -r`)
   from `backend/services/` into `backend/app/services/`. Do not delete the source
   tree yet.
2. **Update imports** — rewrite all 85 cross-import lines from
   `from backend.services.<module>` / `from services.<module>` to
   `from backend.app.services.<module>`. Use automated sed/grep pass, then verify
   with `grep -r "from backend.services\|from services\." backend/app/`.
3. **Update `__init__.py` re-exports** — ensure any `__init__.py` in
   `backend/services/` that re-exports symbols is mirrored or removed.
4. **Delete old tree** — `rm -rf backend/services/`.
5. **Validate** — run `cd backend && pytest` and confirm zero import errors.
6. **Commit** as a single PR commit; squash-merge to keep history clean.

---

## Rollback plan

Because the migration is a single atomic commit on a feature branch, rollback is
a simple `git revert <commit-sha>` or `git reset --hard HEAD~1` before the PR is
merged. The full `backend/services/` tree is recoverable from git history at any
point after the PR merge via `git checkout <pre-merge-sha> -- backend/services/`.

No database schema changes are involved; rollback has zero data risk.

---

## Consequences

**Positive:**
- Single canonical service tree. One import pattern (`from backend.app.services.<module>`).
- Eliminates the 85 reverse cross-imports that currently violate the `app/` dependency graph.
- Unblocks sub-package refactor (e.g., `app/services/policy/`).
- Simplifies CI coverage reporting and static analysis.

**Negative / mitigated:**
- Large diff (~155 files moved + 85 import sites updated). Mitigated by atomic single PR;
  no partial states exist in `main`.
- Code review is wide but shallow — reviewers need to verify import rewrites, not logic
  changes. A targeted review checklist will be provided in the AUDIT-A9.3 PR description.

---

## Known risks

1. **`policy_assistant_llm_client` collision.** `backend/services/policy_assistant_llm_client.py`
   may conflict with a new `llm_client.py` that exists or is planned in `backend/app/services/`.
   Resolution: rename `policy_assistant_llm_client.py` to keep its distinct name on move
   (no rename is needed if no collision exists — A9.3 must verify with
   `ls backend/app/services/llm_client.py` before copying).

2. **`resources/` sub-package.** `backend/services/resources/` is a sub-package (contains
   `__init__.py`). It must be moved with `cp -r`, not as individual files, and the destination
   `backend/app/services/resources/` must not already exist.

3. **`__init__.py` re-exports.** If `backend/services/__init__.py` re-exports symbols used
   elsewhere (outside `backend/app/`), those call sites must also be updated.
   A9.3 must grep for `from backend.services import` and `import backend.services` before
   deleting the old tree.

4. **Circular import risk.** After the move, any module in `backend/app/services/` that
   previously imported from `backend/services/` will now import from itself. Python's
   import system handles this correctly for flat modules, but `__init__.py` ordering matters
   if re-exports are involved.
