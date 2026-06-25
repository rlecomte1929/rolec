/**
 * Immigration → vendor RFQ context — IMM-15 (AIQ-121)
 *
 * Shared shape threaded from ImmigrationStatusPanel → VendorBrowsePanel → RfqModal
 * so that an RFQ raised against an immigration vendor is pre-loaded with the
 * case's visa type, corridor, move date, and the employee's specific situation.
 */

export type ImmigrationContext = {
  visa_type?: string;
  corridor_from?: string;
  corridor_to?: string;
  move_date?: string;            // ISO date YYYY-MM-DD (sourced from the case)
  employee_nationality?: string;
  has_dependents?: boolean;
  dependents_count?: number;
  risk_flags?: Array<{ flag_type: string; title: string }>;
};

/** "blue_card" → "Blue Card" */
const humanizeVisaType = (visa: string): string =>
  visa
    .split('_')
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(' ');

/**
 * Human-readable one-paragraph summary HR can review and edit before sending.
 * Example:
 *   "Blue Card application, FR→DE corridor. Employee is Indian national.
 *    Move date: 2026-09-01. Dependents: 1. Risk flags: BfA pre-approval needed."
 */
export function buildImmigrationSummary(ctx: ImmigrationContext): string {
  const parts: string[] = [];

  if (ctx.visa_type) {
    const visa = `${humanizeVisaType(ctx.visa_type)} application`;
    if (ctx.corridor_from && ctx.corridor_to) {
      parts.push(`${visa}, ${ctx.corridor_from}→${ctx.corridor_to} corridor.`);
    } else {
      parts.push(`${visa}.`);
    }
  } else if (ctx.corridor_from && ctx.corridor_to) {
    parts.push(`${ctx.corridor_from}→${ctx.corridor_to} corridor.`);
  }

  if (ctx.employee_nationality) {
    parts.push(`Employee is ${ctx.employee_nationality} national.`);
  }

  if (ctx.move_date) {
    parts.push(`Move date: ${ctx.move_date}.`);
  }

  if (ctx.has_dependents && ctx.dependents_count && ctx.dependents_count > 0) {
    const n = ctx.dependents_count;
    parts.push(`Dependents: ${n} ${n === 1 ? 'dependent' : 'dependents'}.`);
  }

  if (ctx.risk_flags && ctx.risk_flags.length > 0) {
    const titles = ctx.risk_flags.map((f) => f.title).filter(Boolean);
    if (titles.length > 0) {
      parts.push(`Risk flags: ${titles.join('; ')}.`);
    }
  }

  return parts.join(' ');
}
