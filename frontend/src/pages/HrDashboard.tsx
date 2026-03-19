import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input, Alert, Badge } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { AssignmentSummary, AssignmentDetail } from '../types';
import { startInteraction, endInteraction } from '../perf/perf';
import { trackAuthPerf } from '../perf/authPerf';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { getCaseMissingFields } from '../components/CaseIncompleteBanner';
import { getAuthItem } from '../utils/demo';

export const HrDashboard: React.FC = () => {
  const { setSelectedCaseId } = useSelectedCase();
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [caseId, setCaseId] = useState<string | null>(null);
  const [employeeIdentifier, setEmployeeIdentifier] = useState('');
  const [employeeFirstName, setEmployeeFirstName] = useState('');
  const [employeeLastName, setEmployeeLastName] = useState('');
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [assignmentDetails, setAssignmentDetails] = useState<Record<string, AssignmentDetail>>({});
  const [detailsLoadedCount, setDetailsLoadedCount] = useState(0);
  const [detailsErrorCount, setDetailsErrorCount] = useState(0);
  const [search, setSearch] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [destinationFilter, setDestinationFilter] = useState('');
  const [departingSoonOnly, setDepartingSoonOnly] = useState(false);
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedForRemoval, setSelectedForRemoval] = useState<Set<string>>(new Set());
  const [isConfirmingRemoval, setIsConfirmingRemoval] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const navigate = useNavigate();

  const loadAssignmentDetails = async (items: AssignmentSummary[], limit: number, signal?: AbortSignal) => {
    if (items.length === 0) {
      setAssignmentDetails({});
      setDetailsLoadedCount(0);
      return;
    }

    const targets = items
      .filter((assignment) => !assignmentDetails[assignment.id])
      .slice(0, limit);
    if (targets.length === 0) return;

    const detailEntries = await Promise.allSettled(
      targets.map(async (assignment) => {
        const detail = await hrAPI.getAssignment(assignment.id, { signal });
        return [assignment.id, detail] as const;
      })
    );

    const nextDetails: Record<string, AssignmentDetail> = {};
    let fulfilled = 0;
    let rejected = 0;
    detailEntries.forEach((entry) => {
      if (entry.status === 'fulfilled') {
        const [id, detail] = entry.value;
        if (detail) {
          nextDetails[id] = detail;
          fulfilled += 1;
        }
      } else {
        rejected += 1;
      }
    });
    setAssignmentDetails((prev) => ({ ...prev, ...nextDetails }));
    setDetailsLoadedCount((prev) => prev + targets.length);
    setDetailsErrorCount((prev) => prev + rejected);
  };

  const loadAssignments = async (signal?: AbortSignal) => {
    setIsLoading(true);
    setDetailsErrorCount(0);
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackAuthPerf({ stage: 'bootstrap_start', route: '/hr/dashboard', meta: { endpoint: 'listAssignments' } });
    try {
      const data = await hrAPI.listAssignments({ signal });
      if (signal?.aborted) return;
      setAssignments(data);
      if (data.length > 0) {
        localStorage.setItem('relopass_last_assignment_id', data[0].id);
      }
      const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
      trackAuthPerf({ stage: 'bootstrap_end', route: '/hr/dashboard', durationMs: dur, meta: { endpoint: 'listAssignments' } });
      setIsLoading(false);
      // Load a small initial batch to avoid request fan-out; user can load more.
      void loadAssignmentDetails(data, 5, signal ?? undefined);
    } catch (err: any) {
      if (err?.name === 'AbortError' || signal?.aborted) return;
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load assignments.');
      }
      const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
      trackAuthPerf({ stage: 'bootstrap_end', route: '/hr/dashboard', durationMs: dur, meta: { endpoint: 'listAssignments', error: true } });
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const ac = new AbortController();
    loadAssignments(ac.signal);
    return () => ac.abort();
  }, []);

  useEffect(() => {
    let mounted = true;
    hrAPI.getCompanyProfile()
      .then((res) => {
        if (mounted && !res.company) {
          safeNavigate(navigate, 'hrCompanyProfile');
        }
      })
      .catch(() => undefined);
    return () => { mounted = false; };
  }, [navigate]);

  useRegisterNav('HrDashboard', [
    { label: 'Case Summary', routeKey: 'hrCaseSummary' },
    { label: 'Compliance', routeKey: 'hrCompliance' },
    { label: 'Package', routeKey: 'hrPackage' },
  ]);

  const handleCreateCase = async () => {
    setError('');
    setInviteToken(null);
    setAssignmentId(null);
    setEmployeeIdentifier('');
    setEmployeeFirstName('');
    setEmployeeLastName('');
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
    const interaction = startInteraction('HR_ASSIGN_CLICK');
    try {
      const response = await hrAPI.assignCase(caseId, employeeIdentifier.trim(), {
        firstName: employeeFirstName || undefined,
        lastName: employeeLastName || undefined,
      });
      setAssignmentId(response.assignmentId);
      if (response.inviteToken) {
        setInviteToken(response.inviteToken);
      }
      await loadAssignments();
    } catch (err: any) {
      const data = err.response?.data;
      const msg = data?.detail || data?.error || 'Unable to assign case.';
      setError(msg);
      // Log full error to console for debugging (see docs/DEBUG_ASSIGN_ERROR.md)
      console.error('[Assign failed]', msg, data || err);
    } finally {
      // Measure click -> UI render (best-effort).
      void endInteraction(interaction);
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
    if (status === 'approved') return <Badge variant="success">Approved</Badge>;
    if (status === 'rejected') return <Badge variant="warning">Rejected</Badge>;
    if (status === 'submitted') return <Badge variant="info">HR review</Badge>;
    if (status === 'assigned' || status === 'awaiting_intake') {
      return <Badge variant="warning">Intake in progress</Badge>;
    }
    return <Badge variant="neutral">Created</Badge>;
  };

  const parseDate = (value?: string | null) => (value ? new Date(value) : null);
  const daysUntil = (date?: Date | null) => {
    if (!date) return null;
    const diffMs = date.getTime() - new Date().getTime();
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
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
    const fromProfile = detail?.profile?.primaryApplicant?.fullName;
    const fromHr =
      [assignment.employeeFirstName, assignment.employeeLastName].filter(Boolean).join(' ') ||
      (detail
        ? [detail.employeeFirstName, detail.employeeLastName].filter(Boolean).join(' ')
        : '');
    return fromProfile || fromHr || assignment.employeeIdentifier;
  };

  const displayDestination = (assignment: AssignmentSummary) => {
    const detail = assignmentDetails[assignment.id];
    return detail?.profile?.movePlan?.destination || '—';
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

  return (
    <AppShell title="Assignments" subtitle="Create cases, assign employees, and monitor relocations.">
      <div className="space-y-6">
        {error && <Alert variant="error">{error}</Alert>}
        {detailsErrorCount > 0 && (
          <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
            Some case details could not be loaded ({detailsErrorCount} failed). Showing partial data.
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-2">
          <input
            id="hr-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search employees..."
            className="w-64 rounded-full border border-[#e2e8f0] bg-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
          />
          <Button variant="outline" onClick={() => setIsFilterOpen(true)}>Filter</Button>
          {getAuthItem('relopass_role') === 'ADMIN' ? (
            <Link to={buildRoute('adminAssignments')}>
              <Button>Add assignment</Button>
            </Link>
          ) : (
            <Button onClick={handleCreateCase}>Add assignment</Button>
          )}
          <Button variant="outline" onClick={handleCreateCase}>Create case</Button>
        </div>

        {caseId && (
          <Card padding="lg">
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  value={employeeFirstName}
                  onChange={setEmployeeFirstName}
                  label="First name"
                  placeholder="Jane"
                  fullWidth
                />
                <Input
                  value={employeeLastName}
                  onChange={setEmployeeLastName}
                  label="Last name"
                  placeholder="Doe"
                  fullWidth
                />
              </div>
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
                  <div className="flex items-center gap-2 flex-wrap">
                    <span>Assignment ID: <strong>{assignmentId}</strong></span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(assignmentId);
                          setCopyFeedback(true);
                          setTimeout(() => setCopyFeedback(false), 2000);
                        } catch {
                          const el = document.createElement('input');
                          el.value = assignmentId;
                          document.body.appendChild(el);
                          el.select();
                          document.execCommand('copy');
                          document.body.removeChild(el);
                          setCopyFeedback(true);
                          setTimeout(() => setCopyFeedback(false), 2000);
                        }
                      }}
                    >
                      {copyFeedback ? 'Copied!' : 'Copy Assignment ID'}
                    </Button>
                  </div>
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

        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[#0b2b43]">Active relocation cases</span>
              {getAuthItem('relopass_role') === 'ADMIN' && (
                <Link to={buildRoute('adminAssignments')} className="text-xs text-[#0b2b43] hover:underline">
                  Admin Assignments →
                </Link>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!isManageMode ? (
                <>
                  <Button variant="outline" onClick={() => loadAssignments()}>Refresh</Button>
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
          {detailsLoadedCount < assignments.length && !isManageMode && (
            <div className="mb-3 text-xs text-[#6b7280] flex items-center gap-2">
              Loaded details for {detailsLoadedCount}/{assignments.length} cases.
              <Button
                variant="outline"
                onClick={() => loadAssignmentDetails(assignments, assignments.length, undefined)}
              >
                Load remaining details
              </Button>
            </div>
          )}

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

          {isLoading && (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="grid grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,0.3fr] gap-4 px-4 py-4 border-t border-[#e2e8f0] first:border-t-0">
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-32" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-24" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-16" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-4 ml-auto" />
                </div>
              ))}
            </div>
          )}
          {!isLoading && filteredAssignments.length === 0 && (
            <div className="text-sm text-[#4b5563]">No assignments yet.</div>
          )}

          {!isLoading && filteredAssignments.length > 0 && (
            <div className="border border-[#e2e8f0] rounded-xl overflow-hidden">
              <div className={`grid gap-4 bg-[#f8fafc] px-4 py-3 text-[11px] uppercase tracking-wide text-[#6b7280] ${isManageMode ? 'grid-cols-[2rem,1.5fr,1fr,1.5fr,1fr,1fr,0.3fr]' : 'grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,0.3fr]'}`}>
                {isManageMode && <div></div>}
                <div>Employee name</div>
                <div>Destination</div>
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
                        ? `grid-cols-[2rem,1.5fr,1fr,1.5fr,1fr,1fr,0.3fr] ${isSelected ? 'bg-red-50' : 'hover:bg-[#f8fafc]'}`
                        : 'grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,0.3fr] hover:bg-[#f8fafc]'
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
                      <div className="text-xs font-semibold text-[#0b2b43]">{assignment.employeeIdentifier}</div>
                    </div>
                    <div>
                      <div className="text-sm text-[#0b2b43]">{displayDestination(assignment)}</div>
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
                  <option value="created">Created</option>
                  <option value="assigned">Assigned</option>
                  <option value="awaiting_intake">Awaiting intake</option>
                  <option value="submitted">HR review</option>
                  <option value="approved">Approved</option>
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
