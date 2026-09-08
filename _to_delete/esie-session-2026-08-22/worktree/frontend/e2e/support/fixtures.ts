/**
 * QG-5b mock fixtures — shared by the Playwright authed specs (as page.route
 * bodies) and the Vitest anti-drift test (validated against the TS-1 zod schemas
 * in src/api/schemas/__tests__/e2eFixtures.test.ts). Kept as a TS module (not
 * JSON) so both the Playwright (Node) and Vitest (Vite) loaders import it without
 * JSON import-attribute friction. The route `:caseId` is `asg-e2e-1`.
 */

export const overviewFixture = {
  linked: [
    {
      assignment_id: 'asg-e2e-1',
      case_id: 'case-e2e-1',
      company: { id: 'co-e2e', name: 'Acme E2E GmbH' },
      destination: {
        label: 'Berlin, Germany',
        host_country: 'DE',
        home_country: 'GB',
        host_city: 'Berlin',
        home_city: 'London',
      },
      status: 'assigned',
      current_stage: 'intake',
      intake_step: 1,
      intake_total_steps: 5,
      intake_updated_at: '2026-06-26T10:00:00Z',
      created_at: '2026-06-26T10:00:00Z',
      updated_at: '2026-06-26T10:00:00Z',
    },
  ],
  pending: [],
};

export const intakeEnvelopeFixture = {
  assignmentId: 'asg-e2e-1',
  intakeStep: 1,
  intakeTotalSteps: 5,
  intakeUpdatedAt: '2026-06-26T10:00:00Z',
  intakeDraft: null,
};
