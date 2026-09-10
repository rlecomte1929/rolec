import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Load `frontend/.env.test` into `process.env` if the file exists.
 *
 * Zero-dependency on purpose (no `dotenv`) so we don't churn the lockfile — see the
 * `npm ci` lockfile-drift note in CLAUDE.md. A NO-OP when the file is absent, which
 * is the case in preview/PR CI, so the deterministic gate is untouched. Never
 * overrides a variable that is already set (real CI secrets win over the local file).
 *
 * `.env.test` holds throwaway QA credentials and is gitignored (`.env.*`). The
 * committed template is `frontend/.env.test.example`. See docs/e2e-live-portals.md.
 */
export function loadTestEnv(): void {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const file = path.resolve(here, '../../.env.test'); // → frontend/.env.test
  if (!fs.existsSync(file)) return;
  for (const raw of fs.readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (key && process.env[key] === undefined) process.env[key] = val;
  }
}
