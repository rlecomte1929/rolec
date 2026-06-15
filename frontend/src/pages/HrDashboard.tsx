import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Checkbox } from '../components/antigravity/Checkbox';
import { useNavigate, Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { logger } from '../lib/logger';
import { Card, Button, Input, Alert, Badge, Select } from '../components/antigravity';
import { RefreshButton } from '../components/RefreshButton';
import { hrAPI, policyConfigMatrixAPI } from '../api/client';
import type { AssignmentSummary } from '../types';
import { startInteraction, endInteraction } from '../perf/perf';
import { trackAuthPerf } from '../perf/authPerf';
import { buildRoute } from '../navigation/routes';
import { displayNameOrEmail, orEmptyLabel } from '../utils/caseDisplay';
import { useRegisterNav } from '../navigation/registry';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { getAuthItem, normalizeStoredRole } from '../utils/demo';
import { getCaseStatusLabel } from '../utils/caseStatusLabel';
import { trackFirstMeaningfulContent, trackRouteEntry, trackShellRender } from '../perf/pagePerf';
import { CalibrationAlertBanner } from '../components/CalibrationAlertBanner';
import { AnswerProvenanceWidget } from '../components/AnswerProvenanceWidget';

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 300;

export const HrDashboard: React.FC = () => {
  const { setSelectedCaseId } = useSelectedCase();
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState('');
  // CASE-3: field-level validation error for the employee identifier, shown inline
  // next to the input (not the page-top banner).
  const [identifierError, setIdentifierError] = useState('');
  const [caseId, setCaseId] = useState<string | null>(null);
  const [employeeIdentifier, setEmployeeIdentifier] = useState('');
  const [employeeFirstName, setEmployeeFirstName] = useState('');
  const [employeeLastName, setEmployeeLastName] = useState('');
  const [employeeLevel, setEmployeeLevel] = useState('');
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  // New-case form is opened locally; the case is NOT created until the HR user
  // submits a valid employee identifier (prevents orphan empty cases on open).
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // Has this company published a benefits policy? null = unknown/loading.
  const [policyPublished, setPolicyPublished] = useState<boolean | null>(null);
  const [policyBannerDismissed, setPolicyBannerDismissed] = useState<boolean>(
    () => localStorage.getItem('relopass_hr_policy_publish_banner_dismissed') === '1',
  );
  const [search, setSearch] = useState('');
  const [searchDebounced, setSearchDebounced] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [destinationFilter, setDestinationFilter] = useState('');
  const [appliedStatus, setAppliedStatus] = useState<string>('all');
  const [appliedDestination, setAppliedDestination] = useState('');
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedForRemoval, setSelectedForRemoval] = useState<Set<string>>(new Set());
  const [isConfirmingRemoval, setIsConfirmingRemoval] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const navigate = useNavigate();
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const acRef = useRef<AbortController | null>(null);
  const offsetRef = useRef(0);
  const routePerfStartedAt = useRef<number | null>(null);
  const identifierRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    offsetRef.current = offset;
  }, [offset]);

  // Detect whether this company has published a benefits policy. When not, we
  // surface a dismissible nudge — employees can't compare services until then.
  useEffect(() => {
    let cancelled = false;
    policyConfigMatrixAPI
      .hrPublished()
      .then((resp) => {
        if (cancelled) return;
        const r = (resp || {}) as { version_number?: number | null; published_at?: string | null };
        const published =
          Boolean(r.published_at) || (typeof r.version_number === 'number' && r.version_number > 0);
        setPolicyPublished(published);
      })
      .catch(() => {
        // Unknown on error — don't nag if we couldn't determine status.
        if (!cancelled) setPolicyPublished(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const dismissPolicyBanner = useCallback(() => {
    localStorage.setItem('relopass_hr_policy_publish_banner_dismissed', '1');
    setPolicyBannerDismissed(true);
  }, []);

  useEffect(() => {
    routePerfStartedAt.current = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackRouteEntry('/hr/dashboard');
    trackShellRender('/hr/dashboard');
  }, []);

  const loadAssignments = useCallback(async (append = false, signal?: AbortSignal) => {
    const nextOffset = append ? offsetRef.current : 0;
    const nextLimit = PAGE_SIZE;
    const isAppend = append && nextOffset > 0;
    if (isAppend) setIsLoadingMore(true);
    else setIsLoading(true);
    setError('');
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackAuthPerf({ stage: 'bootstrap_start', route: '/hr/dashboard', meta: { endpoint: 'listAssignments' } });
    try {
      const res = await hrAPI.listAssignments({
        signal,
        limit: nextLimit,
        offset: nextOffset,
        search: searchDebounced.trim() || undefined,
        status: appliedStatus !== 'all' ? appliedStatus : undefined,
        destination: appliedDestination.trim() || undefined,
      });
      if (signal?.aborted) return;
      const list = Array.isArray(res.assignments) ? res.assignments : [];
      const totalCount = typeof res.total === 'number' && Number.isFinite(res.total) ? res.total : list.length;
      if (list.length > 0 && !append) {
        localStorage.setItem('relopass_last_assignment_id', list[0].id);
      }
      setAssignments((prev) => (append ? [...prev, ...list] : list));
      setTotal(totalCount);
      setOffset(nextOffset + list.length);
      if (!append && routePerfStartedAt.current != null) {
        const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
        trackFirstMeaningfulContent('/hr/dashboard', now - routePerfStartedAt.current);
        routePerfStartedAt.current = null;
      }
      const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
      trackAuthPerf({ stage: 'bootstrap_end', route: '/hr/dashboard', durationMs: dur, meta: { endpoint: 'listAssignments', count: list.length } });
    } catch (err: any) {
      if (err?.name === 'AbortError' || signal?.aborted) return;
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load assignments.');
      }
      const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
      trackAuthPerf({ stage: 'bootstrap_end', route: '/hr/dashboard', durationMs: dur, meta: { endpoint: 'listAssignments', error: true } });
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [searchDebounced, appliedStatus, appliedDestination, navigate]);

  useEffect(() => {
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => setSearchDebounced(search), SEARCH_DEBOUNCE_MS);
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [search]);

  useEffect(() => {
    acRef.current = new AbortController();
    loadAssignments(false, acRef.current.signal);
    return () => {
      acRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch when filters change, not when loadAssignments identity changes
  }, [searchDebounced, appliedStatus, appliedDestination]);

  useEffect(() => {
    if (isFilterOpen) {
      setStatusFilter(appliedStatus);
      setDestinationFilter(appliedDestination);
    }
  }, [isFilterOpen]);

  useRegisterNav('HrDashboard', [
    { label: 'Case Summary', routeKey: 'hrCaseSummary' },
    { label: 'Compliance', routeKey: 'hrCompliance' },
    { label: 'Package', routeKey: 'hrPackage' },
  ]);

  // Open the New-case form locally. Does NOT create a case — that happens on a
  // validated Assign, so abandoning the form leaves no orphan case behind.
  const openNewCaseForm = () => {
    setError('');
    setInviteToken(null);
    setAssignmentId(null);
    setCaseId(null);
    setEmployeeIdentifier('');
    setEmployeeFirstName('');
    setEmployeeLastName('');
    setEmployeeLevel('');
    setFormOpen(true);
  };

  const handleAssign = async () => {
    if (!employeeIdentifier.trim()) {
      // CASE-3: show the error on the field itself and focus it, not as a far-away banner.
      setIdentifierError('Enter the employee’s email or username to continue.');
      identifierRef.current?.focus();
      return;
    }
    if (submitting || assignmentId) {
      // Guard against double-submit (the success state is already shown).
      return;
    }
    setIdentifierError('');
    setError('');
    setInviteToken(null);
    setAssignmentId(null);
    setSubmitting(true);
    const interaction = startInteraction('HR_ASSIGN_CLICK');
    try {
      // Create the case only now that we have a valid identifier, then assign.
      const created = await hrAPI.createCase();
      setCaseId(created.caseId);
      const response = await hrAPI.assignCase(created.caseId, employeeIdentifier.trim(), {
        firstName: employeeFirstName || undefined,
        lastName: employeeLastName || undefined,
        level: employeeLevel || undefined,
      });
      setAssignmentId(response.assignmentId);
      if (response.inviteToken) {
        setInviteToken(response.inviteToken);
      }
      await loadAssignments(false);
    } catch (err: any) {
      const data = err.response?.data;
      const msg = data?.detail || data?.error || 'Unable to assign case.';
      setError(msg);
      // Log full error to console for debugging (see docs/DEBUG_ASSIGN_ERROR.md)
      logger.error('[Assign failed]', msg, data || err);
    } finally {
      setSubmitting(false);
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
      const results = await Promise.allSettled(
        Array.from(selectedForRemoval, (id) => hrAPI.deleteAssignment(id))
      );
      const failed = results.filter((result) => result.status === 'rejected');
      if (failed.length > 0) {
        throw failed[0];
      }
      setSelectedForRemoval(new Set());
      setIsConfirmingRemoval(false);
      setIsManageMode(false);
      await loadAssignments(false);
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

  // TASK-005: label text comes from the shared getCaseStatusLabel so this matches
  // the Mobility center exactly; only the Badge variant is chosen here.
  const caseStatusBadge = (status: AssignmentSummary['status']) => {
    const label = getCaseStatusLabel(status);
    const variant =
      status === 'approved'
        ? 'success'
        : status === 'rejected' || status === 'awaiting_intake'
        ? 'warning'
        : status === 'submitted'
        ? 'info'
        : 'neutral';
    return <Badge variant={variant}>{label}</Badge>;
  };

  // BRAND-5: lead with the employee's real name; email is a genuine fallback only.
  const employeeName = (assignment: AssignmentSummary) => {
    const safe = (v: unknown) => (typeof v === 'string' && v.trim() ? v.trim() : '');
    return [safe(assignment.employeeFirstName), safe(assignment.employeeLastName)].filter(Boolean).join(' ');
  };
  const displayName = (assignment: AssignmentSummary) =>
    displayNameOrEmail(employeeName(assignment), assignment.employeeIdentifier);

  // BRAND-5: intentional muted empty labels, never 'tbd'/'-'. Destination is the
  // host country only (home country is the route's origin, shown separately).
  const destinationCell = (assignment: AssignmentSummary) =>
    orEmptyLabel(assignment.case?.host_country, 'Destination not set');
  const routeCell = (assignment: AssignmentSummary) => {
    const home = (assignment.case?.home_country || '').trim();
    const host = (assignment.case?.host_country || '').trim();
    return orEmptyLabel(home && host ? `${home} → ${host}` : '', 'Route not set');
  };

  return (
    <AppShell section="HR Operations" title="Cases" subtitle="Track every relocation case. Assign stakeholders, manage status, run the full lifecycle.">
      <div className="space-y-6">
        {/* P5-7: Policy calibration alerts — shown to HR/Admin when benefit caps need review */}
        <CalibrationAlertBanner />

        {/* W2-5: Policy Assistant answer provenance (grounded% / refusal% / unverified) */}
        <AnswerProvenanceWidget />

        {/* Nudge HR to publish a benefits policy — employees can't compare services until they do. */}
        {policyPublished === false && !policyBannerDismissed && (
          <Alert variant="warning" title="You haven't published a benefits policy">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-relaxed">
                Employees won&rsquo;t be able to compare services against your policy until you publish one.
              </p>
              <div className="flex flex-wrap gap-2 shrink-0">
                <Button onClick={() => navigate(buildRoute('hrPolicy'))}>Publish policy →</Button>
                <Button variant="outline" onClick={dismissPolicyBanner}>
                  Dismiss
                </Button>
              </div>
            </div>
          </Alert>
        )}

        {error && (
          <Alert variant="error">
            <span>{error}</span>
            <Button
              variant="outline"
              className="ml-4 text-xs py-1 px-3"
              onClick={() => loadAssignments()}
            >
              Retry
            </Button>
          </Alert>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-2">
          <Input unstyled
            id="hr-search"
            value={search}
            onChange={(event) => setSearch(event)}
            placeholder="Search employees..."
            className="w-64 rounded-full border border-[#e2e8f0] bg-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
          />
          {/* BRAND-1: 'New case' is the single filled primary on this Cases
              surface; Filter + All assignments are secondary/ghost. */}
          <Button variant="outline" onClick={() => setIsFilterOpen(true)}>Filter</Button>
          {normalizeStoredRole(getAuthItem('relopass_role')) === 'ADMIN' && (
            <Link to={buildRoute('adminAssignments')}>
              <Button variant="outline">All assignments</Button>
            </Link>
          )}
          <Button onClick={openNewCaseForm}>New case</Button>
        </div>

        {formOpen && (
          <Card padding="lg">
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  value={employeeFirstName}
                  onChange={setEmployeeFirstName}
                  label="First name (optional)"
                  placeholder="Jane"
                  fullWidth
                />
                <Input
                  value={employeeLastName}
                  onChange={setEmployeeLastName}
                  label="Last name (optional)"
                  placeholder="Doe"
                  fullWidth
                />
              </div>
              <Input
                ref={identifierRef}
                value={employeeIdentifier}
                onChange={(v) => {
                  setEmployeeIdentifier(v);
                  if (identifierError) setIdentifierError('');
                }}
                label="Employee username or email *"
                placeholder="jane_doe or jane@company.com"
                error={identifierError}
                required
                fullWidth
              />
              <Select
                value={employeeLevel}
                onChange={setEmployeeLevel}
                label="Seniority level (sets benefit caps)"
                placeholder="— Select level (optional) —"
                options={[
                  { value: 'manager', label: 'Manager' },
                  { value: 'director', label: 'Director' },
                  { value: 'vp', label: 'VP' },
                  { value: 'c_suite', label: 'C-suite' },
                ]}
              />
              <Button onClick={handleAssign} disabled={submitting || !!assignmentId}>
                {submitting ? 'Assigning…' : 'Assign'}
              </Button>
              {assignmentId && (
                <Alert variant="info" title="Assignment created">
                  <div className="space-y-3 text-[#0b2b43]">
                    <p className="text-sm leading-relaxed">
                      An <strong>invite email</strong> has been sent to <strong>{employeeIdentifier.trim()}</strong> with
                      a link to get started — they can <strong>register</strong> with that email (or <strong>sign in</strong>{' '}
                      if they already have an account), and the case attaches automatically when the login matches.
                    </p>
                    {caseId && (
                      <Button onClick={() => navigate(buildRoute('hrCaseSummary', { caseId }))}>
                        Open case →
                      </Button>
                    )}
                    {/* CASE-2: keep the success state calm — the assignment ID, invite token, and
                        manual-claim steps are support-tier details, tucked behind a disclosure for
                        the rare "email didn't arrive / typo in the identifier" case. */}
                    <details className="mt-1 text-sm text-[#4b5563]">
                      <summary className="cursor-pointer font-medium text-[#0b2b43]">
                        Didn&rsquo;t get the email?
                      </summary>
                      <div className="space-y-3 mt-3">
                        <p className="leading-relaxed">
                          For a <strong>manual claim</strong> (e.g. a typo in the identifier), the employee can attach the
                          case with the assignment ID below. In ReloPass they enter:
                        </p>
                        <ol className="list-decimal pl-5 space-y-1.5">
                          <li>
                            Field 1: <strong>ReloPass email or username</strong> (what they sign in with, not the ID).
                          </li>
                          <li>
                            Field 2: <strong>Assignment ID</strong> (the UUID below).
                          </li>
                        </ol>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span>
                            Assignment ID: <strong className="font-mono">{assignmentId}</strong>
                          </span>
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
                        {inviteToken && (
                          <div>
                            <p className="mb-1">Invite token (optional, for your records):</p>
                            <span className="font-mono break-all">{inviteToken}</span>
                          </div>
                        )}
                      </div>
                    </details>
                  </div>
                </Alert>
              )}
            </div>
          </Card>
        )}

        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[#0b2b43]">Active relocation cases</span>
              {normalizeStoredRole(getAuthItem('relopass_role')) === 'ADMIN' && (
                <Link to={buildRoute('adminAssignments')} className="text-xs text-[#0b2b43] hover:underline">
                  Admin Assignments →
                </Link>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!isManageMode ? (
                <>
                  <RefreshButton onClick={() => loadAssignments(false)} label="Refresh" />
                  <Button variant="outline" onClick={() => setIsManageMode(true)}>Manage cases</Button>
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
          {assignments.length < total && !isManageMode && (
            <div className="mb-3 text-xs text-[#6b7280] flex items-center gap-2">
              Showing {assignments.length} of {total} cases.
              <Button
                variant="outline"
                onClick={() => loadAssignments(true)}
                disabled={isLoadingMore}
              >
                {isLoadingMore ? 'Loading…' : 'Load more'}
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
                <Button unstyled
                  onClick={handleRemoveSelected}
                  disabled={isDeleting}
                  className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {isDeleting ? 'Removing...' : 'Confirm removal'}
                </Button>
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
          {!isLoading && assignments.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="text-sm text-[#4b5563]">No active cases.</p>
              <p className="text-xs text-[#6b7280]">Open the first case — every stakeholder works from the same record.</p>
            </div>
          )}

          {!isLoading && assignments.length > 0 && (
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
              {assignments.map((assignment) => {
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
                    {...(!isManageMode && {
                      role: 'button',
                      tabIndex: 0,
                      onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setSelectedCaseId(assignment.id);
                          navigate(buildRoute('hrCaseSummary', { caseId: assignment.id }));
                        }
                      },
                    })}
                    className={`grid gap-4 px-4 py-4 border-t border-[#e2e8f0] items-center cursor-pointer ${
                      isManageMode
                        ? `grid-cols-[2rem,1.5fr,1fr,1.5fr,1fr,1fr,0.3fr] ${isSelected ? 'bg-red-50' : 'hover:bg-[#f8fafc]'}`
                        : 'grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,0.3fr] hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-[#2563eb] focus-visible:outline-none'
                    }`}
                  >
                    {isManageMode && (
                      <div className="flex items-center justify-center">
                        <Checkbox
                          checked={isSelected}
                          onChange={() => toggleSelection(assignment.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded border-[#d1d5db] text-red-600 focus:ring-red-500"
                        />
                      </div>
                    )}
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{displayName(assignment)}</div>
                      {/* BRAND-5: only show the email subline when it isn't already the
                          primary identity (i.e. a real name exists) \u2014 avoids the email twice. */}
                      {employeeName(assignment) ? (
                        <div className="text-xs text-[#6b7280]">{assignment.employeeIdentifier}</div>
                      ) : null}
                    </div>
                    <div>
                      {(() => {
                        const d = destinationCell(assignment);
                        return <div className={`text-sm ${d.isEmpty ? 'text-slate-400' : 'text-[#0b2b43]'}`}>{d.text}</div>;
                      })()}
                    </div>
                    <div>
                      {(() => {
                        const r = routeCell(assignment);
                        return <div className={`text-sm ${r.isEmpty ? 'text-slate-400' : 'text-[#0b2b43]'}`}>{r.text}</div>;
                      })()}
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {caseStatusBadge(assignment.status)}
                    </div>
                    <div>
                      <div className="text-sm text-[#0b2b43]">
                        {assignment.nextDeadline?.trim() || '—'}
                      </div>
                      <div className="text-xs text-[#6b7280]">
                        {assignment.nextDeadline?.trim() ? 'Next milestone' : 'No upcoming date'}
                      </div>
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
              <Button unstyled
                onClick={() => setIsFilterOpen(false)}
                className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
              >
                Close
              </Button>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Status</div>
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                >
                  {/* TASK-005: option labels match the table cell labels (getCaseStatusLabel).
                      created+assigned are the same "Not started" state — one option (value
                      'assigned', the post-assign norm); 'created' cases show under All statuses. */}
                  <option value="all">All statuses</option>
                  <option value="assigned">Not started</option>
                  <option value="awaiting_intake">Intake in progress</option>
                  <option value="submitted">Awaiting HR review</option>
                  <option value="approved">Complete</option>
                  <option value="rejected">Rejected</option>
                  <option value="closed">Canceled</option>
                </select>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Destination</div>
                <Input unstyled
                  value={destinationFilter}
                  onChange={(event) => setDestinationFilter(event)}
                  placeholder="Singapore, New York, etc."
                  className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setStatusFilter('all');
                    setDestinationFilter('');
                    setAppliedStatus('all');
                    setAppliedDestination('');
                    setIsFilterOpen(false);
                  }}
                >
                  Reset
                </Button>
                <Button
                  onClick={() => {
                    setAppliedStatus(statusFilter);
                    setAppliedDestination(destinationFilter);
                    setIsFilterOpen(false);
                  }}
                >
                  Apply filters
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
};
