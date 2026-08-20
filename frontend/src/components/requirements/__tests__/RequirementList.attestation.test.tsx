import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementList } from '../RequirementList';
import type { RequirementItemDTO } from '../../../types';

vi.mock('../ImmigrationDisclaimer', () => ({ ImmigrationDisclaimer: () => null }));
vi.mock('../Citations', () => ({ Citations: () => null }));

const item = (over: Partial<RequirementItemDTO> = {}): RequirementItemDTO => ({
  id: '1', pillar: 'RESIDENCE', title: 'Residence permit', description: 'd',
  severity: 'WARN', owner: 'EMPLOYEE', requiredFields: [], statusForCase: 'MISSING',
  citations: [], ...over,
});

/**
 * The badge for the value production actually stores.
 *
 * requirement_items holds `verified` on 10 approved (therefore served) rows, while every
 * frontend map only knew `expert_verified` — so those ten rendered NO provenance badge at
 * all. There is no translation layer in the backend; verification_status is passed
 * straight through. That original defect is still pinned here.
 *
 * The expected LABEL was corrected on 2026-08-20. Honouring `verified` by aliasing it onto
 * "Expert-verified" fixed the blank badge by asserting a status we do not hold: all ten of
 * those rows are reviewed_by='romain' with attestation_status=null, and `expert_verified`
 * is 0 catalog-wide, while disclaimers.py reserves that word for sign-off by a licensed
 * immigration lawyer. The badge must render AND must be true.
 */
describe('RequirementList provenance — the value production stores', () => {
  it('renders a badge for `verified` rather than blanking it', () => {
    render(<RequirementList items={[item({ verificationStatus: 'verified' })]} />);
    expect(screen.getByText('Reviewed')).toBeTruthy();
  });

  it('does not dress an internal review as counsel sign-off', () => {
    render(<RequirementList items={[item({ verificationStatus: 'verified' })]} />);
    expect(screen.queryByText('Expert-verified')).toBeNull();
  });
});

/**
 * Counsel attestation is a SECOND axis, not a further rung on the provenance ladder.
 * "Sellable means BOTH" (backend/app/models.py). These tests pin the two apart, and pin
 * the rule that an absent attestation renders as absence rather than as reassurance.
 */
describe('RequirementList counsel-attestation badge', () => {
  it('shows Counsel-attested when counsel has signed off', () => {
    render(<RequirementList items={[item({ attestationStatus: 'attested' })]} />);
    expect(screen.getByText('Counsel-attested')).toBeTruthy();
  });

  it('names the attesting firm when one is recorded', () => {
    render(<RequirementList items={[item({
      attestationStatus: 'attested', attestedBy: 'Wikborg Rein',
    })]} />);
    expect(screen.getByText('Counsel-attested · Wikborg Rein')).toBeTruthy();
  });

  it('shows Attestation stale when the signed content has moved on', () => {
    render(<RequirementList items={[item({ attestationStatus: 'stale' })]} />);
    expect(screen.getByText('Attestation stale')).toBeTruthy();
  });

  it('renders NOTHING for `requested` — asking is not attesting', () => {
    render(<RequirementList items={[item({ attestationStatus: 'requested' })]} />);
    expect(screen.queryByTestId('attestation-badge')).toBeNull();
  });

  it('renders NOTHING when no counsel has looked, which is every row today', () => {
    render(<RequirementList items={[item({ attestationStatus: null })]} />);
    expect(screen.queryByTestId('attestation-badge')).toBeNull();
  });

  it('keeps the two axes independent: representative content can still be attested', () => {
    render(<RequirementList items={[item({
      verificationStatus: 'representative', attestationStatus: 'attested',
    })]} />);
    expect(screen.getByText('Representative')).toBeTruthy();
    expect(screen.getByText('Counsel-attested')).toBeTruthy();
  });
});
