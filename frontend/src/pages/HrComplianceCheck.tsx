import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Checkbox } from '../components/antigravity/Checkbox';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, ProgressBar } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type {
  AssignmentDetail,
  ComplianceCaseReport,
  ComplianceCheckItem,
  PolicyResponse,
} from '../types';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { CaseIncompleteBanner } from '../components/CaseIncompleteBanner';

type TabId = 'requirements' | 'verification' | 'risk';
type OwnerFilter = 'ALL' | 'HR' | 'Employee' | 'Partner';

const statusColors = (status: ComplianceCheckItem['status']) => {
  if (status === 'PASS') return 'bg-[#ecfdf5] text-[#047857]';
  if (status === 'WARN') return 'bg-[#fff7ed] text-[#9a3412]';
  return 'bg-[#fef2f2] text-[#7a2a2a]';
};

const severityColors = (severity: ComplianceCheckItem['severity']) => {
  if (severity === 'CRITICAL') return 'bg-[#fee2e2] text-[#7f1d1d]';
  if (severity === 'HIGH') return 'bg-[#ffedd5] text-[#9a3412]';
  if (severity === 'MED') return 'bg-[#e0f2fe] text-[#075985]';
  return 'bg-[#f3f4f6] text-[#4b5563]';
};

const actionLabel = (label: string, employeeName: string) => {
  if (label.toLowerCase().includes('ask')) return `Ask ${employeeName}`;
  return label;
};

const categoryFromCheck = (checkId: string) => {
  if (checkId.startsWith('housing')) return 'housing';
  if (checkId.startsWith('movers')) return 'movers';
  if (checkId.startsWith('schools')) return 'schools';
  if (checkId.startsWith('immigration')) return 'immigration';
  return 'general';
};

// AIQ-1474: per-call error info so one failed request degrades a single section
// rather than blanking the whole page.
type CallErr = { status: number; message: string } | null;
function toCallErr(r: PromiseSettledResult<unknown>): CallErr {
  if (r.status === 'fulfilled') return null;
  const reason = (r.reason ?? {}) as {
    response?: { status?: number; data?: { detail?: unknown } };
    message?: string;
  };
  const detail = reason.response?.data?.detail;
  return {
    status: reason.response?.status ?? 0,
    message: (typeof detail === 'string' && detail) || reason.message || 'Request failed',
  };
}
function friendlyErr(e: { status: number; message: string }): string {
  if (e.status === 404) return 'no record found for this case yet';
  if (e.status >= 500) return 'server error — please retry';
  if (e.status === 0) return 'could not reach the server (network)';
  return e.message;
}

export const HrComplianceCheck: React.FC = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { selectedCaseId } = useSelectedCase();
  const queryClient = useQueryClient();

  // `error` is also written by the compliance mutations, so keep it local and
  // fold the read errors into what we render.
  const [error, setError] = useState('');
  /** Re-run compliance API in flight. */
  const [complianceRunPending, setComplianceRunPending] = useState(false);
  /** Single in-flight compliance mutation: `exception:${checkId}` or `${checkId}|${actionType}`. */
  const [complianceMutationKey, setComplianceMutationKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('requirements');
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>('ALL');
  const [showBlockingOnly, setShowBlockingOnly] = useState(true);

  const caseId = id || searchParams.get('caseId') || selectedCaseId || '';

  const assignmentsQuery = useQuery({
    queryKey: ['hr', 'assignments'],
    queryFn: async () => {
      const res = await hrAPI.listAssignments();
      return res.assignments ?? [];
    },
  });

  const complianceQuery = useQuery({
    queryKey: ['hr', 'case-compliance', caseId],
    queryFn: async () => {
      // AIQ-1474: allSettled (not all) so a single failing call (e.g. a 404 on the
      // compliance report) degrades that section instead of blanking the entire page.
      const [aR, pR, cR] = await Promise.allSettled([
        hrAPI.getAssignment(caseId),
        hrAPI.getPolicy(caseId),
        hrAPI.getCaseCompliance(caseId),
      ]);
      localStorage.setItem('relopass_last_assignment_id', caseId);
      return {
        assignment: aR.status === 'fulfilled' ? aR.value : null,
        policy: pR.status === 'fulfilled' ? pR.value : null,
        report: cR.status === 'fulfilled' ? cR.value : null,
        errors: { assignment: toCallErr(aR), policy: toCallErr(pR), compliance: toCallErr(cR) },
      };
    },
    enabled: !!caseId,
  });

  const assignment: AssignmentDetail | null = complianceQuery.data?.assignment ?? null;
  const policy: PolicyResponse | null = complianceQuery.data?.policy ?? null;
  const report: ComplianceCaseReport | null = complianceQuery.data?.report ?? null;
  const callErrors = complianceQuery.data?.errors;
  // Sections that failed for a non-auth reason — surfaced individually, never as a
  // single opaque "error" that hides the rest of the page.
  const degradedSections = [
    callErrors?.assignment && callErrors.assignment.status !== 401
      ? { label: 'Case details', ...callErrors.assignment } : null,
    callErrors?.policy && callErrors.policy.status !== 401
      ? { label: 'Policy caps', ...callErrors.policy } : null,
    callErrors?.compliance && callErrors.compliance.status !== 401
      ? { label: 'Compliance checklist', ...callErrors.compliance } : null,
  ].filter((s): s is { label: string; status: number; message: string } => s !== null);

  // Original kept isLoading=true until a compliance load resolved; with no case
  // selected it never flips false.
  const isLoading = caseId ? complianceQuery.isLoading : true;

  const assignments401 =
    (assignmentsQuery.error as { response?: { status?: number } } | null)?.response?.status === 401;
  // AIQ-1474: the combined query now resolves (allSettled), so a 401 is detected from the
  // per-call errors rather than the query erroring. Read failures render per-section
  // (degradedSections) — displayedError is reserved for mutation errors.
  const compliance401 = [callErrors?.assignment, callErrors?.policy, callErrors?.compliance].some(
    (e) => e?.status === 401,
  );
  const displayedError = error;

  // Auto-select the first assignment when no case is in scope (mirrors the old
  // loadAssignments side effect).
  useEffect(() => {
    const data = assignmentsQuery.data;
    if (!data) return;
    if (!caseId && data.length > 0) {
      const first = data[0];
      if (first) {
        const nextId = first.id;
        localStorage.setItem('relopass_last_assignment_id', nextId);
        setSearchParams({ caseId: nextId });
      }
    }
  }, [assignmentsQuery.data, caseId, setSearchParams]);

  // Preserve the 401 → landing redirect from both reads.
  useEffect(() => {
    if ((assignmentsQuery.isError && assignments401) || compliance401) {
      safeNavigate(navigate, 'landing');
    }
  }, [assignmentsQuery.isError, assignments401, compliance401, navigate]);

  const complianceMutationsBusy = complianceRunPending || complianceMutationKey !== null;

  const handleRunCompliance = async () => {
    if (!caseId || complianceMutationsBusy) return;
    setError('');
    setComplianceRunPending(true);
    try {
      const complianceData = await hrAPI.runCaseCompliance(caseId);
      queryClient.setQueryData(
        ['hr', 'case-compliance', caseId],
        (old: { assignment: AssignmentDetail; policy: PolicyResponse; report: ComplianceCaseReport } | undefined) =>
          old ? { ...old, report: complianceData } : old,
      );
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Unable to run compliance.');
    } finally {
      setComplianceRunPending(false);
    }
  };

  const handleAction = async (checkId: string, actionType: string, notes?: string) => {
    if (!caseId || complianceMutationsBusy) return;
    const key = `${checkId}|${actionType}`;
    setComplianceMutationKey(key);
    setError('');
    try {
      await hrAPI.recordComplianceAction(caseId, { checkId, actionType, notes });
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(
        typeof e.response?.data?.detail === 'string'
          ? e.response.data.detail
          : 'Unable to record action.'
      );
    } finally {
      setComplianceMutationKey(null);
    }
  };

  const handleRequestException = async (checkId: string) => {
    if (!caseId || complianceMutationsBusy) return;
    const key = `exception:${checkId}`;
    setComplianceMutationKey(key);
    setError('');
    try {
      const category = categoryFromCheck(checkId);
      await hrAPI.requestPolicyException(caseId, {
        category,
        reason: 'Auto-requested from Compliance Check.',
      });
      await queryClient.invalidateQueries({ queryKey: ['hr', 'case-compliance', caseId] });
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(
        typeof e.response?.data?.detail === 'string'
          ? e.response.data.detail
          : 'Unable to request exception.'
      );
    } finally {
      setComplianceMutationKey(null);
    }
  };

  const exportSummary = () => {
    if (!report) return;
    const payload = {
      riskScore: report.summary.riskScore,
      criticalCount: report.summary.criticalCount,
      topChecks: report.checks.slice(0, 10),
      policyExceptions: policy?.exceptions || [],
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `compliance-summary-${caseId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const profile = assignment?.profile;
  const employeeName = profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const routeLabel = profile?.movePlan?.origin && profile?.movePlan?.destination
    ? `${profile.movePlan.origin} → ${profile.movePlan.destination}`
    : 'Relocation route';
  const familySize = 1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);
  const targetDate = profile?.movePlan?.targetArrivalDate
    ? new Date(profile.movePlan.targetArrivalDate).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '-';

  const filteredChecks = useMemo(() => {
    if (!report) return [];
    return report.checks.filter((check) => {
      if (activeTab === 'verification' && check.status === 'PASS') return false;
      if (activeTab === 'risk' && !['HIGH', 'CRITICAL'].includes(check.severity)) return false;
      if (showBlockingOnly && !check.blocking) return false;
      if (ownerFilter !== 'ALL' && check.owner !== ownerFilter) return false;
      return true;
    });
  }, [report, showBlockingOnly, ownerFilter, activeTab]);

  const groupedChecks = useMemo(() => {
    return filteredChecks.reduce<Record<string, ComplianceCheckItem[]>>((acc, check) => {
      const group = check.pillar || 'Other';
      if (!acc[group]) acc[group] = [];
      acc[group].push(check);
      return acc;
    }, {});
  }, [filteredChecks]);

  const criticalCount = report?.summary.criticalCount || 0;
  // The risk score is driven by every WARN/FAIL check, not just CRITICAL-
  // severity ones. Surface that broader count alongside the score so the
  // user can reconcile e.g. "score 58 / High risk" with "0 critical issues".
  const flaggedCount = report?.checks.filter((check) => check.status === 'WARN' || check.status === 'FAIL').length || 0;
  const gateBlocked = report?.checks.some((check) => check.blocking) || false;

  return (
    <AppShell title="Compliance" subtitle={`${employeeName}: requirements check`}>
      {displayedError && <Alert variant="error">{displayedError}</Alert>}

      {/* AIQ-1474: per-section status summary — one call failing no longer blanks the
          page; the user sees exactly which parts are degraded and why. */}
      {!isLoading && degradedSections.length > 0 && (
        <Alert variant="warning" className="mb-4">
          <div className="text-sm font-medium">Some compliance data couldn&apos;t be loaded</div>
          <ul className="mt-1 space-y-0.5 text-xs">
            {degradedSections.map((s) => (
              <li key={s.label}>• {s.label}: {friendlyErr(s)}</li>
            ))}
          </ul>
          <Button
            unstyled
            type="button"
            onClick={() => void complianceQuery.refetch()}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Retry
          </Button>
        </Alert>
      )}

      {isLoading && <div className="text-sm text-[#6b7280]">Loading compliance checks...</div>}

      {!isLoading && !caseId && (
        <Card padding="lg">
          <div className="text-sm text-[#4b5563]">Select a case from the HR Dashboard to view compliance checks.</div>
        </Card>
      )}

      {/* AIQ-1474: the compliance checklist failed to load, but the page shell + the
          summary above still render — never a blank screen. */}
      {!isLoading && caseId && !report && (
        <Card padding="lg">
          <div className="text-sm font-medium text-[#0b2b43]">Compliance checklist unavailable</div>
          <div className="mt-1 text-xs text-[#6b7280]">
            {callErrors?.compliance
              ? `We couldn't load the requirements checklist for this employee (${friendlyErr(callErrors.compliance)}).`
              : "We couldn't load the requirements checklist for this employee."}{' '}
            Any sections that did load are shown above.
          </div>
        </Card>
      )}

      {!isLoading && report && assignment && (
        <div className="mb-4">
          <CaseIncompleteBanner assignment={assignment} />
        </div>
      )}

      {!isLoading && report && assignment && (
        <div className="space-y-6">
          <div className="bg-[#0b1d33] text-white rounded-xl px-6 py-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide text-[#bfdbfe]">
              <span>Current case</span>
              <span className="text-white text-sm font-semibold normal-case">
                {routeLabel}
              </span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">👥 {familySize} Family Members</span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">📅 Target: {targetDate}</span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">🚩 Stage: {report.meta.stage}</span>
            </div>
          </div>

          {gateBlocked && (
            <Card padding="md" className="bg-[#fff5f5] border border-[#fecaca]">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#7a2a2a]">Submission Center not available</div>
                  <div className="text-xs text-[#6b7280]">
                    Resolve blocking items before submission.
                  </div>
                </div>
                <Badge variant="warning">{criticalCount} critical issues</Badge>
              </div>
            </Card>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="text-sm text-[#6b7280]">
              Compliance checks aligned to HR Policy and case data.
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={exportSummary} disabled={complianceMutationsBusy}>
                Export Summary
              </Button>
              <Button onClick={() => void handleRunCompliance()} disabled={complianceMutationsBusy}>
                {complianceRunPending ? 'Running checks…' : 'Re-run Checks'}
              </Button>
            </div>
          </div>

          <Card padding="lg">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-center">
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280]">Immigration path</div>
                <div className="text-sm font-semibold text-[#0b2b43] mt-1">{report.meta.visaPath}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280]">Destination</div>
                <div className="text-sm font-semibold text-[#0b2b43] mt-1">{report.meta.destination}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280]">Current stage</div>
                <div className="text-sm font-semibold text-[#0b2b43] mt-1">{report.meta.stage}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280]">Last verified</div>
                <div className="text-sm font-semibold text-[#0b2b43] mt-1">
                  {new Date(report.summary.lastVerified).toLocaleString('en-US')}
                </div>
              </div>
              <div className="flex items-center justify-between gap-4 border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
                <div>
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Risk score</div>
                  <div className="text-2xl font-semibold text-[#0b2b43]">{report.summary.riskScore}</div>
                  <div className="text-xs text-[#6b7280]">{report.summary.label} risk</div>
                  <div className="text-sm font-semibold text-[#b45309]">{flaggedCount} issues flagged</div>
                  <div className="text-xs text-[#6b7280]">{criticalCount} critical-severity</div>
                </div>
                <div className="w-16">
                  <ProgressBar value={report.summary.riskScore} showLabel={false} />
                </div>
              </div>
            </div>
          </Card>

          <div className="border-b border-[#e2e8f0]">
            <div className="flex gap-6 text-sm text-[#6b7280]">
              {(['requirements', 'verification', 'risk'] as TabId[]).map((tab) => (
                <Button unstyled
                  key={tab}
                  className={`pb-3 ${activeTab === tab ? 'text-[#0b2b43] font-semibold border-b-2 border-[#0b2b43]' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab === 'requirements' ? 'Requirements' : tab === 'verification' ? 'Verification Checks' : 'Risk & Guidance'}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm text-[#6b7280]">
            <label className="flex items-center gap-2">
              <Checkbox
                checked={showBlockingOnly}
                onChange={(event) => setShowBlockingOnly(event.target.checked)}
              />
              Blocking only
            </label>
            <div className="flex items-center gap-2">
              <span>Owner</span>
              <select
                value={ownerFilter}
                onChange={(event) => setOwnerFilter(event.target.value as OwnerFilter)}
                className="rounded-lg border border-[#e2e8f0] px-2 py-1 text-sm"
              >
                <option value="ALL">All</option>
                <option value="HR">HR</option>
                <option value="Employee">Employee</option>
                <option value="Partner">Partner</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[2.2fr,1fr] gap-6">
            <div className="space-y-4">
              {Object.entries(groupedChecks).map(([pillar, checks]) => (
                <Card key={pillar} padding="lg">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{pillar}</div>
                      <div className="text-xs text-[#6b7280]">Confidence: High</div>
                    </div>
                    <Badge variant="neutral">{checks.length} items</Badge>
                  </div>
                  <div className="space-y-3">
                    {checks.map((check) => (
                      <div key={check.checkId} className="border border-[#e2e8f0] rounded-lg p-4 bg-white">
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold text-[#0b2b43]">{check.title}</span>
                              <span className={`text-xs px-2 py-1 rounded-full ${statusColors(check.status)}`}>
                                {check.status}
                              </span>
                              <span className={`text-xs px-2 py-1 rounded-full ${severityColors(check.severity)}`}>
                                {check.severity}
                              </span>
                              <span className="text-xs px-2 py-1 rounded-full bg-[#eef4f8] text-[#0b2b43]">
                                {check.owner}
                              </span>
                            </div>
                            <div className="text-xs text-[#6b7280]">{check.whyItMatters}</div>
                            {check.evidenceNeeded.length > 0 && (
                              <div className="text-xs text-[#4b5563]">
                                Evidence: {check.evidenceNeeded.join(', ')}
                              </div>
                            )}
                            <div className="text-xs text-[#6b7280]">Confidence: {check.confidence}</div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            {check.fixActions.map((action) => {
                              const isReq = action.toLowerCase().includes('request');
                              const actionType = action.toUpperCase().replace(' ', '_');
                              const pendKey = isReq ? `exception:${check.checkId}` : `${check.checkId}|${actionType}`;
                              const showPending = complianceMutationKey === pendKey;
                              return (
                                <Button
                                  key={action}
                                  variant={isReq ? 'outline' : 'primary'}
                                  disabled={complianceMutationsBusy}
                                  onClick={() => {
                                    if (isReq) {
                                      void handleRequestException(check.checkId);
                                      return;
                                    }
                                    void handleAction(check.checkId, actionType);
                                  }}
                                >
                                  {showPending ? (isReq ? 'Requesting…' : 'Applying…') : actionLabel(action, employeeName.split(' ')[0] ?? '')}
                                </Button>
                              );
                            })}
                            {check.fixActions.length === 0 && (
                              <Button
                                variant="outline"
                                disabled={complianceMutationsBusy}
                                onClick={() => void handleAction(check.checkId, 'MARK_REVIEWED')}
                              >
                                {complianceMutationKey === `${check.checkId}|MARK_REVIEWED` ? 'Saving…' : 'Mark Reviewed'}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>

            <div className="space-y-4">
              <Card padding="lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">Consistency Check</div>
                  <Badge variant="warning">{report.consistencyConflicts.length} conflict</Badge>
                </div>
                {report.consistencyConflicts.length === 0 && (
                  <div className="text-sm text-[#6b7280]">No cross-field data conflicts detected.</div>
                )}
                {report.consistencyConflicts.map((conflict) => (
                  <div key={conflict.id} className="border border-[#fde2e2] rounded-lg p-3 text-sm text-[#7a2a2a] mb-2">
                    <div className="font-semibold">{conflict.title}</div>
                    <div className="text-xs text-[#6b7280] mt-1">
                      Offer letter: {conflict.details.offerLetter} · Questionnaire: {conflict.details.questionnaire}
                    </div>
                    <div className="mt-2">
                      <Button variant="outline" onClick={() => handleAction(conflict.id, 'APPLY_FIX')}>
                        Apply to all
                      </Button>
                    </div>
                  </div>
                ))}
              </Card>

              <Card padding="lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">Recent Checks</div>
                  <span className="text-xs text-[#6b7280]">Last 5</span>
                </div>
                <div className="space-y-2">
                  {report.recentChecks.map((check) => (
                    <div key={check.checkId} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-sm text-[#0b2b43]">{check.title}</div>
                      <Badge variant={check.status === 'PASS' ? 'success' : check.status === 'WARN' ? 'warning' : 'error'}>
                        {check.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </Card>

              <Card padding="lg" className="bg-[#0b1d33] text-white">
                <div className="text-sm font-semibold">Need Expert Help?</div>
                <div className="text-xs text-[#bfdbfe] mt-1">
                  This case has high-risk indicators. Request a manual review by legal.
                </div>
                <div className="mt-3">
                  <Button
                    variant="outline"
                    disabled={complianceMutationsBusy}
                    onClick={() => void handleAction('human_review', 'REQUEST_HUMAN_REVIEW')}
                  >
                    {complianceMutationKey === 'human_review|REQUEST_HUMAN_REVIEW' ? 'Submitting…' : 'Request Human Review'}
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};
