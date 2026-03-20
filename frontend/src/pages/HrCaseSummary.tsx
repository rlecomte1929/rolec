import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card } from '../components/antigravity';
import { hrAPI } from '../api/client';
import { hrReopenAssignment } from '../api/rpc';
import type { AssignmentDetail, AssignmentStatus } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import { CaseTimeline } from '../features/timeline/CaseTimeline';
import { CaseReadinessCore } from '../features/readiness/CaseReadinessCore';

const statusBadge = (status?: AssignmentStatus) => {
  if (!status) return <Badge variant="neutral">Unknown</Badge>;
  if (status === 'approved') return <Badge variant="success">Approved</Badge>;
  if (status === 'rejected') return <Badge variant="warning">Rejected</Badge>;
  if (status === 'submitted') return <Badge variant="info">HR review</Badge>;
  if (status === 'assigned' || status === 'awaiting_intake') {
    return <Badge variant="warning">Intake in progress</Badge>;
  }
  return <Badge variant="neutral">Created</Badge>;
};

const clampPercent = (value?: number | null) => {
  if (value === null || value === undefined) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
};

export const HrCaseSummary: React.FC = () => {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isDecisionOpen, setIsDecisionOpen] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [requestedSections, setRequestedSections] = useState<string[]>([]);
  const [isDeciding, setIsDeciding] = useState(false);
  const [isReopenOpen, setIsReopenOpen] = useState(false);
  const [reopenNote, setReopenNote] = useState('');
  const [isReopening, setIsReopening] = useState(false);
  const [reopenSuccess, setReopenSuccess] = useState('');

  const SECTION_OPTIONS = [
    'Relocation Basics',
    'Employee Profile',
    'Family Members',
    'Assignment / Context',
  ];

  const loadAssignment = async () => {
    if (!caseId) return;
    setIsLoading(true);
    try {
      const data = await hrAPI.getAssignment(caseId);
      setAssignment(data);
      localStorage.setItem('relopass_last_assignment_id', data.id);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Assignment not found or not visible under RLS.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignment();
  }, [caseId]);

  const handleRunCompliance = async () => {
    if (!assignment?.id) return;
    setError('');
    setIsRunning(true);
    try {
      await hrAPI.runCompliance(assignment.id);
      await loadAssignment();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to run compliance checks.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleApprove = async () => {
    if (!assignment?.id) return;
    setError('');
    setIsDeciding(true);
    try {
      await hrAPI.decide(assignment.id, 'approved', { notes: decisionNotes || undefined });
      setIsDecisionOpen(false);
      setDecisionNotes('');
      setRequestedSections([]);
      await loadAssignment();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to approve case.');
    } finally {
      setIsDeciding(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!assignment?.id) return;
    if (requestedSections.length === 0 && !decisionNotes.trim()) {
      setError('Select at least one section or add a comment for the employee.');
      return;
    }
    setError('');
    setIsDeciding(true);
    try {
      await hrAPI.decide(assignment.id, 'rejected', {
        notes: decisionNotes || undefined,
        requestedSections: requestedSections.length ? requestedSections : undefined,
      });
      setIsDecisionOpen(false);
      setDecisionNotes('');
      setRequestedSections([]);
      await loadAssignment();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to request changes.');
    } finally {
      setIsDeciding(false);
    }
  };

  const handleReopen = async () => {
    if (!assignment?.id) return;
    setError('');
    setReopenSuccess('');
    setIsReopening(true);
    if (import.meta.env.DEV) {
      console.debug('RPC transition_assignment: HR_REOPEN', {
        assignmentId: assignment.id,
        note: reopenNote || null,
      });
    }
    const { error: rpcError } = await hrReopenAssignment(assignment.id, reopenNote || undefined);
    if (rpcError) {
      setError(rpcError);
      setIsReopening(false);
      return;
    }
    setIsReopening(false);
    setIsReopenOpen(false);
    setReopenNote('');
    setReopenSuccess('Reopened for employee edits.');
    await loadAssignment();
  };

  const headerName =
    assignment?.profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const origin = assignment?.profile?.movePlan?.origin;
  const destination = assignment?.profile?.movePlan?.destination;

  const blockingItems = assignment?.complianceReport?.checks?.filter((check) => check.status !== 'COMPLIANT') || [];
  const complianceStatus = assignment?.complianceReport?.overallStatus || 'NEEDS_REVIEW';
  const canReopen = assignment?.status === 'submitted';

  const nextDeadline = useMemo(() => {
    const target = assignment?.profile?.movePlan?.targetArrivalDate;
    if (target) return new Date(target);
    if (assignment?.submittedAt) return new Date(assignment.submittedAt);
    return null;
  }, [assignment]);

  return (
    <AppShell title="Case Summary" subtitle="Overview of the relocation case for review.">
      {error && (
        <Alert variant="error">
          {error}
          {import.meta.env.DEV && caseId && (
            <div className="mt-2 text-xs font-mono text-[#6b7280]">assignmentId/caseId: {caseId}</div>
          )}
        </Alert>
      )}
      {reopenSuccess && <Alert variant="success">{reopenSuccess}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading case summary...</div>}

      {!isLoading && assignment && (
        <div className="space-y-6">
          <Card padding="lg">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-xl font-semibold text-[#0b2b43]">{headerName}</div>
                <div className="text-sm text-[#6b7280]">
                  {origin && destination ? `${origin} → ${destination}` : 'Route not set'}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {statusBadge(assignment.status)}
                <Button onClick={handleRunCompliance} disabled={isRunning}>
                  {isRunning ? 'Running...' : 'Run compliance checks'}
                </Button>
                {canReopen && (
                  <Button variant="outline" onClick={() => setIsReopenOpen((prev) => !prev)}>
                    {isReopenOpen ? 'Close reopen' : 'Reopen for employee'}
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={() => setIsDecisionOpen((prev) => !prev)}
                >
                  {isDecisionOpen ? 'Close decision' : 'Approve / Request changes'}
                </Button>
                {caseId && (
                  <Link to={`/cases/${caseId}/resources`}>
                    <Button variant="outline">View resources</Button>
                  </Link>
                )}
              </div>
            </div>
          </Card>

          {assignment?.id && <CaseReadinessCore assignmentId={assignment.id} />}

          {canReopen && isReopenOpen && (
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43]">Reopen for employee</div>
              <div className="text-xs text-[#6b7280] mt-1">
                This will move the case back to Draft and allow the employee to edit their responses.
              </div>
              <div className="mt-4">
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Note (optional)</div>
                <textarea
                  value={reopenNote}
                  onChange={(event) => setReopenNote(event.target.value)}
                  className="w-full min-h-[84px] rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                  placeholder="Optional note for the employee."
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={handleReopen} disabled={isReopening}>
                  {isReopening ? 'Reopening...' : 'Reopen for employee'}
                </Button>
                <Button variant="outline" onClick={() => setIsReopenOpen(false)}>
                  Cancel
                </Button>
              </div>
            </Card>
          )}

          {isDecisionOpen && (
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43]">Decision</div>
              <div className="text-xs text-[#6b7280] mt-1">
                If you request changes, the employee will be routed back into the wizard with the sections you flagged.
              </div>

              <div className="mt-4">
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Sections to update</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {SECTION_OPTIONS.map((label) => {
                    const checked = requestedSections.includes(label);
                    return (
                      <label key={label} className="flex items-center gap-2 text-sm text-[#0b2b43]">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(event) => {
                            setRequestedSections((prev) => {
                              if (event.target.checked) return Array.from(new Set([...prev, label]));
                              return prev.filter((s) => s !== label);
                            });
                          }}
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="mt-4">
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Comment (optional)</div>
                <textarea
                  value={decisionNotes}
                  onChange={(event) => setDecisionNotes(event.target.value)}
                  className="w-full min-h-[84px] rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                  placeholder="Explain what to fix and why (visible to employee)."
                />
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={handleApprove} disabled={isDeciding}>
                  {isDeciding ? 'Saving...' : 'Approve'}
                </Button>
                <Button variant="outline" onClick={handleRequestChanges} disabled={isDeciding}>
                  {isDeciding ? 'Saving...' : 'Request changes'}
                </Button>
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card padding="md">
              <div className="text-xs uppercase tracking-wide text-[#6b7280]">Profile completeness</div>
              <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
                {clampPercent(assignment.completeness)}%
              </div>
              <div className="text-xs text-[#6b7280] mt-1">Completion status</div>
            </Card>
            <Card padding="md">
              <div className="text-xs uppercase tracking-wide text-[#6b7280]">Compliance status</div>
              <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{complianceStatus}</div>
              <div className="text-xs text-[#6b7280] mt-1">Latest checks</div>
            </Card>
            <Card padding="md">
              <div className="text-xs uppercase tracking-wide text-[#6b7280]">Next deadline</div>
              <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
                {nextDeadline ? nextDeadline.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}
              </div>
              <div className="text-xs text-[#6b7280] mt-1">Upcoming milestone</div>
            </Card>
          </div>

          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43]">Compliance screening (internal rules)</div>
            <p className="text-xs text-[#64748b] mt-1">
              Assignment-level checks use ReloPass internal policy configuration — not immigration law. Outcomes are
              preliminary; human review is required for any immigration decision.
            </p>
            {assignment.complianceReport?.disclaimer_legal && (
              <p className="text-xs text-[#475569] mt-3 border border-[#e2e8f0] rounded-lg px-3 py-2 bg-[#f8fafc]">
                {assignment.complianceReport.disclaimer_legal}
              </p>
            )}
            {assignment.complianceReport?.verdict_explanation && (
              <p className="text-sm text-[#334155] mt-3">{assignment.complianceReport.verdict_explanation}</p>
            )}
            {assignment.complianceReport?.explanation?.steps &&
              assignment.complianceReport.explanation.steps.length > 0 && (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer text-[#1d4ed8] font-medium">
                    Step-by-step run log
                  </summary>
                  <ol className="mt-2 space-y-2 pl-4 list-decimal text-[#475569]">
                    {assignment.complianceReport.explanation.steps.map((s) => (
                      <li key={s.step}>
                        <span className="font-medium text-[#0f172a]">{s.title}</span>
                        <pre className="mt-1 text-xs bg-[#f1f5f9] rounded p-2 overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(s.detail, null, 2)}
                        </pre>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
            <div className="text-sm font-semibold text-[#0b2b43] mt-6">Blocking or review items</div>
            {blockingItems.length === 0 && (
              <div className="text-sm text-[#6b7280] mt-2">No blocking items under internal rules.</div>
            )}
            {blockingItems.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-[#4b5563]">
                {blockingItems.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-col gap-1 border border-[#e2e8f0] rounded-lg px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-[#0f172a]">{item.name}</span>
                      <Badge variant="warning">{item.status}</Badge>
                    </div>
                    {item.rationale && <p className="text-xs text-[#64748b]">{item.rationale}</p>}
                    {item.rationale_legal_safety && (
                      <p className="text-xs italic text-[#64748b]">{item.rationale_legal_safety}</p>
                    )}
                    {item.human_review_required && (
                      <Badge variant="warning" size="sm">
                        Human review
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {assignment.complianceReport?.actions && assignment.complianceReport.actions.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-semibold text-[#0b2b43] uppercase tracking-wide">Suggested actions</div>
                <ul className="mt-2 list-disc list-inside text-sm text-[#475569] space-y-1">
                  {assignment.complianceReport.actions.map((a, i) => (
                    <li key={i}>{typeof a === 'string' ? a : a.title}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <CaseTimeline assignmentId={assignment.id} ensureDefaults />

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => safeNavigate(navigate, 'hrAssignmentReview', { id: assignment.id })}>
              Review submission
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                navigate(`${buildRoute('hrComplianceIndex')}?caseId=${assignment.id}`)
              }
            >
              Compliance details
            </Button>
            <Button variant="outline" onClick={() => safeNavigate(navigate, 'hrPackage', { id: assignment.id })}>
              Package review
            </Button>
          </div>
        </div>
      )}
    </AppShell>
  );
};
