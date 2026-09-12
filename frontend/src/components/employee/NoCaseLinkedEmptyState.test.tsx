import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NoCaseLinkedEmptyState } from './NoCaseLinkedEmptyState';

describe('NoCaseLinkedEmptyState (AIQ-2361)', () => {
  it('renders the Services-style heading, explanation, and dashboard CTA', () => {
    render(
      <MemoryRouter>
        <NoCaseLinkedEmptyState explanation="Select a case to access tasks for this relocation." />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No case linked/)).toBeInTheDocument();
    expect(screen.getByText(/Select a case to access tasks/)).toBeInTheDocument();
    const cta = screen.getByRole('button', { name: /back to dashboard/i });
    expect(cta).toBeInTheDocument();
  });
});
