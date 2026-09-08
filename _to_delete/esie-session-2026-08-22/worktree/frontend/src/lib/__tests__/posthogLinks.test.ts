import { describe, it, expect } from 'vitest';
import { posthogAppHost, posthogPersonUrl, posthogEventsUrl } from '../posthogLinks';

describe('posthogLinks', () => {
  it('derives the app host from the ingest host', () => {
    // env.posthogHost defaults to eu.i.posthog.com under the test runner.
    expect(posthogAppHost()).toBe('https://eu.posthog.com');
  });

  it('builds a person page url (no project id needed)', () => {
    expect(posthogPersonUrl('abc 123')).toBe('https://eu.posthog.com/person/abc%20123');
  });

  it('falls back to the app host for events when no project id is configured', () => {
    // VITE_POSTHOG_PROJECT_ID is unset in tests → host root, not a /project/ deep-link.
    expect(posthogEventsUrl()).toBe('https://eu.posthog.com');
  });
});
