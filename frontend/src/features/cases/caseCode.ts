/** Displayed case code and clipboard payload must be the same (BUG-260804-1BA9). */

export function caseCodeForDisplay(assignmentId: string | null | undefined): string {
  return (assignmentId ?? '').trim();
}
