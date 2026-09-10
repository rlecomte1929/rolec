import { z } from 'zod';

/**
 * Central, validated front-end environment config (AP-04 / TS-5).
 *
 * `import.meta.env.*` reads were previously scattered across ~50 files — some
 * via `import.meta as unknown as { env }` double-casts — with no validation, so
 * a missing/renamed VITE_ var surfaced as a deep runtime failure. This module
 * zod-parses the env ONCE into a typed, validated object. Import `env` from here
 * instead of touching `import.meta.env` directly.
 *
 * Required vars (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY) are asserted with a
 * clear startup error — this centralises the throw that previously lived in
 * api/supabase.ts. The anon key is public by design (subject to RLS); nothing
 * secret is exposed here. VITE_API_URL keeps its existing dev fallback.
 *
 * Read each key explicitly (not the whole `import.meta.env` object) so Vite can
 * statically inline the values at build time.
 */

const DEV = import.meta.env.DEV;
const PROD = import.meta.env.PROD;
const MODE = import.meta.env.MODE;

/** Empty string → undefined, so `.optional()` and required checks behave sanely. */
const optionalString = z.preprocess(
  (v) => (typeof v === 'string' && v.trim() === '' ? undefined : v),
  z.string().optional(),
);

const envSchema = z.object({
  VITE_API_URL: optionalString,
  VITE_API_BASE_URL: optionalString,
  VITE_SUPABASE_URL: z.string().min(1),
  VITE_SUPABASE_ANON_KEY: z.string().min(1),
  VITE_POSTHOG_KEY: optionalString,
  VITE_POSTHOG_HOST: optionalString,
  VITE_POSTHOG_PROJECT_ID: optionalString,
  VITE_ENABLE_PASSKEYS: optionalString,
});

const raw = {
  VITE_API_URL: import.meta.env.VITE_API_URL,
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL as string | undefined,
  VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
  VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY,
  VITE_POSTHOG_KEY: import.meta.env.VITE_POSTHOG_KEY as string | undefined,
  VITE_POSTHOG_HOST: import.meta.env.VITE_POSTHOG_HOST as string | undefined,
  VITE_POSTHOG_PROJECT_ID: import.meta.env.VITE_POSTHOG_PROJECT_ID as string | undefined,
  VITE_ENABLE_PASSKEYS: import.meta.env.VITE_ENABLE_PASSKEYS as string | undefined,
};

const parsed = envSchema.safeParse(raw);

// Under the test runner (vitest sets MODE='test') the VITE_ vars are typically
// unset; don't hard-fail there — unit tests mock the network/supabase layer.
// The startup assertion is what matters for the real dev/prod browser bundle.
const isTest = MODE === 'test';

if (!parsed.success && !isTest) {
  const missing = parsed.error.issues
    .map((i) => i.path.join('.'))
    .filter(Boolean)
    .join(', ');
  throw new Error(
    `[env] Missing or invalid required environment variables: ${missing}. ` +
      'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (see frontend/.env*).',
  );
}

const data = parsed.success
  ? parsed.data
  : ({ ...raw, VITE_SUPABASE_URL: raw.VITE_SUPABASE_URL ?? '', VITE_SUPABASE_ANON_KEY: raw.VITE_SUPABASE_ANON_KEY ?? '' } as z.infer<typeof envSchema>);

/** Validated, typed front-end environment. */
export const env = {
  /**
   * Backend base URL. Empty = same-origin `/api` (Vite proxies to :8000 in
   * dev). Do not default to http://localhost:8000 — a page on 127.0.0.1:PORT
   * then CORS-fails against localhost.
   */
  apiUrl: data.VITE_API_URL ?? '',
  /** Provider-portal axios base URL (VITE_API_BASE_URL). */
  apiBaseUrl: data.VITE_API_BASE_URL ?? '',
  supabaseUrl: data.VITE_SUPABASE_URL,
  supabaseAnonKey: data.VITE_SUPABASE_ANON_KEY,
  posthogKey: data.VITE_POSTHOG_KEY,
  // TD-M2 (AIQ-1560): EU ingest host for GDPR fit (compliance-first brand). Render sets
  // VITE_POSTHOG_HOST=https://eu.i.posthog.com; the default matches so it's EU either way.
  posthogHost: data.VITE_POSTHOG_HOST ?? 'https://eu.i.posthog.com',
  /** Optional numeric PostHog project id — enables /project/{id}/... deep-links from admin. */
  posthogProjectId: data.VITE_POSTHOG_PROJECT_ID,
  /**
   * [AIQ-1491] Passkey sign-in + registration. OFF unless explicitly set to
   * 'true'. Passkeys additionally require the WebAuthn toggle to be enabled on
   * the Supabase project — while that is off, every passkey call fails, so the
   * UI must not be reachable. Absent this flag the button and the Settings
   * section do not render at all: a POC that ships a dead end to every user on
   * the login page is not "additive".
   */
  enablePasskeys: data.VITE_ENABLE_PASSKEYS === 'true',
  /** Vite-provided runtime flags. */
  isDev: DEV,
  isProd: PROD,
  mode: MODE,
} as const;

export type Env = typeof env;
