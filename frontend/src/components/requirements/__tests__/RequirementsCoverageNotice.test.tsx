import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RequirementsCoverageNotice } from '../RequirementsCoverageNotice';

describe('RequirementsCoverageNotice (AIQ-1473d)', () => {
  it('renders an honest "no catalogue" notice when covered is false', () => {
    render(<RequirementsCoverageNotice covered={false} destCountry="ATLANTIS" />);
    expect(screen.getByText(/No requirements catalogue yet for ATLANTIS/i)).toBeTruthy();
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
});
