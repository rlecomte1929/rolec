import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementList } from '../RequirementList';
import type { RequirementItemDTO } from '../../../types';

vi.mock('../ImmigrationDisclaimer', () => ({ ImmigrationDisclaimer: () => null }));
vi.mock('../Citations', () => ({ Citations: () => null }));

const item = (over: Partial<RequirementItemDTO> = {}): RequirementItemDTO => ({
  id: '1', pillar: 'EMPLOYMENT', title: 'Tax deduction card (skattekort)', description: 'd',
  severity: 'BLOCKER', owner: 'EMPLOYEE', requiredFields: [], statusForCase: 'MISSING',
  citations: [], ...over,
});

describe('RequirementList non-obvious flag', () => {
  it('flags a non-obvious requirement and states when it bites', () => {
    render(
      <RequirementList
        items={[item({ nonObvious: true, timing: 'before first salary payment' })]}
      />,
    );
    expect(screen.getByText('Easy to miss')).toBeTruthy();
    expect(screen.getByTestId('requirement-timing').textContent).toContain(
      'before first salary payment',
    );
  });

  // The null case is the one that regresses silently: if the badge ever renders
  // unconditionally, every ordinary requirement starts claiming to be a hidden trap and
  // the flag stops meaning anything.
  it('renders neither when the fields are absent', () => {
    render(<RequirementList items={[item()]} />);
    expect(screen.queryByText('Easy to miss')).toBeNull();
    expect(screen.queryByTestId('requirement-timing')).toBeNull();
  });

  // null ("not modeled" — an engine-synthesised item with no catalog row) and false
  // ("modeled, and it is obvious") both stay unbadged, but for different reasons.
  it('does not flag an explicitly-obvious requirement', () => {
    render(<RequirementList items={[item({ nonObvious: false, timing: null })]} />);
    expect(screen.queryByText('Easy to miss')).toBeNull();
    expect(screen.queryByTestId('requirement-timing')).toBeNull();
  });

  it('shows timing on its own, without the flag', () => {
    render(<RequirementList items={[item({ timing: 'within 3 months of arrival' })]} />);
    expect(screen.queryByText('Easy to miss')).toBeNull();
    expect(screen.getByTestId('requirement-timing').textContent).toContain(
      'within 3 months of arrival',
    );
  });
});
