import { describe, it, expect } from 'vitest';
import { intakeEnvelopeSchema, assignmentsOverviewSchema } from '../employee';
import {
  overviewFixture as overview,
  intakeEnvelopeFixture as intake,
} from '../../../../e2e/support/fixtures';

/**
 * QG-5b anti-drift guard. The Playwright E2E fixtures used to MOCK /api must
 * satisfy the TS-1 zod schemas that validate the real API boundary. If the
 * backend contract changes a schema, this test (in the gated unit suite) goes
 * red — so the mocked E2E fixtures can never silently diverge from the real
 * response shape. (Only the boundaries with a zod schema are checked; the
 * roadmap fixture has no TS-1 schema yet.)
 */
describe('E2E fixtures match the TS-1 API schemas', () => {
  it('assignments-overview.json matches assignmentsOverviewSchema', () => {
    const result = assignmentsOverviewSchema.safeParse(overview);
    expect(result.success, JSON.stringify(result.error?.issues)).toBe(true);
  });

  it('intake-envelope.json matches intakeEnvelopeSchema', () => {
    const result = intakeEnvelopeSchema.safeParse(intake);
    expect(result.success, JSON.stringify(result.error?.issues)).toBe(true);
  });
});
