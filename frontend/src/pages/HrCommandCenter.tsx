import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { getAuthItem } from '../utils/demo';
import { Card } from '../components/antigravity';
import { KPICard } from '../components/command-center/KPICard';
import { RiskBadge } from '../components/command-center/RiskBadge';
import { hrAPI } from '../api/client';
import { safeNavigate } from '../navigation/safeNavigate';

type CaseRow = {
  id: string;
  employeeIdentifier: string;
  destCountry?: string;
  status: string;
  riskStatus: string;
  tasksDonePercent: number;
  budgetLimit?: number;
  budgetEstimated?: number;
  nextDeadline?: string;
};

export const HrCommandCenter: React.FC = () => {
  const navigate = useNavigate();
  const role = getAuthItem('relopass_role');
  useEffect(() => {
    if (role && role !== 'HR' && role !== 'ADMIN') {
      safeNavigate(navigate, 'landing');
    }
  }, [role, navigate]);
  const [kpis, setKpis] = useState<{
    activeCases: number;
    atRiskCount: number;
    attentionNeededCount: number;
    overdueTasksCount: number;
    budgetOverrunsCount: number;
    actionRequiredCount: number;
    departingSoonCount: number;
    completedCount: number;
  } | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [kpisLoading, setKpisLoading] = useState(true);
  const [casesLoading, setCasesLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [riskFilter, setRiskFilter] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    async function loadKpis() {
      setKpisLoading(true);
      try {
        const k = await hrAPI.getCommandCenterKPIs();
        if (!cancelled) setKpis(k);
      } catch (err: unknown) {
        if (!cancelled && (err as { response?: { status?: number } })?.response?.status === 401) {
          safeNavigate(navigate, 'landing');
        }
      } finally {
        if (!cancelled) setKpisLoading(false);
      }
    }
    loadKpis();
    return () => { cancelled = true; };
  }, [navigate]);

  useEffect(() => {
    let cancelled = false;
    async function loadCases() {
      setCasesLoading(true);
      try {
        const c = await hrAPI.listCommandCenterCases({ page, limit: 25, risk_filter: riskFilter || undefined });
        if (!cancelled) setCases(c);
      } catch (err: unknown) {
        if (!cancelled && (err as { response?: { status?: number } })?.response?.status === 401) {
          safeNavigate(navigate, 'landing');
        }
        if (!cancelled) setCases([]);
      } finally {
        if (!cancelled) setCasesLoading(false);
      }
    }
    loadCases();
    return () => { cancelled = true; };
  }, [navigate, page, riskFilter]);

  const handleRowClick = (id: string) => {
    navigate(`/hr/command-center/cases/${id}`);
  };

  return (
    <AppShell title="Command Center" subtitle="Portfolio view and risk signals across cases.">
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
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex gap-4 py-3 border-b border-[#e2e8f0] last:border-0">
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-32" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-16" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-24" />
                </div>
              ))}
            </div>
          ) : cases.length === 0 ? (
            <div className="text-sm text-[#6b7280] py-8">No cases match your criteria.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280]">
                    <th className="py-3 pr-4 font-medium">Employee</th>
                    <th className="py-3 pr-4 font-medium">Country</th>
                    <th className="py-3 pr-4 font-medium">Status</th>
                    <th className="py-3 pr-4 font-medium">Risk</th>
                    <th className="py-3 pr-4 font-medium">Tasks Done %</th>
                    <th className="py-3 pr-4 font-medium">Budget</th>
                    <th className="py-3 font-medium">Next Deadline</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((row) => (
                    <tr
                      key={row.id}
                      onClick={() => handleRowClick(row.id)}
                      className="border-b border-[#f1f5f9] hover:bg-[#f8fafc] cursor-pointer transition-colors"
                    >
                      <td className="py-3 pr-4 text-[#0b2b43] font-medium">{row.employeeIdentifier}</td>
                      <td className="py-3 pr-4 text-[#4b5563]">{row.destCountry || '-'}</td>
                      <td className="py-3 pr-4 text-[#4b5563]">{row.status}</td>
                      <td className="py-3 pr-4">
                        <RiskBadge status={row.riskStatus as 'green' | 'yellow' | 'red'} size="sm" />
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
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="py-1 text-sm text-[#6b7280]">Page {page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1 text-sm"
              >
                Next
              </button>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
};
