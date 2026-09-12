import { describe, it, expect } from 'vitest';
import { shouldShowAppShellBreadcrumb } from './breadcrumbVisibility';

describe('shouldShowAppShellBreadcrumb (AIQ-2296)', () => {
  it('hides the trail on top-level pages with no parent', () => {
    expect(shouldShowAppShellBreadcrumb(undefined)).toBe(false);
  });

  it('keeps the trail when there is a parent page to go back to', () => {
    expect(shouldShowAppShellBreadcrumb({ label: 'Cases', href: '/hr/dashboard' })).toBe(true);
  });
});
