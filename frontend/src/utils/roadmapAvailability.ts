/**
 * [P2-07b · AIQ-699] computeAvailableNow — pure dependency-graph availability
 * for the "What You Can Do Now" widget (parent P2-07 / AIQ-213).
 *
 * A roadmap step is "available now" when it has not been started yet
 * (status 'pending' — the schema's not-started state) and every step it
 * depends on (`dependency_ids`) is 'completed'. Steps whose dependencies are
 * unmet, missing, or still in flight are excluded — those are the blocked ones.
 *
 * The functions are generic over a minimal structural shape so they work with
 * both `RoadmapStep` (relopass-api-contracts) and the live `RoadmapV2Step`
 * (api/roadmapV2) without coupling to either.
 */

/** Minimal shape the availability functions need from a roadmap step. */
export interface AvailabilityStep {
  id: string;
  status: string;
  dependency_ids: string[];
}

/** Status meaning "completed" — the only status that satisfies a dependency. */
const COMPLETED_STATUS = 'completed';
/** Status meaning "not started yet" — the precondition for being available. */
const AVAILABLE_STATUS = 'pending';

/**
 * Thrown when the dependency graph contains a cycle. Carries the offending
 * path so callers can surface a helpful message instead of looping forever.
 */
export class CircularDependencyError extends Error {
  readonly cycle: string[];
  constructor(cycle: string[]) {
    super(`Circular dependency detected in roadmap: ${cycle.join(' → ')}`);
    this.name = 'CircularDependencyError';
    this.cycle = cycle;
  }
}

/**
 * Depth-first traversal that throws CircularDependencyError on the first cycle.
 * Missing dependency ids (pointing at a step not in the list) are treated as
 * dangling edges, not cycles. Roadmaps are small (~tens of steps), so simple
 * recursion is fine.
 */
function assertNoCycles(steps: AvailabilityStep[]): void {
  const byId = new Map(steps.map(s => [s.id, s]));
  const WHITE = 0;
  const GRAY = 1;
  const BLACK = 2;
  const color = new Map<string, number>();
  const path: string[] = [];

  const visit = (id: string): void => {
    color.set(id, GRAY);
    path.push(id);
    const step = byId.get(id);
    if (step) {
      for (const depId of step.dependency_ids) {
        if (!byId.has(depId)) continue; // dangling dependency — not a cycle
        const c = color.get(depId) ?? WHITE;
        if (c === GRAY) {
          const start = path.indexOf(depId);
          throw new CircularDependencyError([...path.slice(start), depId]);
        }
        if (c === WHITE) visit(depId);
      }
    }
    path.pop();
    color.set(id, BLACK);
  };

  for (const step of steps) {
    if ((color.get(step.id) ?? WHITE) === WHITE) visit(step.id);
  }
}

/**
 * Returns the steps that can be started right now: not-yet-started steps whose
 * every dependency is completed. Order is preserved from the input (callers
 * typically pass a sort_order-sorted list).
 *
 * @throws {CircularDependencyError} if the dependency graph contains a cycle.
 */
export function computeAvailableNow<T extends AvailabilityStep>(steps: T[]): T[] {
  assertNoCycles(steps);
  const byId = new Map(steps.map(s => [s.id, s]));
  return steps.filter(step => {
    if (step.status !== AVAILABLE_STATUS) return false;
    return step.dependency_ids.every(depId => {
      const dep = byId.get(depId);
      return dep != null && dep.status === COMPLETED_STATUS;
    });
  });
}

/**
 * Returns the steps currently blocking progress: dependencies of not-yet-started
 * steps that are themselves not completed. Used to name the blocker in the
 * widget's empty state ("No actions available — waiting on [blocker]"). Only
 * inspects direct dependencies, so it never loops; if the graph has a cycle,
 * call computeAvailableNow first to detect it.
 */
export function computeBlockers<T extends AvailabilityStep>(steps: T[]): T[] {
  const byId = new Map(steps.map(s => [s.id, s]));
  const blockerIds = new Set<string>();
  for (const step of steps) {
    if (step.status !== AVAILABLE_STATUS) continue;
    for (const depId of step.dependency_ids) {
      const dep = byId.get(depId);
      if (dep && dep.status !== COMPLETED_STATUS) blockerIds.add(dep.id);
    }
  }
  return steps.filter(s => blockerIds.has(s.id));
}
