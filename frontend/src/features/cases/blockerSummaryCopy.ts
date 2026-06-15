/**
 * Copy helper for the case "ReloPass Assistant" readiness summary.
 *
 * TASK-003 (AIQ-1042): the assistant summary previously counted a different
 * data source (`compliance.checks`) than the visible "Attention Needed"
 * checklist (`compliance.actions`), producing the factual contradiction
 * "0 blocking items remain" beside a non-empty checklist. The count passed in
 * here MUST come from the same array the checklist renders, so the message can
 * never disagree with what the employee sees.
 */
export function blockerSummaryMessage(count: number, topTask?: string): string {
  if (count <= 0) {
    return 'Your case is on track — no items are blocking your plan right now.';
  }
  const noun = count === 1 ? 'item' : 'items';
  const lead = `You have ${count} ${noun} to complete before your plan can move forward.`;
  const top = topTask?.trim();
  return top ? `${lead} The most important: ${top}.` : lead;
}
