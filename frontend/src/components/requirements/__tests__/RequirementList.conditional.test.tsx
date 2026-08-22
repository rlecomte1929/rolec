/**
 * AIQ-1969 — a conditional requirement renders WITH its condition, never as a flat claim.
 *
 * The failure: Andrea (ES→IE, EEA national) shown "you are exempt from Emergency Tax".
 * Relief is conditional on a PPS number AND a valid employer RPN.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RequirementList } from '../RequirementList';
import type { RequirementItemDTO } from '../../../types';

const CONDITION = 'you hold a PPS number and your employer has a valid RPN';

const item = (overrides: Partial<RequirementItemDTO> = {}): RequirementItemDTO =>
  ({
    id: 'r1',
    title: 'Emergency Tax',
    description: 'Emergency Tax does not apply once your job is registered.',
    pillar: 'EMPLOYMENT',
    severity: 'WARN',
    owner: 'EMPLOYEE',
    statusForCase: 'MISSING',
    citations: [],
    ...overrides,
  }) as RequirementItemDTO;

describe('RequirementList — conditional rendering', () => {
  it('renders the condition when assertionMode is conditional', () => {
    render(<RequirementList items={[item({ assertionMode: 'conditional', conditionalOn: CONDITION })]} />);
    expect(screen.getByTestId('requirement-condition')).toHaveTextContent('Applies only if:');
    expect(screen.getByTestId('requirement-condition')).toHaveTextContent(CONDITION);
  });

  it('renders the condition when only conditionalOn is present', () => {
    // Many catalog rows carry the condition text without the mode flag.
    render(<RequirementList items={[item({ conditionalOn: CONDITION })]} />);
    expect(screen.getByTestId('requirement-condition')).toHaveTextContent(CONDITION);
  });

  it('shows a caveat when the row is conditional but records no condition', () => {
    // Silence here would restate the claim as unconditional fact — the bug.
    render(<RequirementList items={[item({ assertionMode: 'conditional' })]} />);
    expect(screen.getByTestId('requirement-condition')).toHaveTextContent(
      'does not apply in every case',
    );
  });

  it('renders nothing for an unconditional requirement', () => {
    render(<RequirementList items={[item({ assertionMode: 'unconditional' })]} />);
    expect(screen.queryByTestId('requirement-condition')).toBeNull();
  });

  it('renders nothing when neither signal is present', () => {
    render(<RequirementList items={[item()]} />);
    expect(screen.queryByTestId('requirement-condition')).toBeNull();
  });

  it('treats a blank condition string as absent', () => {
    render(<RequirementList items={[item({ conditionalOn: '   ' })]} />);
    expect(screen.queryByTestId('requirement-condition')).toBeNull();
  });

  it('composes with the easy-to-miss badge', () => {
    render(
      <RequirementList
        items={[item({ assertionMode: 'conditional', conditionalOn: CONDITION, nonObvious: true })]}
      />,
    );
    expect(screen.getByText('Easy to miss')).toBeInTheDocument();
    expect(screen.getByTestId('requirement-condition')).toHaveTextContent(CONDITION);
  });
});
