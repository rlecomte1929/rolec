import { describe, expect, it } from 'vitest';
import { caseCodeForDisplay } from './caseCode';

describe('caseCodeForDisplay (BUG-260804-1BA9)', () => {
  it('returns the assignment id unchanged so Copy matches the label', () => {
    const id = '8f3c2a11-1111-4bcd-8e22-abcdef012345';
    expect(caseCodeForDisplay(id)).toBe(id);
  });

  it('treats blank as empty', () => {
    expect(caseCodeForDisplay('  ')).toBe('');
    expect(caseCodeForDisplay(null)).toBe('');
  });
});
