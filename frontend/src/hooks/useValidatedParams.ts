import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { z } from 'zod';

/**
 * Validate React Router URL params against a zod schema (AP-04 / TS-4).
 *
 * `useParams()` types every value as `string | undefined` with no guard, so a
 * missing or garbage `:caseId` flows untyped into the page. This hook parses the
 * raw params once and returns the typed, validated object on success — or `null`
 * on invalid params, firing a graceful redirect (default: replace to the route
 * in `redirectTo`) so the page can render an empty/loading state instead of
 * crashing deep in a data fetch.
 *
 * Usage:
 *   const params = useValidatedParams(caseParamsSchema, { redirectTo: '/employee' });
 *   const caseId = params?.caseId;          // string | undefined, validated
 *   if (!caseId) return <Loading />;        // existing guard still works
 */
export function useValidatedParams<T>(
  schema: z.ZodType<T>,
  opts?: { redirectTo?: string },
): T | null {
  const raw = useParams();
  const navigate = useNavigate();
  const result = schema.safeParse(raw);
  const valid = result.success;
  const redirectTo = opts?.redirectTo;

  useEffect(() => {
    if (!valid && redirectTo) {
      navigate(redirectTo, { replace: true });
    }
  }, [valid, redirectTo, navigate]);

  return result.success ? result.data : null;
}

/** Shared schema for case-scoped employee routes (`/employee/case/:caseId/...`). */
export const caseParamsSchema = z.object({
  caseId: z.string().min(1),
});
export type CaseParams = z.infer<typeof caseParamsSchema>;
