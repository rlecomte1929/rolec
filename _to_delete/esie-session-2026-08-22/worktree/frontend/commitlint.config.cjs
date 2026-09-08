/**
 * QG-11 (AIQ-1184): commitlint config — enforce Conventional Commits on local
 * commit messages via the `.githooks/commit-msg` hook (QG-7 runner).
 *
 * Lives in frontend/ because that's the only workspace where `npm ci` runs and
 * node_modules exists (root package.json is never installed) — same reason the
 * pre-commit/pre-push tooling is frontend-hosted. The hook runs commitlint from
 * frontend/, so this config (and the @commitlint/config-conventional `extends`)
 * resolves from frontend/node_modules.
 *
 * Plain config-conventional, no overrides: the repo's `type(scope): [TASK] desc`
 * subjects already satisfy it (local subjects are <100 chars — the ` (#NNN)` PR
 * suffix is appended server-side at squash-merge and the local hook never sees it).
 */
module.exports = {
  extends: ['@commitlint/config-conventional'],
};
