/**
 * P2-08a (AIQ-702) — staleness helper with per-tier thresholds.
 *
 * Pure-function shared truth for "is this data stale?" decisions, so the UI
 * badge and the backend alerts agree. Thresholds are per-rule-tier and come
 * from the VITE_STALENESS_THRESHOLDS_DAYS env var (JSON), with hardcoded
 * fallback defaults.
 *
 * Mirrors backend/app/services/staleness.py — same tier names, same defaults,
 * same "age in whole days >= threshold" semantics.
 *
 * Env format (override the defaults):
 *   VITE_STALENESS_THRESHOLDS_DAYS='{"tier1_critical":30,"tier1_stable":60,"tier2":90}'
 *
 * Semantics: at exactly N days old (where N is the tier threshold) the record
 * is the first day stale.
 */

export type Tier = 'tier1_critical' | 'tier1_stable' | 'tier2';

export const DEFAULT_THRESHOLDS_DAYS: Readonly<Record<Tier, number>> = Object.freeze({
  tier1_critical: 30,
  tier1_stable: 60,
  tier2: 90,
});

export const ENV_VAR = 'VITE_STALENESS_THRESHOLDS_DAYS';

export interface StalenessConfig {
  readonly thresholdsDays: Readonly<Record<Tier, number>>;
}

const ALL_TIERS: ReadonlyArray<Tier> = ['tier1_critical', 'tier1_stable', 'tier2'];

function parseEnvJson(raw: string): Partial<Record<Tier, number>> | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // eslint-disable-next-line no-console
    console.warn(`staleness: ${ENV_VAR} is not valid JSON; using defaults`);
    return null;
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    // eslint-disable-next-line no-console
    console.warn(`staleness: ${ENV_VAR} must be a JSON object; using defaults`);
    return null;
  }
  const result: Partial<Record<Tier, number>> = {};
  for (const tier of ALL_TIERS) {
    const v = (parsed as Record<string, unknown>)[tier];
    if (v === undefined) continue; // missing → fall back per-tier
    if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) {
      // eslint-disable-next-line no-console
      console.warn(
        `staleness: ${ENV_VAR}.${tier} must be a non-negative integer (got ${String(v)}); using default`,
      );
      continue;
    }
    result[tier] = v;
  }
  return result;
}

export function loadConfig(env?: Record<string, string | undefined>): StalenessConfig {
  // import.meta.env is the Vite source; tests can pass an explicit env map.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const source: Record<string, string | undefined> = env ?? ((import.meta as any)?.env ?? {});
  const raw = source[ENV_VAR];
  if (!raw) return { thresholdsDays: { ...DEFAULT_THRESHOLDS_DAYS } };

  const parsed = parseEnvJson(raw);
  if (parsed === null) return { thresholdsDays: { ...DEFAULT_THRESHOLDS_DAYS } };

  return {
    thresholdsDays: {
      tier1_critical: parsed.tier1_critical ?? DEFAULT_THRESHOLDS_DAYS.tier1_critical,
      tier1_stable: parsed.tier1_stable ?? DEFAULT_THRESHOLDS_DAYS.tier1_stable,
      tier2: parsed.tier2 ?? DEFAULT_THRESHOLDS_DAYS.tier2,
    },
  };
}

// Module-level cache: read env once at import so callers don't re-parse.
const _CONFIG: StalenessConfig = loadConfig();

export function getConfig(): StalenessConfig {
  return _CONFIG;
}

function coerceDate(value: Date | string | number): Date {
  if (value instanceof Date) return value;
  if (typeof value === 'number') return new Date(value);
  if (typeof value === 'string') {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) throw new Error(`unparseable date: ${value}`);
    return d;
  }
  throw new Error(`unsupported lastUpdated type: ${typeof value}`);
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * Return true iff `lastUpdated` is at least `threshold(tier)` whole days old.
 *
 * - `now` is injectable for testing; defaults to `new Date()`.
 * - `config` is injectable to override the module-level (env-loaded) config.
 */
export function isStale(
  lastUpdated: Date | string | number,
  tier: Tier,
  now?: Date | string | number,
  config?: StalenessConfig,
): boolean {
  const cfg = config ?? _CONFIG;
  const threshold = cfg.thresholdsDays[tier];
  if (threshold === undefined) {
    throw new Error(`unknown tier: ${String(tier)}`);
  }

  const updated = coerceDate(lastUpdated);
  const reference = now === undefined ? new Date() : coerceDate(now);

  const ageDays = Math.floor((reference.getTime() - updated.getTime()) / MS_PER_DAY);
  return ageDays >= threshold;
}
