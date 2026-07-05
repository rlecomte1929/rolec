/**
 * AIQ-1416 — HR mobility-manager risk dashboard ("SmartSights"-style).
 *
 * One screen, three risk signals, built entirely on EXISTING company-scoped HR data:
 *   A. Relocations at risk        — REAL (command-center KPIs + cases)
 *   B. Cost overruns              — honest "not tracked yet" (no real per-case spend exists)
 *   C. Upcoming visa/permit expiry — REAL endpoint (/api/compliance/alerts), empty until data is captured
 *
 * Real-or-honest-empty: we never fabricate cost/visa numbers. All queries are company-scoped
 * server-side (tenant isolation). Partial failures degrade gracefully (Promise.allSettled) and the
 * 12s axios timeout guarantees no eternal spinner.
 */
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ShieldAlert, Wallet, PlaneTakeoff, RefreshCw } from 'lucide-react';
import { AppShell } from '../../../components/AppShell';
import { Alert, Badge, Button, Card } from '../../../components/antigravity';
import { hrAPI } from '../../../api/client';
import { listExceptionRequestsForCompany } from '../../../api/exceptions';
import { listComplianceAlerts } from '../../../api/compliance';
import { deriveRiskItems, isVisaAlert, daysUntil } from './riskDashboard.helpers';

type Tone = 'default' | 'danger' | 'warning' | 'accent';
function Kpi({ label, value, tone = 'default' }: { label: string; value: string | number; tone?: Tone }) {
  const toneCls: Record<Tone, string> = {
    default: 'text-[#0b2b43]',
    danger: 'text-rose-600',
    warning: 'text-amber-600',
    accent: 'text-accent-700',
  };
  return (
    <Card padding="md">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${toneCls[tone]}`}>{value}</div>
    </Card>
  );
}

function slaBadge(sla?: string | null) {
  if (sla === 'overdue') return <Badge variant="error" size="sm">Overdue</Badge>;
  if (sla === 'at_risk') return <Badge variant="warning" size="sm">At risk</Badge>;
  return <Badge variant="neutral" size="sm">On track</Badge>;
}

export function HrRiskDashboardPage() {
  const q = useQuery({
    queryKey: ['hr', 'risk'],
    queryFn: async () => {
      const [kpisR, casesR, apprR, alertsR] = await Promise.allSettled([
        hrAPI.getCommandCenterKPIs(),
        hrAPI.listCommandCenterCases({ page: 1, limit: 100 }),
        listExceptionRequestsForCompany('pending'),
        listComplianceAlerts(),
      ]);
      return {
        kpis: kpisR.status === 'fulfilled' ? kpisR.value : null,
        cases: casesR.status === 'fulfilled' ? casesR.value : [],
        degraded: kpisR.status === 'rejected' || casesR.status === 'rejected',
        pendingApprovals: apprR.status === 'fulfilled' ? apprR.value.length : 0,
        alerts: alertsR.status === 'fulfilled' ? alertsR.value.alerts : [],
      };
    },
  });

  const loading = q.isLoading;
  const data = q.data;
  const kpis = data?.kpis ?? null;
  const riskItems = deriveRiskItems(data?.cases ?? []);
  const visaAlerts = (data?.alerts ?? []).filter(isVisaAlert).sort((a, b) => daysUntil(a) - daysUntil(b));

  const loadingValue = (v: number | undefined) => (v ?? (loading ? '…' : 0));

  return (
    <AppShell
      section="HR Operations"
      title="Risk"
      subtitle="At-risk relocations, cost, and visa expirations for your company — on one screen."
    >
      {data?.degraded && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5">
          <p className="text-sm text-amber-900">Some data couldn&rsquo;t load — showing partial results.</p>
          <Button size="sm" variant="outline" onClick={() => q.refetch()}>
            <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden /> Retry
          </Button>
        </div>
      )}

      {/* KPI strip — real risk metrics only */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="At risk" value={loadingValue(kpis?.atRiskCount)} tone="danger" />
        <Kpi label="Needs attention" value={loadingValue(kpis?.attentionNeededCount)} tone="warning" />
        <Kpi label="Overdue tasks" value={loadingValue(kpis?.overdueTasksCount)} tone="warning" />
        <Kpi label="Pending approvals" value={loadingValue(data?.pendingApprovals)} tone="accent" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {/* A. Relocations at risk — REAL */}
        <Card padding="lg" className="lg:col-span-2">
          <div className="flex items-center gap-2 text-[#0b2b43]">
            <AlertTriangle className="h-5 w-5 text-rose-600" aria-hidden />
            <h2 className="text-base font-semibold">Relocations at risk</h2>
          </div>
          {loading ? (
            <div className="mt-3 space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
              ))}
            </div>
          ) : riskItems.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">All relocations on track.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
              {riskItems.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-[#0b2b43]">{c.employeeIdentifier}</div>
                    <div className="text-xs text-slate-500">
                      {[c.originCountry, c.destCountry].filter(Boolean).join(' → ') || 'Corridor not set'}
                      {typeof c.daysUntilMove === 'number' && (
                        <> · {c.daysUntilMove < 0 ? `${Math.abs(c.daysUntilMove)}d overdue` : `${c.daysUntilMove}d to move`}</>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {c.riskStatus === 'red' ? (
                      <Badge variant="error" size="sm">Red</Badge>
                    ) : (
                      <Badge variant="warning" size="sm">Yellow</Badge>
                    )}
                    {slaBadge(c.slaStatus)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          {/* B. Cost overruns — honest empty (no real spend source) */}
          <Card padding="lg">
            <div className="flex items-center gap-2 text-[#0b2b43]">
              <Wallet className="h-5 w-5 text-slate-500" aria-hidden />
              <h2 className="text-base font-semibold">Cost overruns</h2>
            </div>
            <Alert variant="info" className="mt-3">
              Per-case spend isn&rsquo;t captured yet, so overruns can&rsquo;t be computed. Policy budget caps are set
              per policy; actuals-vs-cap will appear here once spend tracking ships.
            </Alert>
          </Card>

          {/* C. Upcoming visa/permit expirations — real endpoint, empty until data captured */}
          <Card padding="lg">
            <div className="flex items-center gap-2 text-[#0b2b43]">
              <PlaneTakeoff className="h-5 w-5 text-accent-600" aria-hidden />
              <h2 className="text-base font-semibold">Upcoming visa / permit expirations</h2>
            </div>
            {loading ? (
              <div className="mt-3 h-10 animate-pulse rounded bg-slate-100" />
            ) : visaAlerts.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">
                No upcoming visa or permit expirations — alerts appear here as permit/visa expiry dates are
                captured for your cases.
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
                {visaAlerts.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className="min-w-0 truncate text-[#0b2b43]">{a.description ?? a.category}</span>
                    {Number.isFinite(daysUntil(a)) && (
                      <Badge variant={daysUntil(a) <= 14 ? 'error' : 'warning'} size="sm">
                        {daysUntil(a)}d
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-500">
        <ShieldAlert className="h-3.5 w-3.5" aria-hidden /> Company-scoped. Built on live command-center data;
        cost and visa signals populate as that data is captured.
      </p>
    </AppShell>
  );
}
