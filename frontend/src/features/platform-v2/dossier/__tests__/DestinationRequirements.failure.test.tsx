import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const getRequirements = vi.fn();
vi.mock('../../../../api/cases', () => ({ getRequirements: (id: string) => getRequirements(id) }));
vi.mock('../../../../components/requirements/Citations', () => ({ Citations: () => null }));
vi.mock('../../../../components/requirements/ImmigrationDisclaimer', () => ({
  ImmigrationDisclaimer: () => null,
}));

import { DestinationRequirements } from '../DestinationRequirements';

/**
 * The single most important assertion about this component, kept in its own file.
 *
 * On this screen an empty list MEANS "nothing is required of you" — a claim about
 * someone's legal obligations. So a fetch failure must never be allowed to render as
 * an empty section. It has to say, in as many words, that it failed.
 *
 * (Own file deliberately: `waitFor` polling alongside a rejected mock in a shared
 * module surfaced the rejection as an unhandled error before the component's catch
 * could run — a harness artefact, not a product one. Isolated, it exercises the real
 * behaviour.)
 */
describe('a fetch failure must never look like "nothing is required"', () => {
  it('renders an explicit error, not an empty list', async () => {
    getRequirements.mockRejectedValue(new Error('500'));

    const { container } = render(<DestinationRequirements caseId="c1" />);
    await new Promise((r) => setTimeout(r, 30));

    const box = screen.getByTestId('requirements-error');
    expect(box).toBeTruthy();

    // Split across elements by <strong>not</strong>, so match the text content.
    expect(box.textContent).toMatch(/couldn’t load your destination requirements/i);
    expect(box.textContent).toMatch(/does\s*not\s*mean nothing is required of you/i);

    // And it must NOT have quietly rendered an empty, reassuring section.
    expect(container.textContent).not.toMatch(/no destination requirements apply/i);
    expect(screen.queryByText(/we don’t have destination requirements/i)).toBeNull();
  });
});
