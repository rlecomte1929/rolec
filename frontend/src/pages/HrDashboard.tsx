import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input, Alert, Badge } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { AssignmentSummary, AssignmentDetail } from '../types';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { getCaseMissingFields } from '../components/CaseIncompleteBanner';

export const HrDashboard: React.FC = () => {
  const { setSelectedCaseId } = useSelectedCase();
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [caseId, setCaseId] = useState<string | null>(null);
  const [employeeIdentifier, setEmployeeIdentifier] = useState('');
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [assignmentDetails, setAssignmentDetails] = useState<Record<string, AssignmentDetail>>({});
  const [search, setSearch] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [destinationFilter, setDestinationFilter] = useState('');
  const [departingSoonOnly, setDepartingSoonOnly] = useState(false);
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedForRemoval, setSelectedForRemoval] = useState<Set<string>>(new Set());
  const [isConfirmingRemoval, setIsConfirmingRemoval] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const navigate = useNavigate();

  const loadAssignments = async () => {
    setIsLoading(true);
    try {
      const data = await hrAPI.listAssignments();
      setAssignments(data);
      if (data.length > 0) {
        localStorage.setItem('relopass_last_assignment_id', data[0].id);
      }
      if (data.length > 0) {
        const detailEntries = await Promise.all(
          data.map(async (assignment) => {
            try {
              const detail = await hrAPI.getAssignment(assignment.id);
              return [assignment.id, detail] as const;
            } catch {
              return [assignment.id, null] as const;
            }
          })
        );
        const nextDetails: Record<string, AssignmentDetail> = {};
        detailEntries.forEach(([id, detail]) => {
          if (detail) nextDetails[id] = detail;
        });
        setAssignmentDetails(nextDetails);
      } else {
        setAssignmentDetails({});
      }
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

  useEffect(() => {
    loadAssignments();
  }, []);

  useRegisterNav('HrDashboard', [
    { label: 'Case Summary', routeKey: 'hrCaseSummary' },
    { label: 'Compliance', routeKey: 'hrCompliance' },
    { label: 'Package', routeKey: 'hrPackage' },
  ]);

  const handleCreateCase = async () => {
    setError('');
    setInviteToken(null);
    setAssignmentId(null);
    try {
      const response = await hrAPI.createCase();
      setCaseId(response.caseId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to create case.');
    }
  };

  const handleAssign = async () => {
    if (!caseId || !employeeIdentifier.trim()) {
      setError('Provide an employee username or email.');
      return;
    }
    setError('');
    setInviteToken(null);
    setAssignmentId(null);
    try {
      const response = await hrAPI.assignCase(caseId, employeeIdentifier.trim());
      setAssignmentId(response.assignmentId);
      if (response.inviteToken) {
        setInviteToken(response.inviteToken);
      }
      await loadAssignments();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to assign case.');
    }
  };

  const toggleSelection = (id: string) => {
    setSelectedForRemoval((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRemoveSelected = async () => {
    setIsDeleting(true);
    setError('');
    try {
      for (const id of selectedForRemoval) {
        await hrAPI.deleteAssignment(id);
      }
      setSelectedForRemoval(new Set());
      setIsConfirmingRemoval(false);
      setIsManageMode(false);
      await loadAssignments();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove some cases.');
    } finally {
      setIsDeleting(false);
    }
  };

  const cancelManageMode = () => {
    setIsManageMode(false);
    setSelectedForRemoval(new Set());
    setIsConfirmingRemoval(false);
  };

  const caseStatusBadge = (status: AssignmentSummary['status']) => {
    if (status === 'HR_APPROVED') return <Badge variant="success">Approved</Badge>;
    if (status === 'CHANGES_REQUESTED') return <Badge variant="warning">Changes requested</Badge>;
    if (status === 'EMPLOYEE_SUBMITTED' || status === 'HR_REVIEW') return <Badge variant="info">HR review</Badge>;
    if (status === 'IN_PROGRESS') return <Badge variant="warning">Intake in progress</Badge>;
    return <Badge variant="neutral">Awaiting intake</Badge>;
  };

  const parseDate = (value?: string | null) => (value ? new Date(value) : null);
  const daysUntil = (date?: Date | null) => {
    if (!date) return null;
    const diffMs = date.getTime() - new Date().getTime();
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  };

  const clampPercent = (value?: number | null) => {
    if (value === null || value === undefined) return 0;
    return Math.max(0, Math.min(100, Math.round(value)));
  };

  const formatRoute = (detail?: AssignmentDetail) => {
    const origin = detail?.profile?.movePlan?.origin;
    const destination = detail?.profile?.movePlan?.destination;
    if (origin && destination) return `${origin} \u2192 ${destination}`;
    return '—';
  };

  const formatDeadline = (detail?: AssignmentDetail) => {
    const target = parseDate(detail?.profile?.movePlan?.targetArrivalDate);
    if (!target) return { label: '—', helper: '' };
    const remaining = daysUntil(target);
    return {
      label: target.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      helper: remaining !== null ? `${remaining} days remaining` : '',
    };
  };

  const displayName = (assignment: AssignmentSummary) => {
    const detail = assignmentDetails[assignment.id];
    const name = detail?.profile?.primaryApplicant?.fullName;
    return name || assignment.employeeIdentifier;
  };

  const filteredAssignments = assignments.filter((assignment) => {
    if (!search.trim()) return true;
    const query = search.trim().toLowerCase();
    const detail = assignmentDetails[assignment.id];
    const name = detail?.profile?.primaryApplicant?.fullName || assignment.employeeIdentifier;
    return name.toLowerCase().includes(query);
  }).filter((assignment) => {
    if (statusFilter === 'all') return true;
    return assignment.status === statusFilter;
  }).filter((assignment) => {
    if (!destinationFilter.trim()) return true;
    const detail = assignmentDetails[assignment.id];
    const destination = detail?.profile?.movePlan?.destination || '';
    return destination.toLowerCase().includes(destinationFilter.trim().toLowerCase());
  }).filter((assignment) => {
    if (!departingSoonOnly) return true;
    const detail = assignmentDetails[assignment.id];
    const target = parseDate(detail?.profile?.movePlan?.targetArrivalDate);
    const targetDays = daysUntil(target);
    if (targetDays !== null) return targetDays >= 0 && targetDays <= 30;
    const fallback = parseDate(detail?.submittedAt);
    const fallbackDays = daysUntil(fallback);
    return fallbackDays !== null && fallbackDays >= 0 && fallbackDays <= 14;
  });

  const highlightedAssignment = filteredAssignments[0] || assignments[0] || null;
  const highlightedDetail = highlightedAssignment ? assignmentDetails[highlightedAssignment.id] : null;
  const highlightedCompleteness = clampPercent(highlightedDetail?.completeness ?? 0);
  const highlightedCompliance = highlightedDetail?.complianceReport?.overallStatus || 'Not run';
  const highlightedBlocking =
    highlightedDetail?.complianceReport?.checks?.filter((check) => check.status !== 'COMPLIANT').length || 0;

  const activeStatuses = new Set([
    'DRAFT',
    'IN_PROGRESS',
    'EMPLOYEE_SUBMITTED',
    'HR_REVIEW',
    'CHANGES_REQUESTED',
    'HR_APPROVED',
  ]);

  const totalActive = assignments.filter((assignment) => activeStatuses.has(assignment.status)).length;
  const completed = assignments.filter((assignment) => assignment.status === 'HR_APPROVED').length;
  const actionRequired = assignments.filter((assignment) => {
    const requiresStatus = ['CHANGES_REQUESTED', 'HR_REVIEW', 'EMPLOYEE_SUBMITTED'].includes(assignment.status);
    const detail = assignmentDetails[assignment.id];
    const blockingCount = detail?.complianceReport?.checks?.filter((check) => check.status !== 'COMPLIANT').length || 0;
    return requiresStatus || blockingCount > 0;
  }).length;
  const departingSoon = assignments.filter((assignment) => {
    const detail = assignmentDetails[assignment.id];
    const target = parseDate(detail?.profile?.movePlan?.targetArrivalDate);
    const targetDays = daysUntil(target);
    if (targetDays !== null) return targetDays >= 0 && targetDays <= 30;
    const fallback = parseDate(detail?.submittedAt);
    const fallbackDays = daysUntil(fallback);
    return fallbackDays !== null && fallbackDays >= 0 && fallbackDays <= 14;
  }).length;

  return (
    <AppShell title="HR Dashboard" subtitle="Monitor relocations, readiness, and approvals.">
      <div className="space-y-6">
        {error && <Alert variant="error">{error}</Alert>}

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <input
                id="hr-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search employees..."
                className="w-64 rounded-full border border-[#e2e8f0] bg-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setIsFilterOpen(true)}>
              Filter
            </Button>
            <Button onClick={handleCreateCase}>New Case</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Total active cases</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{totalActive}</div>
            <div className="text-xs text-[#6b7280] mt-1">Currently in progress</div>
          </Card>
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Action required</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{actionRequired}</div>
            <div className="text-xs text-[#6b7280] mt-1">Needs HR attention</div>
          </Card>
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Departing soon</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{departingSoon}</div>
            <div className="text-xs text-[#6b7280] mt-1">Next 30 days</div>
          </Card>
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Completed (YTD)</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{completed}</div>
            <div className="text-xs text-[#6b7280] mt-1">Approved cases</div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Profile completeness</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{highlightedCompleteness}%</div>
            <div className="text-xs text-[#6b7280] mt-1">Highlighted case</div>
          </Card>
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Compliance status</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{highlightedCompliance}</div>
            <div className="text-xs text-[#6b7280] mt-1">Latest checks</div>
          </Card>
          <Card padding="md">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Blocking items</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{highlightedBlocking}</div>
            <div className="text-xs text-[#6b7280] mt-1">Needs HR attention</div>
          </Card>
        </div>

        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-[#0b2b43]">Active relocation cases</div>
            <div className="flex items-center gap-2">
              {!isManageMode ? (
                <>
                  <Button variant="outline" onClick={loadAssignments}>Refresh</Button>
                  <Button variant="outline" onClick={() => setIsManageMode(true)}>Manage Cases</Button>
                </>
              ) : (
                <>
                  <span className="text-xs text-[#6b7280]">
                    {selectedForRemoval.size} selected
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => {
                      if (selectedForRemoval.size === 0) {
                        setError('Select at least one case to remove.');
                        return;
                      }
                      setIsConfirmingRemoval(true);
                    }}
                    disabled={selectedForRemoval.size === 0}
                  >
                    Remove selected
                  </Button>
                  <Button variant="outline" onClick={cancelManageMode}>Cancel</Button>
                </>
              )}
            </div>
          </div>

          {isConfirmingRemoval && (
            <div className="mb-4 border border-red-200 bg-red-50 rounded-xl p-4">
              <div className="text-sm font-semibold text-red-800 mb-2">
                Confirm removal of {selectedForRemoval.size} case{selectedForRemoval.size > 1 ? 's' : ''}
              </div>
              <div className="text-xs text-red-700 mb-3">
                This will permanently delete the selected case{selectedForRemoval.size > 1 ? 's' : ''} and all associated data.
                This action cannot be undone.
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRemoveSelected}
                  disabled={isDeleting}
                  className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {isDeleting ? 'Removing...' : 'Confirm removal'}
                </button>
                <Button variant="outline" onClick={() => setIsConfirmingRemoval(false)} disabled={isDeleting}>
                  Go back
                </Button>
              </div>
            </div>
          )}

          {isLoading && <div className="text-sm text-[#6b7280]">Loading assignments...</div>}
          {!isLoading && filteredAssignments.length === 0 && (
            <div className="text-sm text-[#4b5563]">No assignments yet.</div>
          )}

          {!isLoading && filteredAssignments.length > 0 && (
            <div className="border border-[#e2e8f0] rounded-xl overflow-hidden">
              <div className={`grid gap-4 bg-[#f8fafc] px-4 py-3 text-[11px] uppercase tracking-wide text-[#6b7280] ${isManageMode ? 'grid-cols-[2rem,1.6fr,1.6fr,1fr,1fr,0.3fr]' : 'grid-cols-[1.6fr,1.6fr,1fr,1fr,0.3fr]'}`}>
                {isManageMode && <div></div>}
                <div>Employee name</div>
                <div>Route (origin → dest)</div>
                <div>Status</div>
                <div>Next deadline</div>
                <div className="text-right">View</div>
              </div>
              {filteredAssignments.map((assignment) => {
                const detail = assignmentDetails[assignment.id];
                const deadline = formatDeadline(detail);
                const isSelected = selectedForRemoval.has(assignment.id);
                return (
                  <div
                    key={assignment.id}
                    onClick={() => {
                      if (isManageMode) {
                        toggleSelection(assignment.id);
                        return;
                      }
                      setSelectedCaseId(assignment.id);
                      navigate(buildRoute('hrCaseSummary', { caseId: assignment.id }));
                    }}
                    className={`grid gap-4 px-4 py-4 border-t border-[#e2e8f0] items-center cursor-pointer ${
                      isManageMode
                        ? `grid-cols-[2rem,1.6fr,1.6fr,1fr,1fr,0.3fr] ${isSelected ? 'bg-red-50' : 'hover:bg-[#f8fafc]'}`
                        : 'grid-cols-[1.6fr,1.6fr,1fr,1fr,0.3fr] hover:bg-[#f8fafc]'
                    }`}
                  >
                    {isManageMode && (
                      <div className="flex items-center justify-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelection(assignment.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded border-[#d1d5db] text-red-600 focus:ring-red-500"
                        />
                      </div>
                    )}
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{displayName(assignment)}</div>
                      <div className="text-xs text-[#6b7280]">{assignment.employeeIdentifier}</div>
                      <div className="text-xs text-[#94a3b8]">Assignment ID: {assignment.id}</div>
                    </div>
                    <div>
                      <div className="text-sm text-[#0b2b43]">{formatRoute(detail)}</div>
                      <div className="text-xs text-[#6b7280]">
                        {detail?.profile?.movePlan?.housing?.budgetMonthlySGD || 'Relocation pathway'}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {caseStatusBadge(assignment.status)}
                      {getCaseMissingFields(detail ?? null).length > 0 && (
                        <Badge variant="warning">Incomplete</Badge>
                      )}
                    </div>
                    <div>
                      <div className="text-sm text-[#0b2b43]">{deadline.label}</div>
                      <div className="text-xs text-[#6b7280]">{deadline.helper}</div>
                    </div>
                    <div className="text-right text-[#94a3b8] text-lg">
                      {isManageMode ? '' : '→'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {caseId && (
          <Card padding="lg">
            <div className="space-y-3">
              <div className="text-sm text-[#4b5563]">Case created: {caseId}</div>
              <Input
                value={employeeIdentifier}
                onChange={setEmployeeIdentifier}
                label="Employee username or email"
                placeholder="jane_doe or jane@company.com"
                fullWidth
              />
              <Button onClick={handleAssign}>Assign</Button>
              {assignmentId && (
                <Alert variant="info" title="Assignment created">
                  Assignment ID: <strong>{assignmentId}</strong>
                </Alert>
              )}
              {inviteToken && (
                <Alert variant="info" title="Invite created">
                  Share this invite token with the employee: <strong>{inviteToken}</strong>
                </Alert>
              )}
            </div>
          </Card>
        )}
      </div>

      {isFilterOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <Card padding="lg" className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-[#0b2b43]">Filter cases</div>
              <button
                onClick={() => setIsFilterOpen(false)}
                className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
              >
                Close
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Status</div>
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                >
                  <option value="all">All statuses</option>
                  <option value="DRAFT">Draft</option>
                  <option value="IN_PROGRESS">In progress</option>
                  <option value="EMPLOYEE_SUBMITTED">Employee submitted</option>
                  <option value="HR_REVIEW">HR review</option>
                  <option value="CHANGES_REQUESTED">Changes requested</option>
                  <option value="HR_APPROVED">Approved</option>
                </select>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Destination</div>
                <input
                  value={destinationFilter}
                  onChange={(event) => setDestinationFilter(event.target.value)}
                  placeholder="Singapore, New York, etc."
                  className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-[#4b5563]">
                <input
                  type="checkbox"
                  checked={departingSoonOnly}
                  onChange={(event) => setDepartingSoonOnly(event.target.checked)}
                />
                Departing soon only
              </label>
              <div className="flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setStatusFilter('all');
                    setDestinationFilter('');
                    setDepartingSoonOnly(false);
                  }}
                >
                  Reset
                </Button>
                <Button onClick={() => setIsFilterOpen(false)}>Apply filters</Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
};
