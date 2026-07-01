import posthog from 'posthog-js';
import { env } from './config/env';

let enabled = false;

export function initAnalytics(): void {
  const key = env.posthogKey;
  if (!key) return;

  const host = env.posthogHost;
  posthog.init(key, {
    api_host: host,
    capture_pageview: true,
    persistence: 'localStorage+cookie',
    autocapture: false,
  });
  enabled = true;
}

export function track(event: string, properties?: Record<string, unknown>): void {
  if (!enabled) return;
  posthog.capture(event, properties);
}

/**
 * Register super-properties that ride along on every subsequent event in the
 * session (persisted by PostHog). Used to split events by A/B arm — e.g. the
 * resolved `hr_inference_onboarding` variant so PR-A's HR onboarding events
 * (AIQ-1223b) can be segmented by arm. No-op without an analytics key.
 */
export function registerSuperProperties(properties: Record<string, unknown>): void {
  if (!enabled) return;
  posthog.register(properties);
}

/** Emit a marketing funnel event to BOTH PostHog and the server-side
 *  analytics_events sink (which the admin marketing dashboard reads). */
export function emitMarketingEvent(event: string, properties?: Record<string, unknown>): void {
  track(event, properties);
  try {
    const base = env.apiUrl;
    void fetch(`${base}/api/public/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, properties: properties || {} }),
      keepalive: true,
    });
  } catch {
    /* best-effort */
  }
}

/** Read utm_source / utm_campaign from the current URL. */
export function readUtm(): { utm_source?: string; utm_campaign?: string } {
  const usp = new URLSearchParams(window.location.search);
  return {
    utm_source: usp.get('utm_source') || undefined,
    utm_campaign: usp.get('utm_campaign') || undefined,
  };
}
