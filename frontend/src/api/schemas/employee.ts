import { z } from 'zod';

/**
 * Runtime schemas for the hottest employee-facing API boundaries (AP-04 / TS-1).
 * Kept lenient on purpose: we validate the envelope shape we rely on and leave
 * complex nested payloads loose, so real prod responses pass while gross drift
 * (missing/renamed top-level fields, wrong types) is caught and logged via
 * `parseResponse`. Inferred types are exported for reuse.
 */

/** GET /api/employee/assignments/{id}/intake — the intake hydration envelope. */
export const intakeEnvelopeSchema = z.object({
  assignmentId: z.string(),
  intakeStep: z.number(),
  intakeTotalSteps: z.number(),
  intakeUpdatedAt: z.string().nullable(),
  intakeDraft: z.record(z.string(), z.unknown()).nullable(),
});
export type IntakeEnvelope = z.infer<typeof intakeEnvelopeSchema>;

/** GET /api/employee/assignments/overview — top-level envelope (rows stay loose). */
export const assignmentsOverviewSchema = z.object({
  linked: z.array(z.unknown()),
  pending: z.array(z.unknown()),
});

/** GET /api/employee/assignments/current — top-level envelope. */
export const currentAssignmentSchema = z.object({
  assignment: z.unknown(),
  linked_assignments: z.array(z.unknown()).optional(),
  pending_claim_assignments: z.array(z.unknown()).optional(),
});
