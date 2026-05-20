/**
 * platform-v2 feature flags.
 *
 * Each ported screen has its own flag. Convention follows the existing
 * `frontend/src/featureFlags.ts` (build-time env var, only the literal string
 * `'true'` enables) but adds a localStorage override so flags can be flipped
 * in the browser without a rebuild — essential for dogfooding and side-by-side
 * QA.
 *
 * Resolution order (first wins):
 *   1. localStorage[`platform_v2_<key>`] — `'on'` / `'off'`
 *   2. import.meta.env[`VITE_PLATFORM_V2_<KEY>`] — `'true'` = on
 *   3. default false
 *
 * To enable a flag for one user / one session, open DevTools console:
 *   localStorage.setItem('platform_v2_companies', 'on')
 * To clear:
 *   localStorage.removeItem('platform_v2_companies')
 *
 * To enable a flag for an environment, set the env var in Render (or
 * `.env.local` for dev). Once a flag is default-on for everyone, delete it
 * here AND delete the legacy code path it gated.
 */

export type V2FlagKey =
  // Phase 0 proof — read-only admin screen
  | 'companies'
  // Phase 1 — HR command center surface
  | 'mobility_control'
  | 'company_profile'
  | 'inbox'
  | 'employee_policy'
  // Phase 2 — policy stack (gated behind canonical-benefits decision)
  | 'policy_builder'
  | 'policy_reality'
  | 'exceptions'
  // Phase 3 — employee intake redesign
  | 'intake_detailed'
  | 'profile_rich'
  // Phase 4 — new schema work
  | 'requirements_discovery'
  | 'roadmap_tracks'
  // Phase 5 — admin polish
  | 'admin_overview';

const LS_PREFIX = 'platform_v2_';
const ENV_PREFIX = 'VITE_PLATFORM_V2_';

const ENV: Record<string, string | undefined> = (import.meta.env ?? {}) as Record<string, string | undefined>;

function readEnv(key: V2FlagKey): boolean {
  const raw = ENV[ENV_PREFIX + key.toUpperCase()];
  return typeof raw === 'string' && raw.trim().toLowerCase() === 'true';
}

function readLocalStorage(key: V2FlagKey): boolean | null {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try {
    const raw = window.localStorage.getItem(LS_PREFIX + key);
    if (raw === 'on') return true;
    if (raw === 'off') return false;
    return null;
  } catch {
    return null;
  }
}

export function isV2FlagOn(key: V2FlagKey): boolean {
  const ls = readLocalStorage(key);
  if (ls !== null) return ls;
  return readEnv(key);
}

export function setV2FlagOverride(key: V2FlagKey, value: boolean | null): void {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    if (value === null) window.localStorage.removeItem(LS_PREFIX + key);
    else window.localStorage.setItem(LS_PREFIX + key, value ? 'on' : 'off');
  } catch {
    /* ignore */
  }
}

export const V2_FLAGS: ReadonlyArray<V2FlagKey> = [
  'companies',
  'mobility_control',
  'company_profile',
  'inbox',
  'employee_policy',
  'policy_builder',
  'policy_reality',
  'exceptions',
  'intake_detailed',
  'profile_rich',
  'requirements_discovery',
  'roadmap_tracks',
  'admin_overview',
];
