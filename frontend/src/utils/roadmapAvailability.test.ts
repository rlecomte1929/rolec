import { describe, it, expect } from 'vitest';
import {
  computeAvailableNow,
  computeBlockers,
  CircularDependencyError,
  type AvailabilityStep,
} from './roadmapAvailability';

function step(id: string, status: string, deps: string[] = []): AvailabilityStep {
  return { id, status, dependency_ids: deps };
}

describe('computeAvailableNow', () => {
  it('returns steps with no dependencies that are not started', () => {
    const steps = [
      step('a', 'pending'),
      step('b', 'pending'),
      step('c', 'pending'),
    ];
    expect(computeAvailableNow(steps).map(s => s.id)).toEqual(['a', 'b', 'c']);
  });

  it('returns exactly the 3 available steps in a mixed graph', () => {
    // a, b, c available; d blocked by pending e; f already completed.
    const steps = [
      step('a', 'pending'),
      step('b', 'pending', ['x']), // x is completed → satisfied
      step('x', 'completed'),
      step('c', 'pending', ['x']),
      step('d', 'pending', ['e']), // e pending → blocked
      step('e', 'pending'),
      step('f', 'completed'),
    ];
    // e is also a no-dependency pending step → available. Constrain to the 3
    // explicitly-named ones plus e by checking the blocked one is absent.
    const available = computeAvailableNow(steps).map(s => s.id);
    expect(available).toContain('a');
    expect(available).toContain('b');
    expect(available).toContain('c');
    expect(available).not.toContain('d'); // blocked by pending 'e'
    expect(available).not.toContain('f'); // already completed
  });

  it('excludes steps whose dependencies are not all completed', () => {
    const steps = [
      step('lease', 'pending', ['viewings']),
      step('viewings', 'in_progress'),
    ];
    expect(computeAvailableNow(steps)).toEqual([]);
  });

  it('treats a missing (dangling) dependency as not satisfied', () => {
    const steps = [step('a', 'pending', ['ghost'])];
    expect(computeAvailableNow(steps)).toEqual([]);
  });

  it('returns 0 available when every step is blocked', () => {
    const steps = [
      step('a', 'pending', ['b']),
      step('b', 'pending', ['c']),
      step('c', 'in_progress'),
    ];
    expect(computeAvailableNow(steps)).toEqual([]);
  });

  it('throws CircularDependencyError on a dependency cycle (no infinite loop)', () => {
    const steps = [
      step('a', 'pending', ['b']),
      step('b', 'pending', ['c']),
      step('c', 'pending', ['a']),
    ];
    expect(() => computeAvailableNow(steps)).toThrow(CircularDependencyError);
  });

  it('exposes the offending cycle path on the error', () => {
    const steps = [
      step('a', 'pending', ['b']),
      step('b', 'pending', ['a']),
    ];
    try {
      computeAvailableNow(steps);
      throw new Error('expected CircularDependencyError');
    } catch (e) {
      expect(e).toBeInstanceOf(CircularDependencyError);
      expect((e as CircularDependencyError).cycle).toContain('a');
      expect((e as CircularDependencyError).cycle).toContain('b');
    }
  });

  it('does not treat a self-completed diamond as a cycle', () => {
    // a → done; b,c depend on a; d depends on b,c. No cycle.
    const steps = [
      step('a', 'completed'),
      step('b', 'pending', ['a']),
      step('c', 'pending', ['a']),
      step('d', 'pending', ['b', 'c']),
    ];
    expect(computeAvailableNow(steps).map(s => s.id)).toEqual(['b', 'c']);
  });
});

describe('computeBlockers', () => {
  it('names the incomplete dependency blocking a not-started step', () => {
    const steps = [
      step('lease', 'pending', ['viewings']),
      step('viewings', 'in_progress'),
    ];
    expect(computeBlockers(steps).map(s => s.id)).toEqual(['viewings']);
  });

  it('returns nothing when all not-started steps are unblocked', () => {
    const steps = [step('a', 'pending'), step('b', 'pending')];
    expect(computeBlockers(steps)).toEqual([]);
  });
});
