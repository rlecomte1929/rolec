/**
 * AIQ-1588: the starter-baseline card now seeds the CONFIG-MATRIX draft
 * (policyConfigMatrixAPI.hrApplyTemplate) — the subsystem the Policy Builder
 * edits — instead of the legacy company_policies initializeFromTemplate. This
 * verifies the rewire on the Policy Builder tab's card.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const mocks = vi.hoisted(() => ({ hrApplyTemplate: vi.fn() }));
vi.mock('../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrApplyTemplate: (...args: unknown[]) => mocks.hrApplyTemplate(...args),
  },
}));

import { PolicyBuilderStarterTab } from '../PolicyBuilderStarterTab';

describe('PolicyBuilderStarterTab — config-matrix baseline seeding (AIQ-1588)', () => {
  beforeEach(() => {
    mocks.hrApplyTemplate.mockReset();
  });

  it('seeds a config-matrix draft via hrApplyTemplate and opens the full builder', async () => {
    mocks.hrApplyTemplate.mockResolvedValue({ status: 'draft' });
    const onOpen = vi.fn();
    render(<PolicyBuilderStarterTab onOpenFullBuilder={onOpen} />);

    // Default tier is Standard; the primary button reads "Create Standard baseline".
    fireEvent.click(screen.getByRole('button', { name: /create standard baseline/i }));

    await waitFor(() => expect(mocks.hrApplyTemplate).toHaveBeenCalledTimes(1));
    expect(mocks.hrApplyTemplate).toHaveBeenCalledWith(
      { template_key: 'standard', replace_existing_draft: false },
      undefined,
    );
    await waitFor(() => expect(onOpen).toHaveBeenCalled());
  });

  it('shows a friendly message (and does not navigate) on a 409 draft_has_rows', async () => {
    mocks.hrApplyTemplate.mockRejectedValue({
      response: { data: { detail: { code: 'draft_has_rows', message: 'draft has rows' } } },
    });
    const onOpen = vi.fn();
    render(<PolicyBuilderStarterTab onOpenFullBuilder={onOpen} />);

    fireEvent.click(screen.getByRole('button', { name: /create standard baseline/i }));

    await screen.findByText(/already have a policy draft in progress/i);
    expect(onOpen).not.toHaveBeenCalled();
  });
});
