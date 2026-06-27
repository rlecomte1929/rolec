import React, { useEffect, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/antigravity/Button';
import { AppShell } from '../components/AppShell';
import { getAuthItem } from '../utils/demo';
import { Card } from '../components/antigravity';
import { KPICard } from '../components/command-center/KPICard';
import { RiskBadge } from '../components/command-center/RiskBadge';
import { SLABadge } from '../components/command-center/SLABadge';
import { hrAPI } from '../api/client';
import { safeNavigate } from '../navigation/safeNavigate';
import { HrExceptionsQueueCard } from '../features/exceptions/HrExceptionsQueueCard';
import { ComplianceAlertsPanel } from '../features/hr/ComplianceAlertsPanel';

type CaseRow = {
  id: string;
  employeeIdentifier: string;
  destCountry?: string | null;
  status: string;
  riskStatus: string;
  tasksDonePercent: number;
  budgetLimit?: number | null;
  budgetEstimated?: number | null;
  nextDeadline?: string | null;
  slaStatus?: 'on_track' | 'at_risk' | 'overdue' | string | null;
  daysUntilMove?: number | null;
};

export const HrCommandCenter: React.FC = () => {
  const navigate = useNavigate();
  const role = getAuthItem('relopass_role');
  useEffect(() => {
    if (role && role !== 'HR' && role !== 'ADMIN') {
      safeNavigate(navigate, 'landing');
    }
  }, [role, navigate]);
  const [page, setPage] = useState(1);
  const [riskFilter, setRiskFilter] = useState<string>('');

  const kpisQuery = useQuery({
    queryKey: ['hr', 'command-center', 'kpis'],
    queryFn: () => hrAPI.getCommandCenterKPIs(),
  });

  const casesQuery = useQuery({
    queryKey: ['hr', 'command-center', 'cases', { page, riskFilter: riskFilter || undefined }],
    queryFn: () => hrAPI.listCommandCenterCases({ page, limit: 25, risk_filter: riskFilter || undefined }),
    // Keep the prior page visible while the next one loads (the hand-rolled
    // version left the old rows up and only swapped on resolve).
    placeholderData: keepPreviousData,
  });

  const kpis: {
    activeCases: number;
    atRiskCount: number;
    attentionNeededCount: number;
    overdueTasksCount: number;
    budgetOverrunsCount: number;
    actionRequiredCount: number;
    departingSoonCount: number;
    completedCount: number;
  } | null = kpisQuery.data ?? null;
  const cases: CaseRow[] = casesQuery.data ?? [];
  const kpisLoading = kpisQuery.isLoading;
  const casesLoading = casesQuery.isLoading;

  // Preserve the 401 → landing redirect from both reads.
  useEffect(() => {
    const kStatus = (kpisQuery.error as { response?: { status?: number } } | null)?.response?.status;
    const cStatus = (casesQuery.error as { response?: { status?: number } } | null)?.response?.status;
    if (kStatus === 401 || cStatus === 401) safeNavigate(navigate, 'landing');
  }, [kpisQuery.error, casesQuery.error, navigate]);

  const handleRowClick = (id: string) => {
    navigate(`/hr/command-center/cases/${id}`);
  };

  return (
    <AppShell section="HR Operations" title="Dashboard" subtitle="Portfolio view and risk signals across cases.">
      <div className="space-y-6">
        {/* KPI Row: shell visible immediately, values stream in */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          <KPICard title="Active Cases" value={kpisLoading && kpis == null ? '…' : (kpis?.activeCases ?? '-')} />
          <KPICard title="Action Required" value={kpisLoading && kpis == null ? '…' : (kpis?.actionRequiredCount ?? '-')} subtitle="Needs HR attention" />
          <KPICard title="Departing Soon" value={kpisLoading && kpis == null ? '…' : (kpis?.departingSoonCount ?? '-')} subtitle="Next 30 days" />
          <KPICard title="Completed (YTD)" value={kpisLoading && kpis == null ? '…' : (kpis?.completedCount ?? '-')} subtitle="Approved cases" />
          <KPICard title="At Risk" value={kpisLoading && kpis == null ? '…' : (kpis?.atRiskCount ?? '-')} subtitle="Red" />
          <KPICard title="Attention Needed" value={kpisLoading && kpis == null ? '…' : (kpis?.attentionNeededCount ?? '-')} subtitle="Yellow" />
          <KPICard title="Overdue Tasks" value={kpisLoading && kpis == null ? '…' : (kpis?.overdueTasksCount ?? '-')} />
          <KPICard title="Budget Overruns" value={kpisLoading && kpis == null ? '…' : (kpis?.budgetOverrunsCount ?? '-')} />
        </div>

        <HrExceptionsQueueCard />

        <ComplianceAlertsPanel />

        {/* Cases Table: shell visible immediately */}
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[#0b2b43]">Cases</h2>
            <select
              value={riskFilter}
              onChange={(e) => { setRiskFilter(e.target.value); setPage(1); }}
              className="rounded-lg border border-[#e2e8f0] px-3 py-1.5 text-sm"
            >
              <option value="">All risk levels</option>
              <option value="green">Green</option>
              <option value="yellow">Yellow</option>
              <option value="red">Red</option>
            </select>
          </div>
          {casesLoading && cases.length === 0 ? (
            <div className="space-y-2 py-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4 py-3 border-b border-[#e2e8f0] last:border-0">
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-32" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-16" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-24" />
                </div>
              ))}
            </div>
          ) : cases.length === 0 ? (
            /* Stage 6 (audit): empty-state copy per docs/product-copy-rules.md */
            <div className="py-10 text-center">
              <p className="text-sm font-medium text-[#0b2b43] mb-1">No cases match this filter</p>
              <p className="text-sm text-[#6b7280]">
                Try changing the risk level or destination above, or clear the search box to see every case.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280]">
                    <th className="py-3 pr-4 font-medium">Employee</th>
                    <th className="py-3 pr-4 font-medium">Country</th>
                    <th className="py-3 pr-4 font-medium">Status</th>
                    <th className="py-3 pr-4 font-medium">Risk</th>
                    <th className="py-3 pr-4 font-medium">SLA</th>
                    <th className="py-3 pr-4 font-medium">Tasks Done %</th>
                    <th className="py-3 pr-4 font-medium">Budget</th>
                    <th className="py-3 font-medium">Next Deadline</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((row) => (
                    <tr
                      key={row.id}
                      role="button"
                      onClick={() => handleRowClick(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleRowClick(row.id); } }}
                      tabIndex={0}
                      className="border-b border-[#f1f5f9] hover:bg-[#f8fafc] cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b2b43]"
                    >
                      <td className="py-3 pr-4 text-[#0b2b43] font-medium">{row.employeeIdentifier}</td>
                      <td className="py-3 pr-4 text-[#4b5563]">{row.destCountry || '-'}</td>
                      <td className="py-3 pr-4 text-[#4b5563]">{row.status}</td>
                      <td className="py-3 pr-4">
                        <RiskBadge status={row.riskStatus as 'green' | 'yellow' | 'red'} size="sm" />
                      </td>
                      <td className="py-3 pr-4">
                        <SLABadge status={row.slaStatus} daysUntilMove={row.daysUntilMove} size="sm" />
                      </td>
                      <td className="py-3 pr-4 text-[#4b5563]">{row.tasksDonePercent}%</td>
                      <td className="py-3 pr-4 text-[#4b5563]">
                        {row.budgetEstimated != null && row.budgetLimit != null
                          ? `${row.budgetEstimated} / ${row.budgetLimit}`
                          : '-'}
                      </td>
                      <td className="py-3 text-[#4b5563]">{row.nextDeadline || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {cases.length >= 25 && (
            <div className="mt-4 flex justify-center gap-2">
              <Button unstyled
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1 text-sm disabled:opacity-50"
              >
                Previous
              </Button>
              <span className="py-1 text-sm text-[#6b7280]">Page {page}</span>
              <Button unstyled
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1 text-sm"
              >
                Next
              </Button>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
};
