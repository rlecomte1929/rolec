/**
 * Shared chrome for the bottom-right product dock (Feedback, Setup, Policy FABs)
 * and the analytics consent band.
 *
 * One owner for stacking: consent sits above FABs; an open Feedback panel hides
 * sibling FABs so they cannot paint through the form (AIQ-2272).
 */
import { useEffect, useState } from 'react';

export const CONSENT_BANNER_ATTR = 'data-consent-banner';
export const CONSENT_BANNER_OFFSET_VAR = '--consent-banner-offset';
export const FEEDBACK_OPEN_ATTR = 'data-feedback-open';

export function publishConsentBannerMetrics(heightPx: number | null) {
  const root = document.documentElement;
  if (heightPx == null) {
    root.removeAttribute(CONSENT_BANNER_ATTR);
    root.style.removeProperty(CONSENT_BANNER_OFFSET_VAR);
    return;
  }
  root.setAttribute(CONSENT_BANNER_ATTR, 'open');
  root.style.setProperty(CONSENT_BANNER_OFFSET_VAR, `${heightPx}px`);
}

export function publishFeedbackOpen(open: boolean) {
  const root = document.documentElement;
  if (open) root.setAttribute(FEEDBACK_OPEN_ATTR, '');
  else root.removeAttribute(FEEDBACK_OPEN_ATTR);
}

export function useFeedbackOpen(): boolean {
  const [open, setOpen] = useState(() =>
    typeof document !== 'undefined' && document.documentElement.hasAttribute(FEEDBACK_OPEN_ATTR),
  );

  useEffect(() => {
    const root = document.documentElement;
    const apply = () => setOpen(root.hasAttribute(FEEDBACK_OPEN_ATTR));
    apply();
    const mo = new MutationObserver(apply);
    mo.observe(root, { attributes: true, attributeFilter: [FEEDBACK_OPEN_ATTR] });
    return () => mo.disconnect();
  }, []);

  return open;
}
