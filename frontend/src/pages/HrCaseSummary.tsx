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
import { CaseEssentialsCard } from '../features/cases/CaseEssentialsCard';
import { ReadinessAndActionsBlock } from '../features/cases/ReadinessAndActionsBlock';
import { CaseOperationalSection } from '../features/cases/CaseOperationalSection';
import { deriveCaseEssentials } from '../features/cases/caseEssentials';

const statusBadge = (status?: AssignmentStatus) => {
  if (!status) return <Badge variant="neutral">Unknown</Badge>;
  if (status === 'approved') return <Badge variant="success">Complete</Badge>;
  if (status === 'rejected') return <Badge variant="warning">Rejected</Badge>;
  if (status === 'closed') return <Badge variant="neutral">Canceled</Badge>;
  if (status === 'submitted') return <Badge variant="info">Awaiting HR review</Badge>;
  if (status === 'awaiting_intake') return <Badge variant="warning">Intake in progress</Badge>;
  if (status === 'assigned' || status === 'created') return <Badge variant="neutral">Not started</Badge>;
  return <Badge variant="neutral">Not started</Badge>;
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

  const essentials = useMemo(
    () => (assignment ? deriveCaseEssentials(assignment) : null),
    [assignment]
  );
  /** Header line: prefer resolved name; if still unknown, show invite identifier so HR knows which login this is */
  const headerName =
    essentials && essentials.fullName !== 'Not provided'
      ? essentials.fullName
      : assignment?.profile?.primaryApplicant?.fullName ||
        assignment?.employeeIdentifier ||
        'Employee';
  const routeSubtitle =
    essentials &&
    essentials.origin !== 'Not provided' &&
    essentials.destination !== 'Not provided'
      ? `${essentials.origin} → ${essentials.destination}`
      : essentials &&
          (essentials.origin !== 'Not provided' || essentials.destination !== 'Not provided')
        ? `${essentials.origin !== 'Not provided' ? essentials.origin : '…'} → ${essentials.destination !== 'Not provided' ? essentials.destination : '…'}`
        : 'Route not set';

  const canReopen = assignment?.status === 'submitted';

  return (
    <AppShell
      title="Case Summary"
      subtitle="Same view as the employee: essentials, gaps, shared plan."
    >
      {error && (
        <Alert variant="error">
          {error}
          {import.meta.env.DEV && caseId && (
            <div className="mt-2 text-xs font-mono text-[#6b7280]">assignmentId/caseId: {caseId}</div>
          )}
        </Alert>
      )}
      {reopenSuccess && <Alert variant="success">{reopenSuccess}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading…</div>}

      {!isLoading && assignment && (
        <div className="space-y-6">
          <Card padding="lg">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-xl font-semibold text-[#0b2b43]">{headerName}</div>
                <div className="text-sm text-[#6b7280]">{routeSubtitle}</div>
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

          <CaseOperationalSection
            step={1}
            id="op-step-essentials"
            title="Case essentials"
            subtitle="Who is moving, household, and route. Ground truth for the checklist and plan below."
          >
            <CaseEssentialsCard assignment={assignment} embedInOperationalFlow />
          </CaseOperationalSection>

          <CaseOperationalSection
            step={2}
            id="op-step-readiness"
            title="Readiness & actions"
            subtitle="What is missing, what needs review, and suggested moves. Intake gaps link to concrete plan tasks in step 3 (owner + due date). Human-review labels preserve when official verification is not available."
          >
            <ReadinessAndActionsBlock assignment={assignment} embedInOperationalFlow />
          </CaseOperationalSection>

          {assignment?.id && (
            <CaseOperationalSection
              step={3}
              id="op-step-plan"
              title="Shared relocation plan"
              subtitle="Same ordered tasks the employee sees: owner, due dates, status, urgency. Use for follow-up; overdue and blocked highlight risk."
            >
              <CaseTimeline
                assignmentId={assignment.id}
                ensureDefaults
                hideMainTitle
                title="Relocation plan & actions"
              />
            </CaseOperationalSection>
          )}

          {assignment?.id && (
            <>
              <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-xs text-[#64748b] leading-relaxed">
                <span className="font-semibold text-[#0b2b43]">Route and template reference</span>. Checklist rows,
                template milestones, and source tiers for this destination. Use after the steps above. Does not replace
                the shared plan for day-to-day work.
              </div>
              <CaseReadinessCore assignmentId={assignment.id} />
            </>
          )}

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

          {assignment.complianceReport?.explanation?.steps &&
            assignment.complianceReport.explanation.steps.length > 0 && (
              <Card padding="md">
                <details className="text-sm">
                  <summary className="cursor-pointer text-[#1d4ed8] font-medium">
                    Latest compliance run (step log)
                  </summary>
                  <p className="text-xs text-[#64748b] mt-2">
                    Internal policy engine only; not immigration law. Same data as merged block above.
                  </p>
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
              </Card>
            )}

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
