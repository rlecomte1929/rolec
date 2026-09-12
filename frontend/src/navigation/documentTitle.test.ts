import { describe, expect, it } from 'vitest';
import { formatAdminDocumentTitle, formatAuthDocumentTitle } from './documentTitle';

describe('formatAdminDocumentTitle', () => {
  it('names the screen after ReloPass admin', () => {
    expect(formatAdminDocumentTitle('Today')).toBe('ReloPass admin — Today');
  });

  it('falls back when the screen name is missing', () => {
    expect(formatAdminDocumentTitle()).toBe('ReloPass admin');
    expect(formatAdminDocumentTitle('  ')).toBe('ReloPass admin');
  });
});

describe('formatAuthDocumentTitle', () => {
  it('uses Sign in for the login screen', () => {
    expect(formatAuthDocumentTitle('login')).toBe('ReloPass — Sign in');
  });

  it('names register and invite separately', () => {
    expect(formatAuthDocumentTitle('register')).toBe('ReloPass — Create account');
    expect(formatAuthDocumentTitle('invite')).toBe('ReloPass — Set password');
  });
});
