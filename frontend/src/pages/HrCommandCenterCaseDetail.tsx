import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { getAuthItem } from '../utils/demo';
import { Card, Button } from '../components/antigravity';
import { RiskBadge } from '../components/command-center/RiskBadge';
import { hrAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import { ExceptionFlagsPanel } from '../components/case/ExceptionFlagsPanel';
import { HrCaseTasksPanel } from '../components/case/HrCaseTasksPanel';
import { VendorBrowsePanel } from '../components/case/VendorBrowsePanel';
import { RfqModal } from '../components/case/RfqModal';
import { PendingRfqsPanel } from '../components/case/PendingRfqsPanel';
import { ImmigrationStatusPanel } from '../components/case/ImmigrationStatusPanel';
import { AdvisorsPanel } from '../components/case/AdvisorsPanel';
import { AssignmentExceptionsPanel } from '../components/case/AssignmentExceptionsPanel';
import { PetRequirementsSection } from '../components/case/PetRequirementsSection';

type QuoteRequest = {
  id: string;
  case_id: string;
  employee_id: string;
  company_id: string;
  service_categories: string[];
  notes: string | null;
  budget_range: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export const HrCommandCenterCaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
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

  // Quote requests for this case
  const [quoteRequests, setQuoteRequests] = useState<QuoteRequest[]>([]);
  const [updatingQrId, setUpdatingQrId] = useState<string | null>(null);

  // Vendor browse panel + RFQ modal
  const [vendorPanelOpen, setVendorPanelOpen] = useState(false);
  const [vendorPanelInitialCategory, setVendorPanelInitialCategory] = useState('');
  const [rfqVendor, setRfqVendor] = useState<{ id: string; name: string; service_categories: string[]; contact_email: string } | null>(null);
  const [rfqSuccessMsg, setRfqSuccessMsg] = useState('');
  const [rfqListKey, setRfqListKey] = useState(0);

  const loadQuoteRequests = useCallback(() => {
    if (!id) return;
    hrAPI
      .getQuoteRequests({ case_id: id })
      .then((res) => setQuoteRequests(res.quote_requests))
      .catch(() => setQuoteRequests([]));
  }, [id]);

  useEffect(() => {
    loadQuoteRequests();
  }, [loadQuoteRequests]);

  const handleQuoteStatusUpdate = async (
    qrId: string,
    status: 'acknowledged' | 'fulfilled'
  ) => {
    setUpdatingQrId(qrId);
    try {
      await hrAPI.updateQuoteRequestStatus(qrId, status);
      loadQuoteRequests();
    } catch {
      // silently fail — HR can retry
    } finally {
      setUpdatingQrId(null);
    }
  };

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
  }, [id, navigate, location.key]);

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
    <AppShell title="Case Detail" subtitle={`${detail.employeeIdentifier} · ${detail.destCountry || '-'}`}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold text-[#0b2b43]">{detail.employeeIdentifier}</h1>
            <RiskBadge status={detail.riskStatus as 'green' | 'yellow' | 'red'} showLabel />
            <span className="text-sm text-[#6b7280]">{detail.destCountry || '-'}</span>
          </div>
          <Button variant="outline" onClick={() => navigate(buildRoute('hrAssignmentReview', { id: detail.id }))}>
            Open in Employee Dashboard
          </Button>
        </div>

        {/* ── Exception flags (P3/B6): blockers + warnings from immigration check ── */}
        <ExceptionFlagsPanel caseId={detail.id} />

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
              <div>Limit: {detail.budgetLimit != null ? detail.budgetLimit : '-'}</div>
              <div>Estimated: {detail.budgetEstimated != null ? detail.budgetEstimated : '-'}</div>
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
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '-'}
                    </span>
                    <span className="font-medium text-[#4b5563]">{e.event_type}</span>
                    {e.description && <span className="text-[#6b7280]">{e.description}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* ── Employee Tasks (AIQ-34-C) — polls every 8s ── */}
        <HrCaseTasksPanel caseId={detail.id} />

        {/* ── IMM-13: Immigration status panel ── */}
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">Immigration status</div>
              <p className="text-xs text-[#94a3b8] mt-0.5">Documents, risk flags and employee interview progress</p>
            </div>
          </div>
          <ImmigrationStatusPanel
            caseId={detail.id}
            onFindVendor={() => {
              setVendorPanelInitialCategory('Immigration/visa');
              setVendorPanelOpen(true);
            }}
            onViewProfile={() => {
              navigate(buildRoute('hrAssignmentReview', { id: detail.id }));
            }}
          />
        </Card>

        {/* ── GAP 4: Immigration advisors matched to corridor ── */}
        <AdvisorsPanel
          destinationCountry={detail.destCountry}
        />

        {/* ── AIQ-160-E: Pet import requirements for destination country ── */}
        <PetRequirementsSection
          caseId={detail.id}
          destCountry={detail.destCountry}
        />

        {/* ── GAP 7: Assignment-level policy exception requests ── */}
        <AssignmentExceptionsPanel assignmentId={detail.id} />

        {/* ── AIQ-40-D: Vendor RFQs (sent by HR, tracked here) ── */}
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">Vendor quote requests</div>
              <p className="text-xs text-[#94a3b8] mt-0.5">RFQs you've sent to vendors for this case</p>
            </div>
            <button
              type="button"
              onClick={() => { setVendorPanelInitialCategory(''); setVendorPanelOpen(true); }}
              className="flex items-center gap-1.5 rounded-lg border border-[#0b2b43] bg-white px-3 py-1.5 text-xs font-medium text-[#0b2b43] hover:bg-[#f8fafc] transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Find a vendor
            </button>
          </div>
          <PendingRfqsPanel key={rfqListKey} caseId={detail.id} />
        </Card>

        {/* ── Quote Requests from employee (Step 4) ── */}
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-[#0b2b43]">
              Employee quote requests
              {quoteRequests.filter((q) => q.status === 'pending').length > 0 && (
                <span className="ml-2 inline-flex items-center justify-center rounded-full bg-[#fef3c7] border border-[#fbbf24] px-2 py-0.5 text-xs font-medium text-[#92400e]">
                  {quoteRequests.filter((q) => q.status === 'pending').length} pending
                </span>
              )}
            </div>
          </div>
          {quoteRequests.length === 0 ? (
            <p className="text-sm text-[#94a3b8]">No quote requests from the employee yet.</p>
          ) : (
            <ul className="space-y-3">
              {quoteRequests.map((qr) => (
                <li
                  key={qr.id}
                  className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap gap-1 mb-1">
                        {qr.service_categories.map((cat) => (
                          <span
                            key={cat}
                            className="rounded-full border border-[#bfdbfe] bg-[#eff6ff] px-2 py-0.5 text-xs text-[#1d4ed8]"
                          >
                            {cat}
                          </span>
                        ))}
                      </div>
                      {qr.notes && (
                        <p className="text-[#374151] text-xs mt-1 leading-relaxed">{qr.notes}</p>
                      )}
                      {qr.budget_range && (
                        <p className="text-[#64748b] text-xs mt-1">Budget: {qr.budget_range}</p>
                      )}
                      <p className="text-[#94a3b8] text-xs mt-1">
                        {new Date(qr.created_at).toLocaleDateString()} ·{' '}
                        <span
                          className={
                            qr.status === 'fulfilled'
                              ? 'text-[#16a34a]'
                              : qr.status === 'acknowledged'
                              ? 'text-[#2563eb]'
                              : 'text-[#d97706]'
                          }
                        >
                          {qr.status}
                        </span>
                      </p>
                    </div>
                    {qr.status === 'pending' && (
                      <button
                        type="button"
                        disabled={updatingQrId === qr.id}
                        onClick={() => handleQuoteStatusUpdate(qr.id, 'acknowledged')}
                        className="shrink-0 rounded-lg border border-[#2563eb] bg-white px-3 py-1.5 text-xs font-medium text-[#2563eb] hover:bg-[#eff6ff] disabled:opacity-50 transition-colors"
                      >
                        {updatingQrId === qr.id ? '…' : 'Acknowledge'}
                      </button>
                    )}
                    {qr.status === 'acknowledged' && (
                      <button
                        type="button"
                        disabled={updatingQrId === qr.id}
                        onClick={() => handleQuoteStatusUpdate(qr.id, 'fulfilled')}
                        className="shrink-0 rounded-lg border border-[#16a34a] bg-white px-3 py-1.5 text-xs font-medium text-[#16a34a] hover:bg-[#f0fdf4] disabled:opacity-50 transition-colors"
                      >
                        {updatingQrId === qr.id ? '…' : 'Mark fulfilled'}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Button variant="outline" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
          Back to Command Center
        </Button>
      </div>

      {/* ── AIQ-40-B: Vendor browse slide-over ── */}
      <VendorBrowsePanel
        isOpen={vendorPanelOpen}
        onClose={() => { setVendorPanelOpen(false); setVendorPanelInitialCategory(''); }}
        destCountry={detail.destCountry}
        initialCategory={vendorPanelInitialCategory}
        onRequestQuote={(vendor) => {
          setVendorPanelOpen(false);
          setVendorPanelInitialCategory('');
          setRfqVendor(vendor);
        }}
      />

      {/* ── AIQ-40-C: RFQ modal ── */}
      {rfqSuccessMsg && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl border border-[#bbf7d0] bg-[#f0fdf4] px-5 py-3 shadow-lg text-sm text-[#166534] font-medium">
          ✓ {rfqSuccessMsg}
          <button type="button" onClick={() => setRfqSuccessMsg('')} className="ml-3 text-[#16a34a] hover:text-[#166534]">✕</button>
        </div>
      )}
      <RfqModal
        vendor={rfqVendor}
        caseId={detail.id}
        onClose={() => setRfqVendor(null)}
        onSent={(vendorName) => {
          setRfqVendor(null);
          setRfqSuccessMsg(`Quote request sent to ${vendorName}`);
          setRfqListKey((k) => k + 1);
        }}
      />
    </AppShell>
  );
};
