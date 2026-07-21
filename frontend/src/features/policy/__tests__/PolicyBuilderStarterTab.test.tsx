/**
 * AIQ-1588: the starter-baseline card now seeds the CONFIG-MATRIX draft
 * (policyConfigMatrixAPI.hrApplyTemplate) — the subsystem the Policy Builder
 * edits — instead of the legacy company_policies initializeFromTemplate. This
 * verifies the rewire on the Policy Builder tab's card.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const mocks = vi.hoisted(() => ({
  hrApplyTemplate: vi.fn(),
  // AIQ-1644: control the published-state signal the tab reads. Default null = unknown
  // (still loading) so the baseline flow renders, exactly as before this change.
  published: { value: null as boolean | null },
}));
vi.mock('../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrApplyTemplate: (...args: unknown[]) => mocks.hrApplyTemplate(...args),
  },
}));
vi.mock('../../../hooks/usePolicyPublished', () => ({
  usePolicyPublished: () => mocks.published.value,
}));

import { PolicyBuilderStarterTab } from '../PolicyBuilderStarterTab';

describe('PolicyBuilderStarterTab — config-matrix baseline seeding (AIQ-1588)', () => {
  beforeEach(() => {
    mocks.hrApplyTemplate.mockReset();
    mocks.published.value = null;
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

  // ── AIQ-1644: builder tab must agree with the Published tab ───────────────────
  it('offers to edit/version when a policy is already published — no baseline invite', () => {
    mocks.published.value = true;
    const onOpen = vi.fn();
    render(<PolicyBuilderStarterTab onOpenFullBuilder={onOpen} />);

    // Must NOT invite a from-scratch baseline (criterion 2).
    expect(screen.queryByRole('button', { name: /create standard baseline/i })).toBeNull();
    expect(screen.queryByText(/signed-off file/i)).toBeNull();
    // Reflects the existing policy + an edit affordance into the full builder (criterion 3).
    expect(screen.getByText(/A relocation policy is already set up/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /edit or version your policy/i }));
    expect(onOpen).toHaveBeenCalled();
  });

  it('still shows the baseline invitation when no policy exists (criterion 4)', () => {
    mocks.published.value = false;
    render(<PolicyBuilderStarterTab onOpenFullBuilder={vi.fn()} />);
    expect(screen.getByRole('button', { name: /create standard baseline/i })).toBeInTheDocument();
    expect(screen.queryByText(/A relocation policy is already set up/i)).toBeNull();
  });
});
