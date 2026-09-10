import { Page } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Log in through the real ReloPass login form so every auth artefact the app
 * relies on (the `relopass_token` session token, role, Supabase mirror) is set
 * exactly as in production — more robust than injecting localStorage by hand.
 *
 * Creds default to the demo employee and can be overridden via env.
 */
export const EMPLOYEE_EMAIL = process.env.E2E_EMPLOYEE_EMAIL || 'employee@testingapril.com';
const EMPLOYEE_PASSWORD = process.env.E2E_EMPLOYEE_PASSWORD || 'EmpPass!1';

export async function loginAsEmployee(page: Page): Promise<void> {
  await page.goto('/login');
  await page.locator('#auth-login-identifier').fill(EMPLOYEE_EMAIL);
  await page.locator('#auth-login-password').fill(EMPLOYEE_PASSWORD);
  await page.locator('#auth-login-password').press('Enter');
  // The login round-trip persists the ReloPass session token; gate on it before
  // navigating so we never race the auth context.
  await page.waitForFunction(() => !!localStorage.getItem('relopass_token'), undefined, {
    timeout: 20_000,
  });
}

export type Role = 'EMPLOYEE' | 'HR' | 'ADMIN';

/**
 * QG-5b: "log in" WITHOUT a backend by seeding the localStorage auth artefacts the
 * client-side route guards read (relopass_token + relopass_role). Set via
 * addInitScript so they exist BEFORE the app's first render — the guard then sees
 * the role and allows the route. Pair with mockApi() to feed page data. For a real
 * end-to-end login (live mode), use loginAsEmployee above instead.
 */
export async function seedAuth(
  page: Page,
  role: Role = 'EMPLOYEE',
  // Spaces are intentional: never a real token (the guard only checks presence +
  // role), and they keep gitleaks' generic-api-key heuristic from flagging it.
  token = 'e2e seeded session',
): Promise<void> {
  await page.addInitScript(
    ([r, t]) => {
      localStorage.setItem('relopass_token', t);
      localStorage.setItem('relopass_role', r);
      localStorage.setItem('relopass_user_id', 'e2e-user');
      localStorage.setItem('relopass_email', 'e2e@test.relopass');
      localStorage.setItem('relopass_username', 'e2e');
      localStorage.setItem('relopass_name', 'E2E User');
      // AIQ-1711 welcome gate. `useWelcomeRedirect` runs on the role home's mount and
      // navigates to /<role>/welcome whenever `hasSeenWelcome(relopass_user_id)` is
      // false — which it always is in a fresh context, because the flag is normally
      // mirrored from `profiles.welcome_seen_at` by `useAuth.setSession`, and seedAuth
      // deliberately bypasses the login path that calls it.
      //
      // That made every seedAuth-based dashboard assertion a RACE against a useEffect:
      // catch the render first and it passes, lose and the page is the onboarding
      // screen with no `#employee-hub-linked-assignments` in the DOM at all. It failed
      // by run ORDER, not by change — a11y.axe.spec.ts running first was enough to flip
      // it, which is why it read as "the dependency bump broke E2E" on an innocent PR.
      //
      // seedAuth means "a logged-in returning user", and a returning user has seen the
      // welcome. welcome.persistence.spec.ts is unaffected: it drives the real login
      // form precisely because seedAuth skips setSession.
      localStorage.setItem('relopass_welcome_seen_e2e-user', '1');
    },
    [role, token] as const,
  );
}

/** Roles exercised by the live authenticated-portal suite (QG-AUTH). */
export const PORTAL_ROLES = ['ADMIN', 'HR', 'EMPLOYEE'] as const;

/**
 * Per-role credentials, read at CALL time (after playwright.config.ts has run
 * loadTestEnv()) so `.env.test` values are visible. Employee falls back to the
 * module defaults above to preserve the existing live-mode behaviour.
 */
function credsFor(role: Role): { email?: string; password?: string } {
  switch (role) {
    case 'ADMIN':
      return { email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD };
    case 'HR':
      return { email: process.env.E2E_HR_EMAIL, password: process.env.E2E_HR_PASSWORD };
    case 'EMPLOYEE':
      return {
        email: process.env.E2E_EMPLOYEE_EMAIL || EMPLOYEE_EMAIL,
        password: process.env.E2E_EMPLOYEE_PASSWORD || EMPLOYEE_PASSWORD,
      };
  }
}

/**
 * Log in as any role through the real login form (same artefacts as loginAsEmployee).
 * Used by portals/auth.setup.ts to mint each role's reusable session.
 */
export async function loginAs(page: Page, role: Role): Promise<void> {
  const { email, password } = credsFor(role);
  if (!email || !password) {
    throw new Error(
      `Missing credentials for ${role}. Set E2E_${role}_EMAIL / E2E_${role}_PASSWORD ` +
        `in frontend/.env.test (see frontend/.env.test.example).`,
    );
  }
  await page.goto('/login');
  await page.locator('#auth-login-identifier').fill(email);
  await page.locator('#auth-login-password').fill(password);
  await page.locator('#auth-login-password').press('Enter');
  await page.waitForFunction(() => !!localStorage.getItem('relopass_token'), undefined, {
    timeout: 20_000,
  });
}

// Config/specs load as native ESM here — derive the dir from import.meta, not __dirname.
const AUTH_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../playwright/.auth',
); // → frontend/playwright/.auth

/** Path to a role's persisted Playwright storageState (gitignored). */
export function authFile(role: Role): string {
  return path.join(AUTH_DIR, `${role.toLowerCase()}.json`);
}
