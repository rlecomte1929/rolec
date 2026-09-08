import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// AdminLayout pulls in shell/router chrome we don't need here — render children only.
vi.mock('./AdminLayout', () => ({ AdminLayout: ({ children }: { children: React.ReactNode }) => children }));
vi.mock('../../api/requirementFacts', () => ({
  listRequirementFacts: vi.fn(),
  reviewRequirementFact: vi.fn(),
}));

import { AdminRequirementFactsPage } from './AdminRequirementFactsPage';
import { listRequirementFacts, reviewRequirementFact } from '../../api/requirementFacts';

const mk = (over: Record<string, unknown>) => ({
  id: 'f1', created_at: null, source_url: 'https://gov.example', corridor: 'IN-DE',
  requirement_type: 'document', fact_text: 'A valid passport is required', confidence_score: 0.9,
  source_quote: 'must hold a passport', extraction_method: 'llm', status: 'pending',
  reviewed_by: null, reviewed_at: null, ...over,
});

const FACTS = [
  mk({ id: 'f1', confidence_score: 0.9, fact_text: 'A valid passport is required' }),
  mk({ id: 'f2', confidence_score: 0.4, requirement_type: 'fee', fact_text: 'Pay the EUR 75 fee' }),
];

afterEach(cleanup);
beforeEach(() => {
  vi.mocked(listRequirementFacts).mockResolvedValue(FACTS as never);
  vi.mocked(reviewRequirementFact).mockResolvedValue(FACTS[0] as never);
});

describe('AdminRequirementFactsPage', () => {
  it('renders pending facts with confidence badges', async () => {
    render(<AdminRequirementFactsPage />);
    expect(await screen.findByText('A valid passport is required')).toBeInTheDocument();
    expect(screen.getByText('Pay the EUR 75 fee')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument(); // high-confidence badge
    expect(screen.getByText('40%')).toBeInTheDocument(); // low-confidence badge
  });

  it('approve calls the API and removes the row', async () => {
    render(<AdminRequirementFactsPage />);
    await screen.findByText('A valid passport is required');
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0]);
    await waitFor(() => expect(reviewRequirementFact).toHaveBeenCalledWith('f1', 'approved'));
    await waitFor(() =>
      expect(screen.queryByText('A valid passport is required')).not.toBeInTheDocument(),
    );
  });
});
