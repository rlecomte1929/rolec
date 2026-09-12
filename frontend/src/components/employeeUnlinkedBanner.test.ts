import { describe, it, expect } from 'vitest';
import {
  employeeUnlinkedActionCopy,
  employeeUnlinkedBannerClassName,
  employeeUnlinkedBannerHasPageEmptyState,
  UNLINKED_BANNER_DISMISS_KEY,
} from './employeeUnlinkedBanner';

describe('employeeUnlinkedActionCopy (AIQ-2287)', () => {
  it('does not send the user to the dashboard when they are already there', () => {
    expect(employeeUnlinkedActionCopy(true)).toMatch(/link case below/i);
    expect(employeeUnlinkedActionCopy(true)).not.toMatch(/dashboard/i);
  });

  it('points other employee pages at the dashboard', () => {
    expect(employeeUnlinkedActionCopy(false)).toMatch(/dashboard/i);
    expect(UNLINKED_BANNER_DISMISS_KEY).toBe('relopass_unlinked_banner_dismissed');
  });
});

describe('employeeUnlinkedBannerHasPageEmptyState (AIQ-2356)', () => {
  it('hides the banner on dashboard and case-scoped empty-state pages', () => {
    expect(employeeUnlinkedBannerHasPageEmptyState('/employee/dashboard')).toBe(true);
    expect(employeeUnlinkedBannerHasPageEmptyState('/employee/tasks')).toBe(true);
    expect(employeeUnlinkedBannerHasPageEmptyState('/employee/benefits')).toBe(true);
    expect(employeeUnlinkedBannerHasPageEmptyState('/services')).toBe(true);
    expect(
      employeeUnlinkedBannerHasPageEmptyState(
        '/employee/case/053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe/roadmap',
      ),
    ).toBe(true);
  });

  it('keeps the banner on pages without their own empty state', () => {
    expect(employeeUnlinkedBannerHasPageEmptyState('/employee/resources')).toBe(false);
    expect(employeeUnlinkedBannerHasPageEmptyState('/messages')).toBe(false);
  });
});

describe('employeeUnlinkedBannerClassName (AIQ-2293)', () => {
  it('uses navy info tokens, not amber warning', () => {
    expect(employeeUnlinkedBannerClassName).toContain('bg-navy-50');
    expect(employeeUnlinkedBannerClassName).toContain('text-navy-800');
    expect(employeeUnlinkedBannerClassName).not.toMatch(/amber/);
  });
});
