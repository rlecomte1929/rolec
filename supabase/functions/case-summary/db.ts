/**
 * case-summary — DB read + tenant scoping (AIQ-1693).
 *
 * Split from index.ts (which imports supabase-js) so the tenant-isolation logic
 * is unit-testable with a fake client under a plain `deno test`. The client is
 * passed in as `any` — this module imports nothing.
 */
import {
  buildSummaryInput,
  OPERATIONAL_ASSIGNMENT_FIELDS,
  OPERATIONAL_CASE_FIELDS,
  type Row,
  type SummaryInput,
} from "./summary.ts";

/** Minimal shape of the supabase-js query builder we rely on (fake-able in tests). */
// deno-lint-ignore no-explicit-any
export type SupabaseLike = any;

/**
 * Resolve the assignment and its linked case, enforcing tenant isolation.
 * Returns null when the assignment is unknown, has no resolvable case, or the
 * case belongs to a different company — the caller maps all of these to 404 so a
 * wrong-tenant id is indistinguishable from a missing one (no existence oracle).
 */
export async function fetchAssignmentAndCase(
  supabase: SupabaseLike,
  assignmentId: string,
  companyId: string,
): Promise<SummaryInput | null> {
  // case_id / canonical_case_id are ids used only to resolve the case; never sent to Claude.
  const assignmentSelect = [...OPERATIONAL_ASSIGNMENT_FIELDS, "case_id", "canonical_case_id"].join(",");
  const { data: assignment, error: aErr } = await supabase
    .from("case_assignments")
    .select(assignmentSelect)
    .eq("id", assignmentId)
    .maybeSingle();
  if (aErr || !assignment) return null;

  const caseId = (assignment.canonical_case_id as string) || (assignment.case_id as string);
  if (!caseId) return null;

  const { data: caseRow, error: cErr } = await supabase
    .from("relocation_cases")
    .select([...OPERATIONAL_CASE_FIELDS, "company_id"].join(","))
    .eq("id", caseId)
    .maybeSingle();
  if (cErr || !caseRow) return null;

  // Tenant gate: the case must belong to the caller's company.
  if (String(caseRow.company_id) !== String(companyId)) return null;

  return buildSummaryInput(assignment as Row, caseRow as Row);
}
