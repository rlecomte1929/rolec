import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

const getRequirements = vi.fn();
vi.mock('../../../../api/cases', () => ({ getRequirements: (id: string) => getRequirements(id) }));
vi.mock('../../../../components/requirements/Citations', () => ({ Citations: () => null }));
vi.mock('../../../../components/requirements/ImmigrationDisclaimer', () => ({
  ImmigrationDisclaimer: () => null,
}));

import { DestinationRequirements } from '../DestinationRequirements';

/**
 * [AIQ-1902] The failure direction of the `onLoaded` callback.
 *
 * This is the assertion that matters. The HR cockpit's Path tile uses the reported count
 * to decide whether to say "No permit mapping for this destination yet." — so a failed
 * fetch that reported anything other than `null` would let a network blip change what the
 * tile claims about someone's immigration route. The section itself is scrupulous about
 * this; the callback has to be too, or the discipline leaks.
 *
 * (Own file, and `setTimeout` rather than `waitFor`, for the harness reason spelled out
 * in DestinationRequirements.hr.failure.test.tsx: a rejected mock polled by `waitFor` in
 * a shared module surfaces as an unhandled error before the component's catch runs.)
 */
describe('onLoaded on failure', () => {
  it('reports null — a broken fetch is never an answer', async () => {
    getRequirements.mockRejectedValue(new Error('502'));
    const onLoaded = vi.fn();

    render(<DestinationRequirements caseId="c1" audience="hr" onLoaded={onLoaded} />);
    await new Promise((r) => setTimeout(r, 30));

    expect(onLoaded).toHaveBeenCalledTimes(2); // loading, then failed
    expect(onLoaded.mock.calls.at(-1)![0]).toBeNull();
  });
});
