/**
 * [AIQ-2041] "Needs your attention" — the HR action list.
 *
 * One row per case that is past a milestone's target date, most-behind first, each
 * with a concrete next step and a link to the case.
 *
 * WHY IT MOVED HERE. The panel already existed, on /hr/policy-dashboard — a route
 * nothing links to (it is in the AIQ-2086 orphan baseline), so no HR user had ever
 * seen it. It now sits on the Mobility command centre, which is in the sidebar and
 * is where HR already goes to see their cases.
 *
 * EVERY ITEM IS A REAL ROW. The list is `GET /api/hr/cases/behind-schedule`, which
 * reads deterministic signals from `public.case_milestones` — no model is involved
 * and nothing here can invent a case. `suggested_action` is a per-stage template
 * or, for a milestone type we do not recognise, that milestone's own curated title.
 */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { hrAPI, type CaseHealthFlag, type CommandCenterCaseRow } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { displayNameOrEmail } from '../../utils/caseDisplay';
import { getCountryName } from '../../utils/countries';

/** 'hr' reads as HR's own queue; everything else is someone HR chases. */
function ownerLabel(owner: string | null): string | null {
  const who = (owner || '').trim().toLowerCase();
  if (who === 'hr') return 'Waiting on you';
  if (who === 'employee') return 'Waiting on employee';
  if (who === 'joint') return 'Shared step';
  return null;
}

export function matchAttentionCase(
  flag: CaseHealthFlag,
  catalog: CommandCenterCaseRow[],
): CommandCenterCaseRow | undefined {
  return catalog.find((row) => row.caseId === flag.case_id || row.id === flag.case_id);
}

export function attentionOpenCaseAriaLabel(name: string, destination: string): string {
  return `Open case for ${name} (${destination})`;
}

function destinationLabel(row: CommandCenterCaseRow | undefined): string {
  const raw = row?.destCountry?.trim();
  if (!raw) return 'Destination not set';
  return getCountryName(raw) || raw;
}

export const HrCaseHealthPanel: React.FC<{ catalog?: CommandCenterCaseRow[] }> = ({
  catalog = [],
}) => {
  const query = useQuery({
    queryKey: ['hr', 'case-health'],
    queryFn: ({ signal }) => hrAPI.getCaseHealth({ signal }),
    staleTime: 60_000,
  });

  const cases: CaseHealthFlag[] = query.data?.cases ?? [];

  // Nothing to show while loading, and nothing to shout about when the query
  // failed — the case table below is the page's real content, so a spinner or an
  // error card here would be noise on a surface that is not the point of the page.
  if (query.isLoading || query.isError) return null;

  if (cases.length === 0) {
    // Honest and small: one reassuring line, not an empty hero card.
    return (
      <p className="mb-4 text-[13px] text-slate-500">
        No cases are behind schedule.
      </p>
    );
  }

  return (
    <section className="mb-5" aria-labelledby="hr-needs-attention">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 id="hr-needs-attention" className="text-[15px] font-semibold text-slate-900">
          Needs your attention
        </h2>
        <span className="text-[12px] text-slate-500">
          {cases.length} case{cases.length === 1 ? '' : 's'} behind schedule
        </span>
      </div>

      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {cases.map((c) => {
          const step = c.milestone_title || c.stage || 'Overdue step';
          const who = ownerLabel(c.owner);
          const matched = matchAttentionCase(c, catalog);
          const name = displayNameOrEmail(null, matched?.employeeIdentifier);
          const dest = destinationLabel(matched);
          const href = buildRoute('hrCommandCenterCase', { id: matched?.id ?? c.case_id });
          const ariaLabel = attentionOpenCaseAriaLabel(name, dest);
          return (
            <li key={c.case_id}>
              <Link
                to={href}
                aria-label={ariaLabel}
                className="flex min-h-6 flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-navy-800"
              >
                <span
                  className={`mt-0.5 inline-flex shrink-0 items-center rounded px-2 py-0.5 text-[11px] font-semibold ${
                    c.severity === 'critical'
                      ? 'border border-red-200 bg-red-50 text-red-700'
                      : 'border border-amber-200 bg-amber-50 text-amber-700'
                  }`}
                >
                  {c.days_behind != null ? `${c.days_behind}d behind` : 'behind'}
                </span>

                <div className="min-w-[220px] flex-1">
                  <p className="text-[13px] font-medium text-slate-800">{name}</p>
                  <p className="text-[12px] text-slate-500">
                    {matched?.employeeIdentifier && matched.employeeIdentifier !== name
                      ? `${matched.employeeIdentifier} · ${dest}`
                      : dest}
                  </p>
                  <p className="mt-0.5 text-[13px] text-slate-800">{step}</p>
                  <p className="text-[12px] text-slate-500">
                    {c.suggested_action ?? 'Review this case and follow up.'}
                  </p>
                </div>

                <div className="flex min-h-6 shrink-0 items-center gap-3">
                  {who && <span className="text-[12px] text-slate-500">{who}</span>}
                  <span className="inline-flex min-h-6 items-center text-[12px] font-medium text-navy-800 underline-offset-2 group-hover:underline">
                    Open case
                  </span>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
