#!/usr/bin/env node
/**
 * QG-7 (AIQ-1180): auto-activate the repo's pre-push hook on `npm ci` / `npm install`.
 *
 * Runs from frontend/ via the package.json `prepare` script. Points git at the
 * committed `.githooks/` directory (which holds pre-push, the frontend-build gate)
 * so a fresh clone is protected without the previous manual one-time
 * `git config core.hooksPath .githooks`. The hook itself degrades gracefully when
 * node_modules is missing (see .githooks/pre-push).
 *
 * No-op in CI (the build is already gated there) and outside a git checkout
 * (e.g. when the package is installed from a tarball).
 */
import { execFileSync } from 'node:child_process';

if (process.env.CI) {
  process.exit(0);
}

try {
  execFileSync('git', ['rev-parse', '--is-inside-work-tree'], { stdio: 'ignore' });
} catch {
  // Not a git checkout — nothing to wire.
  process.exit(0);
}

try {
  // core.hooksPath is resolved relative to the working-tree root, so ".githooks"
  // is correct even though this runs from frontend/.
  execFileSync('git', ['config', 'core.hooksPath', '.githooks'], { stdio: 'ignore' });
  console.log('[hooks] pre-push hook activated (core.hooksPath=.githooks)');
} catch {
  // Non-fatal: never let hook setup break an install.
}
