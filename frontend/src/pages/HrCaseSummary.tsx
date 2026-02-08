import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { AssignmentDetail, AssignmentStatus } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';

const statusBadge = (status?: AssignmentStatus) => {
  if (!status) return <Badge variant="neutral">Unknown</Badge>;
  if (status === 'HR_APPROVED') return <Badge variant="success">Approved</Badge>;
  if (status === 'CHANGES_REQUESTED') return <Badge variant="warning">Changes requested</Badge>;
  if (status === 'EMPLOYEE_SUBMITTED' || status === 'HR_REVIEW') return <Badge variant="info">HR review</Badge>;
  if (status === 'IN_PROGRESS') return <Badge variant="warning">Intake in progress</Badge>;
  return <Badge variant="neutral">Draft</Badge>;
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
        setError('Unable to load case summary.');
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
      await hrAPI.decide(assignment.id, 'HR_APPROVED', { notes: decisionNotes || undefined });
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
      await hrAPI.decide(assignment.id, 'CHANGES_REQUESTED', {
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

  const headerName =
    assignment?.profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const origin = assignment?.profile?.movePlan?.origin;
  const destination = assignment?.profile?.movePlan?.destination;

  const blockingItems = assignment?.complianceReport?.checks?.filter((check) => check.status !== 'COMPLIANT') || [];
  const complianceStatus = assignment?.complianceReport?.overallStatus || 'NEEDS_REVIEW';

  const nextDeadline = useMemo(() => {
    const target = assignment?.profile?.movePlan?.targetArrivalDate;
    if (target) return new Date(target);
    if (assignment?.submittedAt) return new Date(assignment.submittedAt);
    return null;
  }, [assignment]);

  return (
    <AppShell title="Case Summary" subtitle="Overview of the relocation case for review.">
      {error && <Alert variant="error">{error}</Alert>}
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
                <Button
                  variant="outline"
                  onClick={() => setIsDecisionOpen((prev) => !prev)}
                >
                  {isDecisionOpen ? 'Close decision' : 'Approve / Request changes'}
                </Button>
              </div>
            </div>
          </Card>

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
            <div className="text-sm font-semibold text-[#0b2b43]">Blocking items</div>
            {blockingItems.length === 0 && (
              <div className="text-sm text-[#6b7280] mt-2">No blocking items.</div>
            )}
            {blockingItems.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-[#4b5563]">
                {blockingItems.map((item) => (
                  <li key={item.id} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg px-3 py-2">
                    <span>{item.name}</span>
                    <Badge variant="warning">{item.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>

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
