import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementList } from '../RequirementList';
import type { RequirementItemDTO } from '../../../types';

vi.mock('../ImmigrationDisclaimer', () => ({ ImmigrationDisclaimer: () => null }));
vi.mock('../Citations', () => ({ Citations: () => null }));

const item = (verificationStatus?: RequirementItemDTO['verificationStatus']): RequirementItemDTO => ({
  id: '1', pillar: 'RESIDENCE', title: 'Residence permit', description: 'd',
  severity: 'WARN', owner: 'EMPLOYEE', requiredFields: [], statusForCase: 'MISSING',
  citations: [], verificationStatus,
});

describe('RequirementList provenance badge', () => {
  it('shows the expert-verified provenance badge', () => {
    render(<RequirementList items={[item('expert_verified')]} />);
    expect(screen.getByText('Expert-verified')).toBeTruthy();
  });

  it('shows source-grounded for corpus_grounded', () => {
    render(<RequirementList items={[item('corpus_grounded')]} />);
    expect(screen.getByText('Source-grounded')).toBeTruthy();
  });

  // Production stores `verified` for rows reviewed INTERNALLY. On 2026-08-20 all ten such
  // rows were Norway, reviewed_by='romain', attestation_status=null — no licensed
  // immigration lawyer has seen any of them, and expert_verified is 0 across the catalog.
  // disclaimers.py reserves "expert_verified" for counsel sign-off, so rendering `verified`
  // as "Expert-verified" told users we held a status we do not.
  it('does NOT claim expert verification for an internally-reviewed row', () => {
    render(<RequirementList items={[item('verified')]} />);
    expect(screen.queryByText('Expert-verified')).toBeNull();
  });

  it('still shows a badge for verified — the fix must not blank it', () => {
    render(<RequirementList items={[item('verified')]} />);
    expect(screen.getByText('Reviewed')).toBeTruthy();
  });

  it('renders no provenance badge when absent', () => {
    render(<RequirementList items={[item(undefined)]} />);
    expect(screen.queryByText('Representative')).toBeNull();
    expect(screen.queryByText('Expert-verified')).toBeNull();
  });
});
