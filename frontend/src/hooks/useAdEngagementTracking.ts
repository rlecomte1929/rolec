import { useEffect, useRef } from 'react';
import { emitMarketingEvent } from '../analytics';

/**
 * [AIQ-1783] Scroll-depth and dwell tracking for the paid-ad landing pages.
 *
 * Cold ad traffic converts too sparsely to read conversion alone early in a campaign,
 * so engagement is the only signal available to tell "wrong audience" from "right
 * audience, wrong page". Thresholds (50% depth, 30s dwell) come from the task.
 *
 * Each event fires AT MOST ONCE per page view — the whole point is a per-visit signal,
 * and a scroll handler that re-fires on every wheel tick would drown the funnel table
 * and burn the endpoint's rate limit (120/hour).
 *
 * Fail-soft: analytics must never surface an error on a page we are paying for clicks
 * on. Every call swallows its rejection.
 */

const SCROLL_THRESHOLD_PCT = 50;
const DWELL_THRESHOLD_MS = 30_000;

export function useAdEngagementTracking(page: string): void {
  // Refs, not state: firing these must never trigger a re-render of the page.
  const scrollFired = useRef(false);
  const dwellFired = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined') return; // SSR/prerender: no-op

    const params = new URLSearchParams(window.location.search);
    const utm = {
      utm_source: params.get('utm_source') || undefined,
      utm_campaign: params.get('utm_campaign') || undefined,
      utm_medium: params.get('utm_medium') || undefined,
      // [AIQ-1784] The creative angle (A1-A6 / B1-B2). Engagement per angle is the only
      // readable signal early in a campaign, before conversions are dense enough to
      // compare — so it has to be on these events, not just on conversions.
      utm_content: params.get('utm_content') || undefined,
    };

    // emitMarketingEvent already fans out to PostHog AND the server-side
    // analytics_events sink, and is best-effort internally — no extra catch needed.
    const send = (event: string, extra: Record<string, unknown>) => {
      emitMarketingEvent(event, { page, ...utm, ...extra });
    };

    const onScroll = () => {
      if (scrollFired.current) return;
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - window.innerHeight;
      // A page shorter than the viewport has nothing to scroll; treat it as fully
      // seen rather than reporting 0% forever.
      const pct = scrollable <= 0 ? 100 : ((window.scrollY || 0) / scrollable) * 100;
      if (pct >= SCROLL_THRESHOLD_PCT) {
        scrollFired.current = true;
        window.removeEventListener('scroll', onScroll);
        send('landing_scroll_depth', { depth: SCROLL_THRESHOLD_PCT });
      }
    };

    const dwellTimer = window.setTimeout(() => {
      if (dwellFired.current) return;
      dwellFired.current = true;
      send('landing_time_on_page', { seconds: DWELL_THRESHOLD_MS / 1000 });
    }, DWELL_THRESHOLD_MS);

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // evaluate once on mount for short pages / restored scroll position

    return () => {
      window.removeEventListener('scroll', onScroll);
      window.clearTimeout(dwellTimer);
    };
  }, [page]);
}
