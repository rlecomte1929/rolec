import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementList } from '../RequirementList';
import type { RequirementItemDTO } from '../../../types';

vi.mock('../ImmigrationDisclaimer', () => ({ ImmigrationDisclaimer: () => null }));
vi.mock('../Citations', () => ({ Citations: () => null }));

const base: RequirementItemDTO = {
  id: '1',
  pillar: 'RESIDENCE',
  title: 'Long-stay work visa',
  description: 'Apply for the VLS-TS.',
  severity: 'BLOCKER',
  owner: 'EMPLOYEE',
  requiredFields: [],
  statusForCase: 'MISSING',
  citations: [],
};

const confirmation: RequirementItemDTO = {
  ...base,
  id: '2',
  title: 'No visa or residence permit required',
  description: 'ignored in favour of reason',
  statusForCase: 'CONFIRMED',
  outcomeType: 'nothing_to_do',
  reason:
    'You are a national of France. You have the right of entry and residence in your own country.',
};

describe('a nothing_to_do item is a positive ANSWER, not a pending task', () => {
  it('renders the reason — the only human-readable payload it has', () => {
    render(<RequirementList items={[confirmation]} />);
    expect(screen.getByText(/right of entry and residence/i)).toBeTruthy();
  });

  it('offers NO affordances — nothing is asked of the employee', () => {
    render(<RequirementList items={[confirmation]} onAction={vi.fn()} />);
    // Even WITH onAction wired, a "you need no visa" row must not invite an upload.
    expect(screen.queryByText('Upload')).toBeNull();
    expect(screen.queryByText('Mark Reviewed')).toBeNull();
    expect(screen.queryByText('Ask HR')).toBeNull();
  });

  it('does not render a status badge — CONFIRMED is not a task state', () => {
    render(<RequirementList items={[confirmation]} />);
    expect(screen.queryByText('CONFIRMED')).toBeNull();
  });

  it('is visually distinct from an action row', () => {
    render(<RequirementList items={[confirmation]} />);
    expect(screen.getByTestId('requirement-confirmation')).toBeTruthy();
  });
});

describe('action rows only offer actions that are wired', () => {
  it('renders no buttons when onAction is absent', () => {
    // No caller has ever passed onAction, so these four were dead no-ops sitting on
    // legally-consequential rows.
    render(<RequirementList items={[base]} />);
    expect(screen.queryByText('Upload')).toBeNull();
    expect(screen.queryByText('Mark Reviewed')).toBeNull();
  });

  it('renders them when onAction IS provided', () => {
    render(<RequirementList items={[base]} onAction={vi.fn()} />);
    expect(screen.getByText('Upload')).toBeTruthy();
    expect(screen.getByText('Mark Reviewed')).toBeTruthy();
  });

  it('still renders the normal row content', () => {
    render(<RequirementList items={[base]} />);
    expect(screen.getByText('Long-stay work visa')).toBeTruthy();
    expect(screen.getByText('MISSING')).toBeTruthy();
  });
});

describe('provenance', () => {
  it('marks hand-authored content as Representative', () => {
    // The EU establishment items are drafted, not corpus-derived. The badge already
    // existed and had simply never been fed real data.
    render(<RequirementList items={[{ ...base, verificationStatus: 'representative' }]} />);
    expect(screen.getByText('Representative')).toBeTruthy();
  });
});
