import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/featureFlags', () => ({
  listFeatureFlags: vi.fn(),
  upsertFeatureFlag: vi.fn(),
  patchFeatureFlag: vi.fn(),
  addFlagAccount: vi.fn(),
  removeFlagAccount: vi.fn(),
}));
vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { listFeatureFlags, upsertFeatureFlag, patchFeatureFlag } from '../../api/featureFlags';
import { AdminFeatureFlagsPage } from './AdminFeatureFlagsPage';

const mockList = listFeatureFlags as unknown as ReturnType<typeof vi.fn>;
const mockUpsert = upsertFeatureFlag as unknown as ReturnType<typeof vi.fn>;
const mockPatch = patchFeatureFlag as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockList.mockReset(); mockUpsert.mockReset(); mockPatch.mockReset();
  mockList.mockResolvedValue({ items: [{ key: 'live_eea_roadmap', enabled: false, description: 'EEA roadmap', account_count: 0 }] });
});

describe('AdminFeatureFlagsPage', () => {
  it('lists flags', async () => {
    render(<AdminFeatureFlagsPage />);
    expect(await screen.findByText('live_eea_roadmap')).toBeInTheDocument();
    expect(screen.getByText('global')).toBeInTheDocument();
  });

  it('toggles a flag', async () => {
    mockPatch.mockResolvedValue({ ok: true });
    render(<AdminFeatureFlagsPage />);
    await screen.findByText('live_eea_roadmap');
    fireEvent.click(screen.getByRole('button', { name: 'Enable' }));
    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith('live_eea_roadmap', { enabled: true }));
  });

  it('creates a flag', async () => {
    mockUpsert.mockResolvedValue({ ok: true, key: 'new_flag' });
    render(<AdminFeatureFlagsPage />);
    await screen.findByText('live_eea_roadmap');
    fireEvent.change(screen.getByLabelText('New flag key'), { target: { value: 'new_flag' } });
    fireEvent.click(screen.getByRole('button', { name: /create flag/i }));
    await waitFor(() => expect(mockUpsert).toHaveBeenCalledWith(expect.objectContaining({ key: 'new_flag' })));
  });
});
