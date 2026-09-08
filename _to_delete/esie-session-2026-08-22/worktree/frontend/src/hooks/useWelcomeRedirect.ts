import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { hasSeenWelcome } from '../utils/welcomeSeen';
import { getAuthItem } from '../utils/demo';

/**
 * Call at the TOP of the post-login landing page (HrDashboard / EmployeeJourney).
 * If the signed-in user has never seen their role's welcome page, redirect them
 * there once. Marking the welcome as seen (on skip/CTA) makes this a no-op on the
 * next mount, so there is no redirect loop.
 *
 * AIQ-1568: pass `{ skip: true }` when the user arrived with an explicit intent (e.g.
 * ?new=1 = "open the case form"). A first-run welcome should greet someone who just
 * logged in — it must not hijack a deliberate destination, or the CTA that sent them
 * here looks broken. This is the tail of TD-BUG-1: a dead route dumped users on this
 * page and the welcome redirect then bounced them to onboarding, so the whole thing
 * read as a loop.
 *
 * @param welcomeRoute '/hr/welcome' | '/employee/welcome'
 * @param opts.skip suppress the redirect for this mount (default false)
 */
export function useWelcomeRedirect(welcomeRoute: string, opts?: { skip?: boolean }): void {
  const navigate = useNavigate();
  const skip = opts?.skip ?? false;
  useEffect(() => {
    if (skip) return;
    const userId = getAuthItem('relopass_user_id') ?? '';
    if (userId && !hasSeenWelcome(userId)) {
      navigate(welcomeRoute, { replace: true });
    }
    // navigate + welcomeRoute are stable (react-router + constant literal),
    // so this runs once on mount.
  }, [navigate, welcomeRoute, skip]);
}
