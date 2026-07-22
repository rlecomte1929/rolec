import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from './antigravity';
import { getAnalyticsConsent, grantAnalyticsConsent, revokeAnalyticsConsent } from '../analytics';
import { useIsAdmin } from '../features/admin/useIsAdmin';

/**
 * GDPR analytics consent banner.
 *
 * Analytics (PostHog) is opted OUT by default (see initAnalytics). This banner is
 * the opt-in surface: it appears once, only while the visitor has made no decision,
 * and gates whether product analytics + analytics cookies are captured at all.
 * Session recording of real users stays off regardless — recording is limited to
 * synthetic test-drive sessions. A returning visitor who has decided never sees it.
 */
export function ConsentBanner() {
  // AIQ-1660: hide the analytics-consent band on the admin profile only — internal
  // staff don't need the opt-in prompt on the admin console. Every other profile
  // (employee, HR, signed-out visitor) still sees it. Render-layer suppression only;
  // the consent state itself is untouched.
  const isAdmin = useIsAdmin();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (getAnalyticsConsent() === null) setVisible(true);
  }, []);

  if (isAdmin || !visible) return null;

  function handleAccept() {
    grantAnalyticsConsent();
    setVisible(false);
  }

  function handleDecline() {
    revokeAnalyticsConsent();
    setVisible(false);
  }

  return (
    <div
      role="dialog"
      aria-label="Analytics consent"
      aria-live="polite"
      className="fixed bottom-0 inset-x-0 z-50 border-t border-[#d7e2e8] bg-white shadow-lg"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-3 px-4 py-3 sm:flex-row sm:items-center">
        <p className="text-sm leading-relaxed text-[#0b2b43]">
          We use privacy-first product analytics to improve ReloPass. No personal data
          is included in the events we collect, and analytics data is stored on EU
          servers.{' '}
          <Link
            to="/privacy"
            className="font-medium text-[#1f8e8b] underline underline-offset-2 hover:text-[#197c79]"
          >
            Privacy policy
          </Link>
        </p>

        <div className="flex shrink-0 items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleDecline}>
            Decline
          </Button>
          <Button variant="primary" size="sm" onClick={handleAccept}>
            Accept analytics
          </Button>
        </div>
      </div>
    </div>
  );
}
