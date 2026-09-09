import { describe, it, expect } from 'vitest';
import { companiesEmptyCopy } from '../CompaniesV2';

describe('companiesEmptyCopy', () => {
  it('explains Issues only with zero matches', () => {
    expect(
      companiesEmptyCopy({ loading: false, issuesOnly: true, anyFilter: true }),
    ).toMatch(/No registry issues/i);
  });

  it('does not look like an empty tenant list while loading', () => {
    expect(companiesEmptyCopy({ loading: true, issuesOnly: false, anyFilter: false })).toBe(
      'Loading companies…',
    );
  });
});
