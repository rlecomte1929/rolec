/**
 * ImmigrationStatusPanel — AIQ-847 (F1 follow-up).
 *
 * Covers the uncovered-corridor coverage state introduced when backend F1
 * (AIQ-832, PR #399) made GET /immigration-requirements fail closed:
 *   - covered=false  → distinct "guidance isn't available yet" empty state
 *                      (NOT the generic "Immigration setup not started"), and
 *                      referencing the corridor when present.
 *   - covered=true   → unchanged checklist; timeline chip renders.
 *   - timeline null  → no "~Nd processing" chip (null guard).
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { ImmigrationStatusPanel } from '../ImmigrationStatusPanel';
import { hrAPI } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  hrAPI: {
    getImmigrationRequirements: vi.fn(),
    getImmigrationInterviewStatus: vi.fn(),
  },
}));

// Stub the milestone timeline — it has its own data needs and is out of scope here.
vi.mock('../../immigration/MilestoneTracker', () => ({
  MilestoneTracker: () => null,
}));

const mockedReqs = vi.mocked(hrAPI.getImmigrationRequirements);
const mockedInterview = vi.mocked(hrAPI.getImmigrationInterviewStatus);

const INTERVIEW = {
  has_session: false,
  completion_pct: 0,
  is_complete: false,
  started_at: null,
  last_active_at: null,
  completed_at: null,
};

const REQUIREMENT = {
  document_type: 'passport',
  document_name: 'Valid passport',
  is_required: true,
  freshness_days: null,
  requires_apostille: false,
  apostille_countries: [],
  requires_translation: false,
  translation_languages: [],
  typical_processing_days: null,
  book_early_flag: false,
  book_early_reason: null,
  form_url: null,
};

const uncovered = (corridor: string | null) => ({
  covered: false,
  coverage_reason: 'corridor_not_supported',
  corridor,
  corridor_from: 'FR',
  corridor_to: 'JP',
  visa_type: 'blue_card',
  document_count: 0,
  estimated_timeline_days: null,
  requirements: [],
  risk_flags: [],
});

const covered = (estimated_timeline_days: number | null) => ({
  covered: true,
  coverage_reason: null,
  corridor: 'FR→DE',
  corridor_from: 'FR',
  corridor_to: 'DE',
  visa_type: 'blue_card',
  document_count: 1,
  estimated_timeline_days,
  requirements: [REQUIREMENT],
  risk_flags: [],
});

const renderPanel = () =>
  render(
    <ImmigrationStatusPanel
      caseId="case-1"
      moveDate={null}
      onFindVendor={() => {}}
      onViewProfile={() => {}}
    />,
  );

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ImmigrationStatusPanel — uncovered-corridor state (AIQ-847)', () => {
  it('covered=false with a known corridor shows the "not available yet" state referencing the corridor, not "setup not started"', async () => {
    mockedReqs.mockResolvedValue(uncovered('FR→JP'));
    mockedInterview.mockResolvedValue(INTERVIEW);

    renderPanel();

    await waitFor(() =>
      expect(
        screen.getByText(/Immigration guidance for FR→JP isn't available yet/i),
      ).toBeInTheDocument(),
    );
    // The misleading generic state must NOT be shown for an uncovered corridor.
    expect(screen.queryByText('Immigration setup not started')).toBeNull();
  });

  it('covered=false with no resolvable corridor falls back to generic copy without crashing', async () => {
    mockedReqs.mockResolvedValue(uncovered(null));
    mockedInterview.mockResolvedValue(INTERVIEW);

    renderPanel();

    await waitFor(() =>
      expect(
        screen.getByText(/Immigration guidance for this corridor isn't available yet/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText('Immigration setup not started')).toBeNull();
  });

  it('covered=true renders the checklist and the processing-time chip when a timeline is present', async () => {
    mockedReqs.mockResolvedValue(covered(30));
    mockedInterview.mockResolvedValue(INTERVIEW);

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText('Document checklist (1)')).toBeInTheDocument(),
    );
    expect(screen.getByText('~30d processing')).toBeInTheDocument();
    expect(screen.queryByText(/isn't available yet/i)).toBeNull();
  });

  it('covered=true with a null timeline renders the checklist but hides the processing chip', async () => {
    mockedReqs.mockResolvedValue(covered(null));
    mockedInterview.mockResolvedValue(INTERVIEW);

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText('Document checklist (1)')).toBeInTheDocument(),
    );
    expect(screen.queryByText(/processing/i)).toBeNull();
  });
});
