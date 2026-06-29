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

  it('renders no provenance badge when absent', () => {
    render(<RequirementList items={[item(undefined)]} />);
    expect(screen.queryByText('Representative')).toBeNull();
    expect(screen.queryByText('Expert-verified')).toBeNull();
  });
});
