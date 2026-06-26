#!/usr/bin/env node
/**
 * QG-12 (AIQ-1185): dependency license-compliance gate.
 *
 * Fails CI when a PRODUCTION dependency carries a license that is neither on the
 * permissive allow-list nor a documented, reviewed exception — so a copyleft
 * (GPL/AGPL/…) or unknown license can't slip in unnoticed. Exceptions are pinned
 * to a specific version so a dependency bump re-triggers review.
 */
import checker from 'license-checker';

// SPDX identifiers we accept without review (the common permissive set + the
// license-OR-combos and font license currently present in the tree).
const ALLOWED = new Set([
  'MIT',
  'MIT*', // license-checker inferred MIT from package contents (e.g. posthog-js)
  'ISC',
  '0BSD',
  'Apache-2.0',
  'BSD-2-Clause',
  'BSD-3-Clause',
  'OFL-1.1', // SIL Open Font License (fonts) — permissive
  'MPL-2.0',
  '(MPL-2.0 OR Apache-2.0)',
  '(MIT OR WTFPL)',
  '(BSD-2-Clause OR MIT OR Apache-2.0)',
]);

// Reviewed, accepted exceptions (pinned to version — a bump re-triggers review).
const EXCEPTIONS = {
  'relopass-frontend@1.0.0':
    'our own private root package (no license field → UNKNOWN); not a third party',
  '@react-leaflet/core@2.1.0':
    'Hippocratic-2.1 — permissive ethical-source (MIT + use restrictions); map dependency, accepted',
  'react-leaflet@4.2.1': 'Hippocratic-2.1 — see @react-leaflet/core',
};

checker.init({ start: '.', production: true }, (err, pkgs) => {
  if (err) {
    console.error('[licenses] license-checker failed:', err);
    process.exit(2);
  }
  const violations = [];
  for (const [pkg, info] of Object.entries(pkgs)) {
    if (pkg in EXCEPTIONS) continue;
    const license = String(info.licenses);
    if (!ALLOWED.has(license)) violations.push(`${pkg} — ${license}`);
  }
  if (violations.length) {
    console.error(
      `[licenses] ${violations.length} production dep(s) with a disallowed/unknown license (review needed):`,
    );
    for (const v of violations) console.error('  ✗ ' + v);
    console.error(
      '\nIf the license is acceptable, add the SPDX id to ALLOWED or a pinned entry to EXCEPTIONS in frontend/scripts/check-licenses.mjs.',
    );
    process.exit(1);
  }
  console.log(
    `[licenses] OK — ${Object.keys(pkgs).length} production deps, all permissive or documented (${Object.keys(EXCEPTIONS).length} exceptions).`,
  );
});
