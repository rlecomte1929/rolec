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
 * @param welcomeRoute '/hr/welcome' | '/employee/welcome'
 */
export function useWelcomeRedirect(welcomeRoute: string): void {
  const navigate = useNavigate();
  useEffect(() => {
    const userId = getAuthItem('relopass_user_id') ?? '';
    if (userId && !hasSeenWelcome(userId)) {
      navigate(welcomeRoute, { replace: true });
    }
    // navigate + welcomeRoute are stable (react-router + constant literal),
    // so this runs once on mount.
  }, [navigate, welcomeRoute]);
}
