import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CountryDetail } from '../CountryDetail';
import type { AdminRequirementReview, KnowledgeScorecard } from '../../../api/admin';
import type { CountryProfileDTO } from '../../../types';

const PROFILE: CountryProfileDTO = {
  countryCode: 'NORWAY',
  sources: [],
  requirementGroups: [],
};

const SCORECARD: KnowledgeScorecard = {
  approvedCount: 2,
  pendingCount: 3,
  rejectedCount: 0,
  citationResolvedApproved: 1,
  citationResolvePct: 50,
  pillarsPresent: ['IDENTITY'],
  catalogReady: false,
  notReadyReason: 'This corridor is not ready: approved items do not yet cover more than one requirement pillar.',
};

const ITEM: AdminRequirementReview = {
  id: '1',
  purpose: 'employment',
  pillar: 'IDENTITY',
  title: 'Valid passport',
  description: 'Passport must be valid.',
  severity: 'WARN',
  owner: 'EMPLOYEE',
  reviewStatus: 'pending',
  citations: [],
};

describe('CountryDetail knowledge scorecard', () => {
  it('shows sufficiency bars and the not-ready reason', () => {
    render(
      <CountryDetail
        profile={PROFILE}
        requirements={[ITEM]}
        pendingCount={1}
        scorecard={SCORECARD}
        busyId={null}
        onRerun={vi.fn()}
        onReview={vi.fn()}
      />,
    );
    expect(screen.getByTestId('knowledge-scorecard')).toBeInTheDocument();
    expect(screen.getByText('Not ready')).toBeInTheDocument();
    expect(screen.getByText(/more than one requirement pillar/i)).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
  });
});
