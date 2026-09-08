/**
 * PolicyDiffView — renders the Draft vs Live diff and wires the
 * per-row revert action. Uses testing-library role/testid queries so
 * the tests double as a11y + behavior checks.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyDiffView } from '../PolicyDiffView';

const mocks = vi.hoisted(() => ({
  hrDiff: vi.fn(),
  hrRevertRow: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrDiff: (...args: unknown[]) => mocks.hrDiff(...args),
    hrRevertRow: (...args: unknown[]) => mocks.hrRevertRow(...args),
  },
}));

function diffPayload(overrides: Record<string, unknown> = {}) {
  return {
    live: { version: { version_number: 1, status: 'published', effective_date: '2026-01-01' } },
    draft: { version: { version_number: 2, status: 'draft', effective_date: '2026-07-01' } },
    diff: {
      added: [],
      removed: [],
      changed: [],
      unchanged_count: 6,
      summary: { added: 0, removed: 0, changed: 0, unchanged: 6 },
      ...(overrides),
    },
  };
}

afterEach(() => {
  cleanup();
  mocks.hrDiff.mockReset();
  mocks.hrRevertRow.mockReset();
});

describe('PolicyDiffView', () => {
  beforeEach(() => {
    mocks.hrDiff.mockResolvedValue(diffPayload());
  });

  it('shows "no draft" when draft version is absent', async () => {
    mocks.hrDiff.mockResolvedValueOnce({
      live: { version: null },
      draft: { version: null },
      diff: { added: [], removed: [], changed: [], unchanged_count: 0, summary: { added: 0, removed: 0, changed: 0, unchanged: 0 } },
    });
    render(<PolicyDiffView />);
    expect(await screen.findByText(/No draft in progress/i)).toBeInTheDocument();
  });

  it('shows the "draft matches live" message when there are no changes', async () => {
    render(<PolicyDiffView />);
    expect(await screen.findByText(/Your draft matches the live version/i)).toBeInTheDocument();
  });

  it('renders added / removed / changed rows with summary badges', async () => {
    mocks.hrDiff.mockResolvedValueOnce(diffPayload({
      added: [
        { benefit_key: 'home_leave_trips', benefit_label: 'Home leave trips', amount_value: 2000, currency_code: 'EUR', targeting_signature: 'global' },
      ],
      removed: [
        { benefit_key: 'storage', benefit_label: 'Storage', amount_value: 500, currency_code: 'EUR', targeting_signature: 'global' },
      ],
      changed: [
        {
          before: { benefit_key: 'shipment', benefit_label: 'Shipment', amount_value: 5000, currency_code: 'EUR', targeting_signature: 'global' },
          after:  { benefit_key: 'shipment', benefit_label: 'Shipment', amount_value: 6500, currency_code: 'EUR', targeting_signature: 'global' },
          changed_fields: ['amount_value'],
        },
      ],
      unchanged_count: 3,
      summary: { added: 1, removed: 1, changed: 1, unchanged: 3 },
    }));
    render(<PolicyDiffView />);
    expect(await screen.findByText(/^Added rows \(1\)$/)).toBeInTheDocument();
    expect(screen.getByText(/^Removed rows \(1\)$/)).toBeInTheDocument();
    expect(screen.getByText(/^Changed rows \(1\)$/)).toBeInTheDocument();
    expect(screen.getByText(/\+1 added/i)).toBeInTheDocument();
    expect(screen.getByText(/~1 changed/i)).toBeInTheDocument();
    expect(screen.getByText(/−1 removed/i)).toBeInTheDocument();
    // Changed row shows before and after values
    expect(screen.getByText('5000')).toBeInTheDocument();
    expect(screen.getByText('6500')).toBeInTheDocument();
  });

  it('calls hrRevertRow with the row key when Revert is clicked on a changed row', async () => {
    mocks.hrDiff.mockResolvedValueOnce(diffPayload({
      changed: [
        {
          before: { benefit_key: 'shipment', amount_value: 5000, targeting_signature: 'global' },
          after:  { benefit_key: 'shipment', amount_value: 6500, targeting_signature: 'global' },
          changed_fields: ['amount_value'],
        },
      ],
      summary: { added: 0, removed: 0, changed: 1, unchanged: 0 },
    }));
    mocks.hrRevertRow.mockResolvedValueOnce(diffPayload()); // after revert: no changes
    render(<PolicyDiffView />);
    // Target the exact heading "Changed rows (1)" — "Changed" is a
    // substring of "unchanged rows not shown" in the footer so a naive
    // regex matches twice.
    await screen.findByText(/^Changed rows \(\d+\)$/);
    const revertBtns = screen.getAllByRole('button', { name: /^Revert$/ });
    fireEvent.click(revertBtns[0]);
    await waitFor(() => expect(mocks.hrRevertRow).toHaveBeenCalledTimes(1));
    expect(mocks.hrRevertRow).toHaveBeenCalledWith(
      { benefit_key: 'shipment', targeting_signature: 'global' },
      undefined
    );
    // After revert succeeds, the clean-state message replaces the changed row.
    expect(await screen.findByText(/Your draft matches the live version/i)).toBeInTheDocument();
  });

  it('surfaces an API error inline', async () => {
    mocks.hrDiff.mockRejectedValueOnce({
      response: { data: { detail: 'Something broke on the server' } },
    });
    render(<PolicyDiffView />);
    expect(await screen.findByText(/Something broke on the server/i)).toBeInTheDocument();
  });
});
