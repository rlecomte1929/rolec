import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import { hrAPI, employeeAPI } from '../api/client';
import type { AssignmentDetail, AssignmentSummary, PolicyResponse, PolicySpendItem } from '../types';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { CaseIncompleteBanner } from '../components/CaseIncompleteBanner';
import { EmployeePolicyView } from '../features/policy/EmployeePolicyView';
import { getAuthItem } from '../utils/demo';
import { buildRoute } from '../navigation/routes';

const formatCurrency = (value: number | undefined | null, currency = 'USD') => {
  const safe = typeof value === 'number' && isFinite(value) ? value : 0;
  return safe.toLocaleString('en-US', { style: 'currency', currency, maximumFractionDigits: 0 });
};

const statusBadge = (status: PolicySpendItem['status']) => {
  if (status === 'OVER_LIMIT') return { label: 'OVER LIMIT', classes: 'bg-[#fef2f2] text-[#7a2a2a]' };
  if (status === 'NEAR_LIMIT') return { label: 'NEAR LIMIT', classes: 'bg-[#fff7ed] text-[#9a3412]' };
  return { label: 'ON TRACK', classes: 'bg-[#eaf5f4] text-[#1f8e8b]' };
};

function EmployeePolicyContent() {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    employeeAPI
      .getCurrentAssignment()
      .then((res) => {
        if (!cancelled && res?.assignment?.id) setAssignmentId(res.assignment.id);
      })
      .catch((err: any) => {
        if (!cancelled && err?.response?.status !== 401) setError('Unable to load your assignment.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div className="text-sm text-[#6b7280] py-8">Loading your policy...</div>;
  if (error) return <Alert variant="error">{error}</Alert>;
  if (!assignmentId) {
    return (
      <Card padding="lg">
        <p className="text-[#4b5563]">You don't have an active assignment yet. Once your case is assigned, your applicable policy and benefit limits will appear here.</p>
      </Card>
    );
  }
  return <EmployeePolicyView assignmentId={assignmentId} compact={false} />;
}

export const HrPolicy: React.FC = () => {
  const role = getAuthItem('relopass_role');
  if (role === 'EMPLOYEE') {
    return (
      <AppShell title="Assignment Package & Limits" subtitle="View your applicable policy and benefit limits.">
        <EmployeePolicyContent />
      </AppShell>
    );
  }
  return (
    <AppShell title="Assignment Package & Limits" subtitle="Understand what is covered, what is capped, and what requires HR approval before proceeding.">
      <HrPolicyContent />
    </AppShell>
  );
};

function HrPolicyContent() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { selectedCaseId } = useSelectedCase();
  const [_assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [policy, setPolicy] = useState<PolicyResponse | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [exceptionCategory, setExceptionCategory] = useState('');
  const [exceptionReason, setExceptionReason] = useState('');
  const [exceptionAmount, setExceptionAmount] = useState('');
  const [exceptionOpen, setExceptionOpen] = useState(false);

  const caseId = searchParams.get('caseId') || selectedCaseId || '';

  const loadAssignments = async () => {
    try {
      const data = await hrAPI.listAssignments();
      setAssignments(data);
      if (!caseId && data.length > 0) {
        const nextId = data[0].id;
        localStorage.setItem('relopass_last_assignment_id', nextId);
        setSearchParams({ caseId: nextId });
      }
      setError('');
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load assignments.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadPolicy = async (id: string) => {
    if (!id) return;
    setIsLoading(true);
    try {
      const [assignmentData, policyData] = await Promise.all([
        hrAPI.getAssignment(id),
        hrAPI.getPolicy(id),
      ]);
      setAssignment(assignmentData);
      setPolicy(policyData);
      localStorage.setItem('relopass_last_assignment_id', id);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else if (err.response?.status === 405) {
        setError('Unable to load policy details. The API is outdated (GET /api/hr/assignments/{id} missing). Please deploy the latest backend.');
      } else {
        setError('Unable to load policy details.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
  }, []);

  useEffect(() => {
    if (caseId) loadPolicy(caseId);
  }, [caseId]);

  const profile = assignment?.profile;
  const routeLabel = profile?.movePlan?.origin && profile?.movePlan?.destination
    ? `${profile.movePlan.origin} → ${profile.movePlan.destination}`
    : 'Relocation route';
  const familySize = 1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);
  const exceptionPending = policy?.exceptions?.some?.((exc) => exc.status === 'PENDING') ?? false;

  const coverageItems = useMemo(() => {
    if (!policy) return [];
    return Object.entries(policy.spend).map(([key, item]) => ({
      key,
      ...item,
    }));
  }, [policy]);

  const handleRequestException = async () => {
    if (!caseId || !exceptionCategory) return;
    try {
      await hrAPI.requestPolicyException(caseId, {
        category: exceptionCategory,
        reason: exceptionReason,
        amount: exceptionAmount ? Number(exceptionAmount) : undefined,
      });
      setExceptionOpen(false);
      setExceptionReason('');
      setExceptionAmount('');
      loadPolicy(caseId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to submit exception.');
    }
  };

  return (
    <>
      {error && <Alert variant="error">{error}</Alert>}
      <div className="flex items-center justify-between mb-4">
        <span />
        <Link
          to={buildRoute('hrPolicyManagement')}
          className="text-sm font-medium text-[#0b2b43] hover:underline px-3 py-2 rounded-lg border border-[#0b2b43] bg-white"
        >
          Manage policies →
        </Link>
      </div>
      {isLoading && <div className="text-sm text-[#6b7280]">Loading policy...</div>}

      {!isLoading && !caseId && (
        <Card padding="lg">
          <div className="text-sm text-[#4b5563] mb-4">Select a case from the HR Dashboard to view its policy.</div>
          <Link to={buildRoute('hrPolicyManagement')}>
            <Button>Create or edit policies</Button>
          </Link>
        </Card>
      )}

      {!isLoading && caseId && !policy && !error && (
        <Card padding="lg">
          <div className="text-sm text-[#4b5563]">Policy data is not available for this case.</div>
        </Card>
      )}

      {!isLoading && policy && assignment && (
        <div className="mb-4">
          <CaseIncompleteBanner assignment={assignment} />
        </div>
      )}

      {!isLoading && policy && assignment && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-3">
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                {routeLabel}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Family size: {familySize}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Policy: {policy.policy?.policyVersion ?? '—'}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                HR owner: {assignment.employeeIdentifier || 'HR'}
              </span>
            </div>
            <div className="text-xs text-[#6b7280]">
              Effective: {policy.policy?.effectiveDate ? new Date(policy.policy.effectiveDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
            </div>
          </div>

          {exceptionPending && (
            <Card padding="md" className="bg-[#eef4ff] border border-[#c7d8ff]">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#0b2b43]">Policy Exceptions Pending</div>
                  <div className="text-xs text-[#4b5563]">
                    You have pending exception requests that require HR approval before submission.
                  </div>
                </div>
                <Button variant="outline">View details</Button>
              </div>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold text-[#0b2b43]">Your Coverage Envelope</div>
            <div className="text-xs text-[#6b7280]">Policy exceptions: {policy.exceptions?.length ?? 0}</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {coverageItems.map((item) => {
              const badge = statusBadge(item.status);
              const barPercent = item.cap ? Math.min(100, Math.round((item.used / item.cap) * 100)) : 0;
              return (
                <Card key={item.key} padding="md">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                    <span className={`text-xs px-2 py-1 rounded-full ${badge.classes}`}>{badge.label}</span>
                  </div>
                  <div className="mt-4 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Used</span>
                    <span className="text-[#0b2b43] font-semibold">
                      {formatCurrency(item.used, item.currency)}
                    </span>
                  </div>
                  <div className="mt-2 h-2 w-full bg-[#e2e8f0] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.status === 'OVER_LIMIT' ? 'bg-[#ef4444]' : item.status === 'NEAR_LIMIT' ? 'bg-[#f59e0b]' : 'bg-[#1f8e8b]'}`}
                      style={{ width: `${barPercent}%` }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Cap: {formatCurrency(item.cap, item.currency)}</span>
                    <span>Remaining: {formatCurrency(item.remaining, item.currency)}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <button className="text-[#0b2b43]">View rules</button>
                    {(item.status === 'OVER_LIMIT' || item.status === 'NEAR_LIMIT') && (
                      <button
                        className="text-[#7a2a2a]"
                        onClick={() => {
                          setExceptionCategory(item.key);
                          setExceptionOpen(true);
                        }}
                      >
                        Request exception
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          <Card padding="lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">Detailed Policy Rules</div>
                <div className="text-xs text-[#6b7280]">Policy logic and required evidence by category.</div>
              </div>
              <span className="text-xs text-[#6b7280]">Read-only</span>
            </div>
            <div className="space-y-3">
              {coverageItems.map((item) => (
                <details key={`rule-${item.key}`} className="border border-[#e2e8f0] rounded-lg p-4">
                  <summary className="flex items-center justify-between cursor-pointer">
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{item.title} Rules</div>
                      <div className="text-xs text-[#6b7280]">
                        Cap: {formatCurrency(item.cap, item.currency)} · Approval: {policy.policy?.approvalRules?.['overLimit'] ?? 'Standard'}
                      </div>
                    </div>
                    <span className="text-xs text-[#6b7280]">View</span>
                  </summary>
                  <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs text-[#4b5563]">
                    <div className="space-y-2">
                      <div>Condition: Applies to all cases requiring {item.title.toLowerCase()} support.</div>
                      <div>Cap logic: Spend must remain within policy cap or request an exception.</div>
                      <div>Enforcement: {item.status === 'OVER_LIMIT' ? 'HARD BLOCK' : 'SOFT WARNING'}.</div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
                      <div className="text-xs font-semibold text-[#0b2b43]">Required evidence</div>
                      <ul className="mt-2 space-y-1">
                        {(policy.policy?.requiredEvidence?.[item.key] ?? []).map((evidence) => (
                          <li key={evidence}>• {evidence}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </Card>
        </div>
      )}

      {exceptionOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <Card padding="lg" className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-[#0b2b43]">Request policy exception</div>
              <button
                onClick={() => setExceptionOpen(false)}
                className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
              >
                Close
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Category</div>
                <div className="text-sm text-[#0b2b43] capitalize">{exceptionCategory}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Amount requested</div>
                <input
                  value={exceptionAmount}
                  onChange={(event) => setExceptionAmount(event.target.value)}
                  placeholder="Enter amount"
                  className="w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Reason</div>
                <textarea
                  value={exceptionReason}
                  onChange={(event) => setExceptionReason(event.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" onClick={() => setExceptionOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleRequestException}>Submit request</Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
