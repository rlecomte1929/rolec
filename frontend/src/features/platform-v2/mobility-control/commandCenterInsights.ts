/**
 * Command-center copy helpers (AIQ-2343 / 2345 / 2348).
 * Kept free of React so the audit tickets can be asserted without mounting the page.
 */

export const INCOMPLETE_CORRIDOR_KEY = 'incomplete';
export const INCOMPLETE_CORRIDOR_LABEL = 'Incomplete corridor';

export function isIncompleteCorridor(
  originCountry?: string | null,
  destCountry?: string | null,
): boolean {
  return !(originCountry ?? '').trim() || !(destCountry ?? '').trim();
}

export function spendIsTracked(estimated: number, limit: number): boolean {
  return estimated > 0 || limit > 0;
}

export function buildCommandCenterInsights(input: {
  behindCount: number;
  atRiskCount: number;
  incompleteCorridorCount: number;
  redCount: number;
}): string | null {
  const parts: string[] = [];
  if (input.behindCount > 0) {
    parts.push(
      `${input.behindCount} case${input.behindCount === 1 ? ' is' : 's are'} behind schedule`,
    );
  }
  if (input.redCount > 0) {
    parts.push(
      `${input.redCount} flagged red`,
    );
  } else if (input.atRiskCount > 0) {
    parts.push(
      `${input.atRiskCount} at risk (delayed 5+ days)`,
    );
  }
  if (input.incompleteCorridorCount > 0) {
    parts.push(
      `${input.incompleteCorridorCount} missing origin or destination`,
    );
  }
  if (parts.length === 0) return null;
  const head = parts[0]!;
  const rest = parts.slice(1);
  if (rest.length === 0) return `${head[0]!.toUpperCase()}${head.slice(1)}.`;
  return `${head[0]!.toUpperCase()}${head.slice(1)}. ${rest.join('. ')}.`;
}
