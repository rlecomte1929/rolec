import { afterEach, describe, expect, it } from 'vitest';
import {
  CONSENT_BANNER_ATTR,
  CONSENT_BANNER_OFFSET_VAR,
  FEEDBACK_OPEN_ATTR,
  publishConsentBannerMetrics,
  publishFeedbackOpen,
} from './chromeDock';

afterEach(() => {
  publishConsentBannerMetrics(null);
  publishFeedbackOpen(false);
});

describe('chromeDock', () => {
  it('publishes consent offset and clears it', () => {
    publishConsentBannerMetrics(88);
    expect(document.documentElement.getAttribute(CONSENT_BANNER_ATTR)).toBe('open');
    expect(document.documentElement.style.getPropertyValue(CONSENT_BANNER_OFFSET_VAR)).toBe('88px');
    publishConsentBannerMetrics(null);
    expect(document.documentElement.getAttribute(CONSENT_BANNER_ATTR)).toBeNull();
    expect(document.documentElement.style.getPropertyValue(CONSENT_BANNER_OFFSET_VAR)).toBe('');
  });

  it('toggles the feedback-open flag used to hide sibling FABs', () => {
    publishFeedbackOpen(true);
    expect(document.documentElement.hasAttribute(FEEDBACK_OPEN_ATTR)).toBe(true);
    publishFeedbackOpen(false);
    expect(document.documentElement.hasAttribute(FEEDBACK_OPEN_ATTR)).toBe(false);
  });
});
