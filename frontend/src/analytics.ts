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
