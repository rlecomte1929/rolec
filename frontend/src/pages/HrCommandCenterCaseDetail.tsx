import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { getAuthItem } from '../utils/demo';
import { Card, Button } from '../components/antigravity';
import { RiskBadge } from '../components/command-center/RiskBadge';
import { hrAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';

export const HrCommandCenterCaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const role = getAuthItem('relopass_role');
  useEffect(() => {
    if (role && role !== 'HR' && role !== 'ADMIN') {
      safeNavigate(navigate, 'landing');
    }
  }, [role, navigate]);
  const [detail, setDetail] = useState<{
    id: string;
    employeeIdentifier: string;
    destCountry?: string;
    status: string;
    riskStatus: string;
    budgetLimit?: number;
    budgetEstimated?: number;
    expectedStartDate?: string;
    tasksTotal: number;
    tasksDone: number;
    tasksOverdue: number;
    phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>;
    events: Array<{ event_type: string; description?: string; created_at: string }>;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    hrAPI.getCommandCenterCaseDetail(id)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err: { response?: { status?: number } }) => {
        if (!cancelled && err?.response?.status === 401) safeNavigate(navigate, 'landing');
        if (!cancelled) setDetail(null);
      })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [id, navigate]);

  const budgetStatus = (): 'Within' | 'Approaching' | 'Exceeded' | null => {
    if (!detail?.budgetLimit || detail.budgetEstimated == null) return null;
    const pct = (detail.budgetEstimated / detail.budgetLimit) * 100;
    if (pct > 100) return 'Exceeded';
    if (pct >= 90) return 'Approaching';
    return 'Within';
  };

  if (isLoading) {
    return (
      <AppShell title="Case Detail" subtitle="Loading...">
        <div className="text-sm text-[#6b7280] py-8">Loading...</div>
      </AppShell>
    );
  }
  if (!detail) {
    return (
      <AppShell title="Case Detail" subtitle="Not found">
        <div className="text-sm text-[#6b7280] py-8">Case not found or not visible.</div>
        <Button variant="outline" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
          Back to Command Center
        </Button>
      </AppShell>
    );
  }

  const bStatus = budgetStatus();

  return (
    <AppShell title="Case Detail" subtitle={`${detail.employeeIdentifier} · ${detail.destCountry || '—'}`}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold text-[#0b2b43]">{detail.employeeIdentifier}</h1>
            <RiskBadge status={detail.riskStatus as 'green' | 'yellow' | 'red'} showLabel />
            <span className="text-sm text-[#6b7280]">{detail.destCountry || '—'}</span>
          </div>
          <Button variant="outline" onClick={() => navigate(buildRoute('hrAssignmentReview', { id: detail.id }))}>
            Open in Employee Dashboard
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Timeline / Phases */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Phase progression</div>
            <div className="space-y-3">
              {detail.phases.length === 0 ? (
                <div className="text-sm text-[#94a3b8]">No phases defined yet.</div>
              ) : (
                detail.phases.map((ph) => (
                  <div key={ph.phase} className="border-l-2 border-[#e2e8f0] pl-4">
                    <div className="text-sm font-medium text-[#4b5563]">{ph.phase}</div>
                    <ul className="mt-1 space-y-1 text-sm text-[#6b7280]">
                      {ph.tasks.map((t, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className={t.status === 'overdue' ? 'text-[#ef4444] font-medium' : ''}>
                            {t.title}
                          </span>
                          <span className="text-xs text-[#94a3b8]">{t.status}</span>
                          {t.due_date && <span className="text-xs">· {t.due_date}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Task completion */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Task completion</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold text-[#0b2b43]">
                {detail.tasksTotal ? Math.round((detail.tasksDone / detail.tasksTotal) * 100) : 0}%
              </span>
              <span className="text-sm text-[#6b7280]">
                {detail.tasksDone} of {detail.tasksTotal} completed
              </span>
            </div>
            {detail.tasksOverdue > 0 && (
              <div className="mt-2 text-sm text-[#ef4444] font-medium">
                {detail.tasksOverdue} overdue task(s)
              </div>
            )}
          </Card>

          {/* Budget */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Budget overview</div>
            <div className="space-y-2 text-sm">
              <div>Limit: {detail.budgetLimit != null ? detail.budgetLimit : '—'}</div>
              <div>Estimated: {detail.budgetEstimated != null ? detail.budgetEstimated : '—'}</div>
              {bStatus && (
                <div className={`font-medium ${bStatus === 'Exceeded' ? 'text-[#ef4444]' : bStatus === 'Approaching' ? 'text-[#eab308]' : 'text-[#22c55e]'}`}>
                  Status: {bStatus}
                </div>
              )}
            </div>
          </Card>

          {/* Activity log */}
          <Card padding="lg" className="lg:col-span-2">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Activity log</div>
            {detail.events.length === 0 ? (
              <div className="text-sm text-[#94a3b8]">No events yet.</div>
            ) : (
              <ul className="space-y-3">
                {detail.events.map((e, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="text-[#94a3b8] shrink-0">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                    </span>
                    <span className="font-medium text-[#4b5563]">{e.event_type}</span>
                    {e.description && <span className="text-[#6b7280]">{e.description}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <Button variant="outline" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
          Back to Command Center
        </Button>
      </div>
    </AppShell>
  );
};
