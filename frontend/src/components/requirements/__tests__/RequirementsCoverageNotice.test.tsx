import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementsCoverageNotice } from '../RequirementsCoverageNotice';

describe('RequirementsCoverageNotice (AIQ-1473d)', () => {
  it('renders an honest "no catalogue" notice when covered is false', () => {
    render(<RequirementsCoverageNotice covered={false} destCountry="ATLANTIS" />);
    // Heading widened: `covered: false` now also covers "the country IS catalogued but
    // has no rows for this purpose", so it must not imply the whole country is missing.
    expect(screen.getByText(/Requirements not available yet for ATLANTIS/i)).toBeTruthy();
    // The load-bearing half — an empty list means "we can't confirm", never "there is
    // nothing required".
    expect(screen.getByText(/not that there are\s+none/i)).toBeTruthy();
    expect(screen.getByText(/not that there are\s+none/i)).toBeTruthy();
  });

  it('renders nothing when covered is true (the common case)', () => {
    const { container } = render(<RequirementsCoverageNotice covered={true} destCountry="GERMANY" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when covered is undefined (older backend)', () => {
    const { container } = render(<RequirementsCoverageNotice destCountry="GERMANY" />);
    expect(container.firstChild).toBeNull();
  });

  it('shows a corridor-not-ready notice when the catalog fails sufficiency', () => {
    render(
      <RequirementsCoverageNotice
        covered
        destCountry="NORWAY"
        catalogReady={false}
        catalogNotReadyReason="This corridor is not ready: approved items do not yet cover more than one requirement pillar."
      />,
    );
    expect(screen.getByTestId('catalog-not-ready')).toBeTruthy();
    expect(screen.getByText(/more than one requirement pillar/i)).toBeTruthy();
  });
});
