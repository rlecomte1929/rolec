/**
 * The corridor's non-obvious traps must reach the reader, and must not overstate.
 *
 * Before this component existed, `git grep advisories -- frontend/src` returned nothing: the
 * backend computed the ES→IE advisories, returned them, and no component read them. The
 * facts the corridor asset exists for — "a Spanish residence card gives you no right to
 * enter Ireland", "the employment permit is not immigration permission" — were dropped on
 * the floor at the UI boundary.
 *
 * The second half of this file is the more important half. An advisory with
 * `asserted: false` rests on an input the platform does not hold, so it may never be
 * rendered as a statement about this reader.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CorridorAdvisories } from '../CorridorAdvisories';
import type { RoadmapV2Advisory } from '../../../../api/roadmapV2';

const PROVENANCE = { corridor: 'ES_IE', pathway: 'CSEP_2026', verification: 'representative' };

const conditional: RoadmapV2Advisory = {
  id: 'VISA_REQUIRED_NATIONAL',
  text: "If your nationality is on Ireland's visa-required list, a long-stay 'D' Employment visa must be applied for and GRANTED before you travel.",
  asserted: false,
  cite: 'IE_D_VISA',
  provenance: PROVENANCE,
};

const asserted: RoadmapV2Advisory = {
  id: 'FAMILY_REUNIFICATION_CSEP',
  text: 'Critical Skills advantage: spouse/de-facto partner may reside on Stamp 1G with the right to work without a separate permit.',
  asserted: true,
  cite: 'IE_CSEP',
  provenance: PROVENANCE,
};

describe('CorridorAdvisories', () => {
  it('renders the trap text the corridor exists to warn about', () => {
    render(<CorridorAdvisories advisories={[conditional]} />);
    expect(screen.getByTestId('advisory-VISA_REQUIRED_NATIONAL')).toHaveTextContent(
      /long-stay 'D' Employment visa/,
    );
  });

  it('frames an unresolved condition as something to check, never as a statement', () => {
    render(<CorridorAdvisories advisories={[conditional]} />);
    // The heading must not assert. "Applies to your move" on a condition we cannot resolve
    // would be inventing the fact that decides whether she can board a plane.
    expect(screen.getByText('Worth checking')).toBeInTheDocument();
    expect(screen.queryByText('Applies to your move')).not.toBeInTheDocument();
  });

  it('states a resolved advisory plainly', () => {
    render(<CorridorAdvisories advisories={[asserted]} />);
    expect(screen.getByText('Applies to your move')).toBeInTheDocument();
    expect(screen.queryByText('Worth checking')).not.toBeInTheDocument();
  });

  it('distinguishes the two in the same list rather than flattening them', () => {
    render(<CorridorAdvisories advisories={[conditional, asserted]} />);
    expect(screen.getByText('Worth checking')).toBeInTheDocument();
    expect(screen.getByText('Applies to your move')).toBeInTheDocument();
  });

  it('carries the representative caveat through to the reader', () => {
    render(<CorridorAdvisories advisories={[conditional]} />);
    const note = screen.getByTestId('corridor-advisory-provenance');
    expect(note).toHaveTextContent(/not legal advice/i);
  });

  it('never claims a status the platform does not hold', () => {
    render(<CorridorAdvisories advisories={[conditional, asserted]} />);
    const body = document.body.textContent ?? '';
    // The corridor files describe themselves as REPRESENTATIVE and not SME-verified.
    // "Expert-verified" / "lawyer" / "certified" are reserved for assurance we do not have.
    expect(body).not.toMatch(/expert.?verified/i);
    expect(body).not.toMatch(/certified/i);
    expect(body).not.toMatch(/verified by (a|our) (lawyer|solicitor|counsel)/i);
  });

  it('renders nothing at all when there are no advisories', () => {
    const { container } = render(<CorridorAdvisories advisories={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the field is absent (older payload, or no corridor)', () => {
    const { container } = render(<CorridorAdvisories />);
    expect(container).toBeEmptyDOMElement();
  });
});
