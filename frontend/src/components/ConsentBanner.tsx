import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from './antigravity/Button';
import { getAnalyticsConsent, grantAnalyticsConsent, revokeAnalyticsConsent } from '../analytics';
import { useIsAdmin } from '../features/admin/useIsAdmin';

const CONSENT_BANNER_ATTR = 'data-consent-banner';
const CONSENT_BANNER_OFFSET_VAR = '--consent-banner-offset';

function publishConsentBannerMetrics(heightPx: number | null) {
  const root = document.documentElement;
  if (heightPx == null) {
    root.removeAttribute(CONSENT_BANNER_ATTR);
    root.style.removeProperty(CONSENT_BANNER_OFFSET_VAR);
    return;
  }
  root.setAttribute(CONSENT_BANNER_ATTR, 'open');
  root.style.setProperty(CONSENT_BANNER_OFFSET_VAR, `${heightPx}px`);
}

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
  // AIQ-1678: this banner mounts once at the app root (App.tsx), outside the route tree, so
  // it would otherwise keep the role it read at first mount. Logging in always navigates
  // (redirectByRole), so subscribing to location makes the admin-hide below re-evaluate
  // post-login — without it, an admin who signs in during the same page load keeps seeing it.
  useLocation();
  const isAdmin = useIsAdmin();
  const [visible, setVisible] = useState(false);
  const bannerRef = useRef<HTMLDivElement>(null);
  const show = visible && !isAdmin;

  useEffect(() => {
    if (getAnalyticsConsent() === null) setVisible(true);
  }, []);

  // AIQ-2272: publish height so the Feedback FAB lifts clear of this band,
  // and so stacking (z-[60]) always wins over the later-in-DOM widget.
  useEffect(() => {
    if (!show) {
      publishConsentBannerMetrics(null);
      return;
    }
    const el = bannerRef.current;
    const apply = () => publishConsentBannerMetrics(el?.offsetHeight ?? 96);
    apply();
    if (!el || typeof ResizeObserver === 'undefined') {
      return () => publishConsentBannerMetrics(null);
    }
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => {
      ro.disconnect();
      publishConsentBannerMetrics(null);
    };
  }, [show]);

  if (!show) return null;

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
      ref={bannerRef}
      role="dialog"
      aria-label="Analytics consent"
      aria-live="polite"
      className="fixed bottom-0 inset-x-0 z-[60] border-t border-[#d7e2e8] bg-white shadow-lg"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-3 px-4 py-3 sm:flex-row sm:items-center">
        <p className="text-sm leading-relaxed text-[#0b2b43]">
          We use privacy-first product analytics to improve ReloPass. No personal data
          is included in the events we collect, and analytics data is stored on EU
          servers.{' '}
          <Link
            to="/privacy"
            /* #1f8e8b is --rp-secondary from the PLATFORM palette and measures 3.96:1 on
               white — below AA. This banner is a public surface, so it takes the marketing
               accent (#197b78, 5.07:1). One node, but it renders on every public route via
               App.tsx, which is why an axe sweep reported it 12 times. */
            className="inline-flex min-h-6 items-center font-medium text-marketing-accent underline underline-offset-2 hover:text-[#167572]"
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
