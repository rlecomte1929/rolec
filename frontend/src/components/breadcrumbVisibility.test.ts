import { describe, it, expect } from 'vitest';
import { shouldShowAppShellBreadcrumb } from './breadcrumbVisibility';

describe('shouldShowAppShellBreadcrumb', () => {
  it('hides the trail on top-level pages with no parent or section (AIQ-2296)', () => {
    expect(shouldShowAppShellBreadcrumb(undefined)).toBe(false);
    expect(shouldShowAppShellBreadcrumb(undefined, '  ')).toBe(false);
  });

  it('keeps the trail when there is a parent page to go back to', () => {
    expect(shouldShowAppShellBreadcrumb({ label: 'Cases', href: '/hr/dashboard' })).toBe(true);
  });

  it('shows ReloPass / section / title when a section is passed (AIQ-2351)', () => {
    expect(shouldShowAppShellBreadcrumb(undefined, 'HR Operations')).toBe(true);
  });
});
