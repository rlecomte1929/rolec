/**
 * AIQ-2268 — HR duty-of-care & compliance command board.
 *
 * Per-case red/amber/green roll-up. Untracked signals (A1, medical, insurance)
 * render as Not tracked — never green.
 */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Alert, Badge, Card } from '../components/antigravity';
import { AppShell } from '../components/AppShell';
import { RiskBadge, type RiskStatus } from '../components/command-center/RiskBadge';
import { listDutyOfCare, isUntracked, type DutyOfCareStatus } from '../api/dutyOfCare';
import { buildRoute } from '../navigation/routes';

function overallRisk(status: DutyOfCareStatus): RiskStatus | null {
  if (status === 'red') return 'red';
  if (status === 'amber') return 'yellow';
  if (status === 'green') return 'green';
  return null;
}

function SignalPill({ status, label }: { status: DutyOfCareStatus; label?: string }) {
  const text =
    label ??
    (status === 'not_tracked'
      ? 'Not tracked'
      : status === 'unknown'
        ? 'Unknown'
        : status === 'amber'
          ? 'Amber'
          : status.charAt(0).toUpperCase() + status.slice(1));
  if (isUntracked(status)) {
    return (
      <Badge variant="neutral" size="sm">
        {text}
      </Badge>
    );
  }
  const variant =
    status === 'red' ? 'error' : status === 'amber' ? 'warning' : 'success';
  return (
    <Badge variant={variant} size="sm">
      {text}
    </Badge>
  );
}

export function HrDutyOfCareBoard() {
  const q = useQuery({
    queryKey: ['hr', 'duty-of-care'],
    queryFn: listDutyOfCare,
  });

  const cases = q.data?.cases ?? [];
  const allUnknown =
    cases.length > 0 &&
    cases.every((row) => row.overall === 'unknown' && isUntracked(row.permit.status));

  return (
    <AppShell
      section="HR Operations"
      title="Duty of care"
      subtitle="Permit, checklist, and open compliance alerts for each active case. Untracked signals stay grey."
    >
      {q.isError && (
        <Alert variant="error" title="Could not load the board" className="mb-4">
          Try again. The board is company-scoped on the server; a failure here is not an all-clear.
        </Alert>
      )}
      {allUnknown && (
        <Alert variant="info" title="No tracked permit or checklist data yet" className="mb-4">
          Unknown means ReloPass has not recorded that signal for the case — it is not an all-clear.
          A1, medical, and insurance are not tracked in this version.
        </Alert>
      )}

      <Card padding="none" className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="border-b border-[#e2e8f0] bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Overall</th>
                <th className="px-4 py-3">Permit</th>
                <th className="px-4 py-3">A1 / CoC</th>
                <th className="px-4 py-3">Medical</th>
                <th className="px-4 py-3">Insurance</th>
                <th className="px-4 py-3">Checklist</th>
                <th className="px-4 py-3">Departing</th>
              </tr>
            </thead>
            <tbody>
              {!q.isLoading && cases.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-slate-600">
                    No active cases for this company.
                  </td>
                </tr>
              )}
              {q.isLoading && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-slate-500">
                    Loading…
                  </td>
                </tr>
              )}
              {cases.map((row) => {
                const risk = overallRisk(row.overall);
                return (
                  <tr key={row.case_id} className="border-b border-[#e2e8f0] last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        className="font-medium text-[#0b2b43] underline-offset-2 hover:underline"
                        to={buildRoute('hrCaseSummary', { caseId: row.case_id })}
                      >
                        {row.employee_name || row.employee_id || row.case_id}
                      </Link>
                      <div className="text-xs text-slate-500">
                        {[row.home_country, row.host_country].filter(Boolean).join(' → ')}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {risk ? (
                        <span className="inline-flex items-center gap-2">
                          <RiskBadge status={risk} size="sm" />
                          <SignalPill status={row.overall} />
                        </span>
                      ) : (
                        <SignalPill status={row.overall} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <SignalPill status={row.permit.status} />
                      {row.permit.expiry_date && (
                        <div className="mt-1 text-xs text-slate-500">{row.permit.expiry_date}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <SignalPill status={row.a1.status} />
                    </td>
                    <td className="px-4 py-3">
                      <SignalPill status={row.medical.status} />
                    </td>
                    <td className="px-4 py-3">
                      <SignalPill status={row.insurance.status} />
                    </td>
                    <td className="px-4 py-3">
                      <SignalPill status={row.checklist.status} />
                      {row.checklist.total > 0 && (
                        <div className="mt-1 text-xs text-slate-500">
                          {row.checklist.completed}/{row.checklist.total}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {row.departing_soon ? (
                        <Badge variant="warning" size="sm">
                          ≤30 days
                        </Badge>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          —
                        </Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}

export default HrDutyOfCareBoard;
