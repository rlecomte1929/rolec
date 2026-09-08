/**
 * HR Resources preview — destination dropdown smoke tests.
 *
 * The page consumes the same payload shape as the employee Resources page,
 * so we just verify the destination knobs render and that the API client
 * is called with the chosen country / persona.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { HrResourcesPreview } from '../HrResourcesPreview';

// AppShell pulls in FeedbackWidget → supabase, which requires env vars not
// set in vitest. We don't need the chrome for these assertions.
vi.mock('../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../api/client', () => ({
  resourcesAPI: {
    getDestinations: vi.fn().mockResolvedValue([]),
    getHrPreviewPage: vi.fn().mockResolvedValue({
      context: { countryCode: 'NO', countryName: 'Norway', cityName: null, hasChildren: false, relocationType: 'permanent', previewMode: true },
      categories: [],
      resources: [],
      events: [],
      recommended: { recommendedForYou: [], firstSteps: [], familyEssentials: [], thisWeekend: [] },
      hints: { priorities: [], recommendations: [] },
      filtersApplied: {},
    }),
  },
}));

vi.mock('../../contexts/HrCompanyContext', () => ({
  useHrCompanyContext: () => ({
    companyId: 'co-1',
    company: { default_destination_country: 'Germany' },
    loading: false,
    error: null,
    refresh: async () => {},
  }),
}));

import { resourcesAPI } from '../../api/client';

// Stage-2 audit: pre-existing failure surfaced after npm ci was fixed in CI.
// Mock does not include `resourcesAPI.getDestinations` which the component
// now calls — test mock wasn't updated when the API surface grew. Skip-with-todo
// until fixed in AUDIT-CITESTS-followup (Notion).
describe('HrResourcesPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders destination knobs and seeds country from company default', async () => {
    render(
      <MemoryRouter initialEntries={['/hr/resources']}>
        <HrResourcesPreview />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/destination country/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/city \(optional\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/as employee/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/assignment length/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(resourcesAPI.getHrPreviewPage).toHaveBeenCalled();
    });
    const firstCall = (resourcesAPI.getHrPreviewPage as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as { countryCode: string; familyType: string; relocationType: string };
    expect(firstCall.countryCode).toBe('DE'); // seeded from company default "Germany"
    expect(firstCall.familyType).toBe('single');
    expect(firstCall.relocationType).toBe('permanent');
  });

  it('refetches when HR changes destination country', async () => {
    render(
      <MemoryRouter initialEntries={['/hr/resources?country=NO']}>
        <HrResourcesPreview />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(resourcesAPI.getHrPreviewPage).toHaveBeenCalled();
    });
    (resourcesAPI.getHrPreviewPage as unknown as ReturnType<typeof vi.fn>).mockClear();

    const select = screen.getByLabelText(/destination country/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'FR' } });

    await waitFor(() => {
      expect(resourcesAPI.getHrPreviewPage).toHaveBeenCalled();
    });
    const calls = (resourcesAPI.getHrPreviewPage as unknown as ReturnType<typeof vi.fn>).mock.calls;
    const lastCall = calls[calls.length - 1][0] as { countryCode: string; countryName: string };
    expect(lastCall.countryCode).toBe('FR');
    expect(lastCall.countryName).toBe('France');
  });
});
