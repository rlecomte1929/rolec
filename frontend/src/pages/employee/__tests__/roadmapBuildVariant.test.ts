import { describe, it, expect } from 'vitest';
import { resolveRoadmapBuildVariant } from '../roadmapBuildVariant';

describe('a permission error is not "we are building your roadmap"', () => {
  it('403 fails FAST — it can never resolve by polling', () => {
    // Observed live: viewing a case you cannot access 403s, and the page showed
    // "We're building your roadmap — you'll get an email the moment it's ready,
    // usually within 2 working days." That email is never coming.
    expect(resolveRoadmapBuildVariant(false, true, 403)).toBe('failed');
    expect(resolveRoadmapBuildVariant(false, true, 401)).toBe('failed');
  });

  it('a transient 5xx still gets the bounded retry', () => {
    expect(resolveRoadmapBuildVariant(false, true, 500)).toBe('generating');
    expect(resolveRoadmapBuildVariant(true, true, 500)).toBe('failed');
  });

  it('an empty plan still generating is unchanged', () => {
    expect(resolveRoadmapBuildVariant(false, false, null)).toBe('generating');
    expect(resolveRoadmapBuildVariant(true, false, null)).toBe('empty');
  });
});
