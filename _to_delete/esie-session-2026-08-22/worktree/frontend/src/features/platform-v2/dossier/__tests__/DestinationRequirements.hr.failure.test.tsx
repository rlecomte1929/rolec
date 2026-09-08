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
 * The HR half of the assertion that matters most about this component.
 *
 * The employee version is pinned in DestinationRequirements.failure.test.tsx. Adding a
 * second audience means adding a second way to get this wrong: an HR user who reads an
 * empty section as "nothing is required of this employee" is exactly the week-seven
 * ambush the product exists to prevent, and HR is the persona who would act on it.
 *
 * (Own file for the same harness reason the employee one has: a rejected mock alongside
 * `waitFor` polling in a shared module surfaces the rejection as an unhandled error
 * before the component's catch can run.)
 */
describe('a fetch failure must never look like "nothing is required of this employee"', () => {
  it('renders an explicit error in HR wording, not an empty list', async () => {
    getRequirements.mockRejectedValue(new Error('500'));

    const { container } = render(<DestinationRequirements caseId="c1" audience="hr" />);
    await new Promise((r) => setTimeout(r, 30));

    const box = screen.getByTestId('requirements-error');
    expect(box).toBeTruthy();

    // Split across elements by <strong>not</strong>, so match the text content.
    expect(box.textContent).toMatch(/couldn’t load the destination requirements/i);
    expect(box.textContent).toMatch(/does\s*not\s*mean nothing is required of\s*this employee/i);

    // Never the second-person copy — HR is reading about someone else.
    expect(box.textContent).not.toMatch(/required of you\b/i);

    // And it must NOT have quietly rendered an empty, reassuring section.
    expect(screen.queryByText(/we don’t have destination requirements/i)).toBeNull();
    expect(container.textContent).not.toMatch(/no destination requirements apply/i);
  });
});
