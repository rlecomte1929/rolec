import { describe, it, expect } from 'vitest';
import { draftToMembers } from './householdRoster';

describe('draftToMembers (ask-once household roster)', () => {
  it('always includes a self member, named from the assignment', () => {
    const members = draftToMembers(undefined, 'Marc Bouchard');
    expect(members).toHaveLength(1);
    expect(members[0]).toMatchObject({ id: 'self', kind: 'self', name: 'Marc Bouchard' });
  });

  it('falls back to "You" when no self name is provided', () => {
    expect(draftToMembers({}, undefined)[0].name).toBe('You');
  });

  it('adds a partner when a spouse name is present', () => {
    const members = draftToMembers({ spouse: { fullName: 'Isabelle Bouchard', dateOfBirth: '1985-03-15' } });
    const partner = members.find((m) => m.kind === 'partner');
    expect(partner).toMatchObject({ name: 'Isabelle Bouchard', dob: '1985-03-15' });
  });

  it('adds a partner from marital status even without a spouse name', () => {
    const members = draftToMembers({ maritalStatus: 'Married' });
    expect(members.some((m) => m.kind === 'partner')).toBe(true);
  });

  it('does NOT add a partner for single/divorced/widowed with no spouse', () => {
    for (const maritalStatus of ['Single', 'Divorced', 'Widowed']) {
      const members = draftToMembers({ maritalStatus });
      expect(members.some((m) => m.kind === 'partner')).toBe(false);
    }
  });

  it('maps children to stable index-based ids (c0, c1, …) with names + DOBs', () => {
    const members = draftToMembers({
      children: [
        { fullName: 'Léa', dateOfBirth: '2016-05-12' },
        { fullName: 'Hugo', dateOfBirth: '2019-10-28' },
      ],
    });
    const children = members.filter((m) => m.kind === 'child');
    expect(children.map((c) => c.id)).toEqual(['c0', 'c1']);
    expect(children[0]).toMatchObject({ name: 'Léa', dob: '2016-05-12' });
    expect(children[1]).toMatchObject({ name: 'Hugo', dob: '2019-10-28' });
  });

  it('builds the full Bouchard-style roster: self + partner + 2 children, no pets', () => {
    const members = draftToMembers(
      {
        maritalStatus: 'Married',
        spouse: { fullName: 'Isabelle Bouchard' },
        children: [
          { fullName: 'Léa', dateOfBirth: '2016-05-12' },
          { fullName: 'Hugo', dateOfBirth: '2019-10-28' },
        ],
      },
      'Marc Bouchard',
    );
    expect(members.filter((m) => m.kind === 'self')).toHaveLength(1);
    expect(members.filter((m) => m.kind === 'partner')).toHaveLength(1);
    expect(members.filter((m) => m.kind === 'child')).toHaveLength(2);
    expect(members.filter((m) => m.kind === 'pet')).toHaveLength(0);
  });
});
