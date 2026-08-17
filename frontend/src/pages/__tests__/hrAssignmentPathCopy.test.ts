import { describe, it, expect } from 'vitest';
import { pathTileSubtitle } from '../hrAssignmentPathCopy';
import { destinationPermitLabel } from '../hrAssignmentPermit';

/**
 * [AIQ-1902] The reported bug, as a test.
 *
 * Case 6ecadafe (ES→IE) has 14 approved IE requirement_items, and the HR cockpit's Path
 * tile said "No permit mapping for this destination yet." above them.
 */
describe('pathTileSubtitle', () => {
  it('stops claiming there is no mapping once the destination has requirements', () => {
    // Ireland genuinely has no permit-dictionary entry — that part was never wrong.
    expect(destinationPermitLabel('IE')).toBeNull();

    expect(
      pathTileSubtitle({ permitLabel: null, requirementCount: 14, destination: 'IRELAND' }),
    ).toBe('14 requirements for this destination — see below.');
  });

  it('keeps the permit label as the headline where one exists', () => {
    // Norway HAS a mapping; the catalog must not displace it.
    expect(
      pathTileSubtitle({
        permitLabel: destinationPermitLabel('NO'),
        requirementCount: 11,
        destination: 'NORWAY',
      }),
    ).toBe('Indicative — confirm with the relevant authority.');
  });

  it('falls back to the permit-mapping notice when the catalog has nothing', () => {
    expect(
      pathTileSubtitle({ permitLabel: null, requirementCount: 0, destination: 'IRELAND' }),
    ).toBe('No permit mapping for this destination yet.');
  });

  it('still distinguishes "no destination" from "destination with no mapping"', () => {
    expect(pathTileSubtitle({ permitLabel: null, requirementCount: 0, destination: '' })).toBe(
      'Awaiting destination from intake.',
    );
  });

  it('agrees with itself about singulars', () => {
    expect(
      pathTileSubtitle({ permitLabel: null, requirementCount: 1, destination: 'IRELAND' }),
    ).toBe('1 requirement for this destination — see below.');
  });
});
