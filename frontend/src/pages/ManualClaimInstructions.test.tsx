import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ManualClaimInstructions } from './EmployeeJourney';

describe('ManualClaimInstructions (AIQ-2290)', () => {
  it('names the region from the visible heading', () => {
    render(<ManualClaimInstructions signedInPrincipal={null} />);
    const region = screen.getByRole('region', { name: 'How to connect your case' });
    expect(region).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /how to fill the claim form/i })).toBeNull();
  });
});
