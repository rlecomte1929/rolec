/**
 * PostHog deep-link builders (pure). Centralises the ingest→app host derivation so
 * the admin surfaces (Feedback diagnostics, Product metrics, Test-drive replays) link
 * out consistently. Ingest host is eu.i.posthog.com; the app where dashboards/replays
 * are viewed is eu.posthog.com — derive one from the other (same trick as TestDriveTab).
 */
import { env } from '../config/env';

/** App host where PostHog dashboards/replays are viewed. */
export function posthogAppHost(): string {
  return (env.posthogHost || 'https://eu.i.posthog.com').replace('.i.posthog.com', '.posthog.com');
}

/**
 * A person's PostHog page (their events + session recordings). PostHog person pages
 * are project-scoped, so include the project id when configured; otherwise fall back
 * to the bare /person path (PostHog resolves it against the default project).
 */
export function posthogPersonUrl(distinctId: string): string {
  const host = posthogAppHost();
  const pid = env.posthogProjectId;
  const id = encodeURIComponent(distinctId);
  return pid ? `${host}/project/${encodeURIComponent(pid)}/person/${id}` : `${host}/person/${id}`;
}

/**
 * The project's event activity view. Deep-links when VITE_POSTHOG_PROJECT_ID is set;
 * otherwise falls back to the app host (PostHog lands on the default project).
 */
export function posthogEventsUrl(): string {
  const host = posthogAppHost();
  const pid = env.posthogProjectId;
  return pid ? `${host}/project/${encodeURIComponent(pid)}/activity/explore` : host;
}
