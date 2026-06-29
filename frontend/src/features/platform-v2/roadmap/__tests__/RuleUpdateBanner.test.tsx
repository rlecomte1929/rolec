import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RuleUpdateBanner } from '../RuleUpdateBanner';

vi.mock('../../../../api/caseRuleUpdates', () => ({
  getCaseRuleUpdates: vi.fn(),
  dismissCaseRuleUpdate: vi.fn().mockResolvedValue(undefined),
}));

import { getCaseRuleUpdates, dismissCaseRuleUpdate } from '../../../../api/caseRuleUpdates';

const mockList = getCaseRuleUpdates as ReturnType<typeof vi.fn>;
const mockDismiss = dismissCaseRuleUpdate as ReturnType<typeof vi.fn>;

describe('RuleUpdateBanner', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when there are no active updates', async () => {
    mockList.mockResolvedValue({ items: [], count: 0 });
    const { container } = render(<RuleUpdateBanner caseId="case-1" />);
    await waitFor(() => expect(mockList).toHaveBeenCalledWith('case-1'));
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the banner when the case has an approved rule update', async () => {
    mockList.mockResolvedValue({
      items: [{ id: 'n1', source_name: 'Cantonal office', source_url: 'https://x' }],
      count: 1,
    });
    render(<RuleUpdateBanner caseId="case-1" />);
    expect(await screen.findByText(/rule updated — please review/i)).toBeInTheDocument();
    expect(screen.getByText('Cantonal office')).toBeInTheDocument();
  });

  it('dismisses an update and removes it from the banner', async () => {
    mockList.mockResolvedValue({
      items: [{ id: 'n1', source_name: 'Cantonal office' }],
      count: 1,
    });
    render(<RuleUpdateBanner caseId="case-1" />);
    await screen.findByText('Cantonal office');

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    await waitFor(() => expect(mockDismiss).toHaveBeenCalledWith('case-1', 'n1'));
    await waitFor(() => expect(screen.queryByText('Cantonal office')).not.toBeInTheDocument());
    // Banner gone once the last update is dismissed.
    expect(screen.queryByText(/rule updated — please review/i)).not.toBeInTheDocument();
  });
});
