import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Checkbox } from '../components/antigravity/Checkbox';
import { AppShell } from '../components/AppShell';
import { logger } from '../lib/logger';
import { Card, Button, Input, Alert, Badge, Select } from '../components/antigravity';
import { RefreshButton } from '../components/RefreshButton';
import { hrAPI } from '../api/client';
import { emitTestDriveStage } from '../api/testDrive';
import type { AssignmentSummary } from '../types';
import { startInteraction, endInteraction } from '../perf/perf';
import { buildRoute } from '../navigation/routes';
import { displayNameOrEmail, orEmptyLabel } from '../utils/caseDisplay';
import { useRegisterNav } from '../navigation/registry';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { getAuthItem, normalizeStoredRole } from '../utils/demo';
import { getCaseStatusLabel } from '../utils/caseStatusLabel';
import { trackRouteEntry, trackShellRender } from '../perf/pagePerf';
import { useHrAssignments } from '../hooks/useHrAssignments';
import { usePolicyPublished } from '../hooks/usePolicyPublished';
import { CalibrationAlertBanner } from '../components/CalibrationAlertBanner';
import { AnswerProvenanceWidget } from '../components/AnswerProvenanceWidget';
import { trackFirstCaseCreated } from '../perf/hrOnboardingInstrumentation';
import { useVariant } from '../lib/feature-flags';
import { registerSuperProperties } from '../analytics';
import { InferredOnboardingPanel } from '../features/platform-v2/InferredOnboardingPanel';
import { useWelcomeRedirect } from '../hooks/useWelcomeRedirect';

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Zero-cases onboarding empty state for the HR Cases page (E1.1–E1.2). Explains
 * what a case is and offers the first-case CTA, which reuses the same
 * openNewCaseForm handler as the toolbar "New case" button.
 */
function CasesEmptyState({ onCreateCase }: { onCreateCase: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center max-w-md mx-auto">
      <h3 className="text-lg font-semibold text-[#0b2b43] mb-2">No relocation cases yet.</h3>
      <p className="text-sm text-[#4b5563] mb-6">
        A case is the record for one employee&rsquo;s move. It holds their timeline,
        documents, vendor assignments, and compliance status.
      </p>
      <Button onClick={onCreateCase}>Open your first case →</Button>
      <p className="text-sm text-[#6b7280] mt-2">
        Takes about 2 minutes. You&rsquo;ll add the employee, destination, and move date.
      </p>
    </div>
  );
}

export const HrDashboard: React.FC = () => {
  // AIQ-1568 (TD-BUG-1): `?new=1` means the user pressed an explicit "create a case"
  // CTA elsewhere (the command-center empty state) and is being routed here to the one
  // real form. Read it before the welcome hook so a first-login redirect cannot swallow
  // that intent: a fresh test-drive HR who clicks "Add your first relocation" must land
  // on the form, not on the onboarding wizard. The welcome page still shows on a plain
  // first login — it just no longer overrides a deliberate destination.
  //
  // AIQ-1590: latch it ONCE at mount (lazy init). The openNewCaseForm effect below strips
  // `?new=1` from the URL, so recomputing from window.location.search on every render would
  // flip this false → flip `skip` false → re-fire useWelcomeRedirect (skip is one of its
  // effect deps) → bounce the first-login HR to /hr/welcome after all. A latched value keeps
  // `skip` stable for the whole mount, so the redirect stays suppressed.
  const [wantsNewCase] = useState(() => new URLSearchParams(window.location.search).get('new') === '1');
  useWelcomeRedirect('/hr/welcome', { skip: wantsNewCase });
  const { setSelectedCaseId } = useSelectedCase();
  // AIQ-1223e: A/B arm for inference-based onboarding. 'inferred' shows the
  // suggested-setup surface; anything else (control / error / disabled) keeps
  // the manual empty-state. Resolved deterministically by useVariant.
  const onboardingVariant = useVariant('hr_inference_onboarding');
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
  // AIQ-1572: did the backend actually queue an invite email for this assignment?
  const [inviteEmailSent, setInviteEmailSent] = useState(true);
  // New-case form is opened locally; the case is NOT created until the HR user
  // submits a valid employee identifier (prevents orphan empty cases on open).
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [policyBannerDismissed, setPolicyBannerDismissed] = useState<boolean>(
    () => localStorage.getItem('relopass_hr_policy_publish_banner_dismissed') === '1',
  );
  const [search, setSearch] = useState('');
  const [searchDebounced, setSearchDebounced] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  // RX-5: the applied server-side filters (status + destination) are URL state
  // (?status=&destination=) so reload / back-button / deep-links preserve the view.
  // The modal "draft" (statusFilter/destinationFilter) and the client-side
  // date-range stay local — they only become URL state on Apply.
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedStatus = searchParams.get('status') ?? 'all';
  const appliedDestination = searchParams.get('destination') ?? '';
  const [statusFilter, setStatusFilter] = useState<string>(appliedStatus);
  const [destinationFilter, setDestinationFilter] = useState(appliedDestination);
  // NAV-HR-1: client-side "submitted between" date-range filter (the list API has
  // no date param, so this narrows the loaded rows). Draft state lives in the modal;
  // `applied*` is what the table actually filters on.
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [appliedDateFrom, setAppliedDateFrom] = useState('');
  const [appliedDateTo, setAppliedDateTo] = useState('');
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedForRemoval, setSelectedForRemoval] = useState<Set<string>>(new Set());
  const [isConfirmingRemoval, setIsConfirmingRemoval] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const navigate = useNavigate();
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const routePerfStartedAt = useRef<number | null>(null);
  const identifierRef = useRef<HTMLInputElement>(null);

  // RX-5: write the applied status/destination filters into the URL query string
  // (omitting defaults to keep the URL clean). Pushes a history entry so the
  // back-button steps through filter changes; preserves any other params.
  const applyFiltersToUrl = useCallback(
    (status: string, destination: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (status && status !== 'all') next.set('status', status);
        else next.delete('status');
        if (destination) next.set('destination', destination);
        else next.delete('destination');
        return next;
      });
    },
    [setSearchParams],
  );

  // null = unknown/loading; gate the publish nudge on `=== false` only.
  const policyPublished = usePolicyPublished();

  const dismissPolicyBanner = useCallback(() => {
    localStorage.setItem('relopass_hr_policy_publish_banner_dismissed', '1');
    setPolicyBannerDismissed(true);
  }, []);

  useEffect(() => {
    routePerfStartedAt.current = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackRouteEntry('/hr/dashboard');
    trackShellRender('/hr/dashboard');
  }, []);

  // AIQ-1223e: attach the resolved arm as a PostHog super-property so PR-A's HR
  // onboarding events (AIQ-1223b) split by experiment arm. No-op without a key.
  useEffect(() => {
    registerSuperProperties({ hr_inference_onboarding: onboardingVariant });
  }, [onboardingVariant]);

  // Assignments list as a TanStack infinite query (RX-2). The filters are part of
  // the query key, so changing one refetches from page 0 automatically — no manual
  // AbortController / refetch effect needed.
  const {
    assignments,
    total,
    isLoading,
    isLoadingMore,
    isFetching: assignmentsFetching,
    isError: assignmentsError,
    hasMore,
    loadMore,
    reload: reloadAssignments,
  } = useHrAssignments(
    { search: searchDebounced, status: appliedStatus, destination: appliedDestination },
    routePerfStartedAt,
  );

  // Parity with the old loadAssignments, which cleared any transient mutation/
  // validation error at the start of every fetch.
  useEffect(() => {
    if (assignmentsFetching) setError('');
  }, [assignmentsFetching]);

  useEffect(() => {
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => setSearchDebounced(search), SEARCH_DEBOUNCE_MS);
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [search]);

  useEffect(() => {
    if (isFilterOpen) {
      setStatusFilter(appliedStatus);
      setDestinationFilter(appliedDestination);
      setDateFrom(appliedDateFrom);
      setDateTo(appliedDateTo);
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

  // AIQ-1568 (TD-BUG-1): honour the ?new=1 deep link from the command-center CTA, which
  // used to navigate to the non-existent '/employees/new'. The form is local state, so a
  // caller cannot route straight to it — this is the seam. Consume the param once so a
  // refresh or a back-nav doesn't re-open the form behind the user.
  useEffect(() => {
    if (searchParams.get('new') !== '1') return;
    openNewCaseForm();
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('new');
        return next;
      },
      { replace: true },
    );
    // Mount-only: the param is consumed immediately, so re-running on every
    // searchParams change would fight the delete above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      // AIQ-1223b: HR onboarding signal — fire only on the genuinely first case
      // (no prior assignments). PII-free: a single count.
      if (assignments.length === 0) {
        trackFirstCaseCreated({ prior_case_count: assignments.length });
      }
      setCaseId(created.caseId);
      // TD-FIX-4 (AIQ-1505): test-drive funnel — HR handed off a case (no-op for real users).
      emitTestDriveStage('hr-handoff');
      const response = await hrAPI.assignCase(created.caseId, employeeIdentifier.trim(), {
        firstName: employeeFirstName || undefined,
        lastName: employeeLastName || undefined,
        level: employeeLevel || undefined,
      });
      setAssignmentId(response.assignmentId);
      // AIQ-1572: test-drive assignments no longer send a Resend invite, so the panel
      // must not keep asserting one was sent. Default true — an older payload without
      // the field keeps the previous copy.
      setInviteEmailSent(response.inviteEmailSent !== false);
      if (response.inviteToken) {
        setInviteToken(response.inviteToken);
      }
      await reloadAssignments();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string; error?: string } } };
      const data = e.response?.data;
      const msg = data?.detail || data?.error || 'Unable to assign case.';
      setError(msg);
      // Log full error to console for debugging (see docs/DEBUG_ASSIGN_ERROR.md)
      logger.error('[Assign failed]', msg, data ?? err);
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
      await reloadAssignments();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Failed to remove some cases.');
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

  // E1.1–E1.3: a genuine zero-cases HR (no cases at all, no active search) gets
  // the onboarding empty state. A search that happens to match nothing is NOT
  // "no cases" — it keeps the toolbar + a "no matches" message, so onboarding
  // copy never wrongly appears for an HR who already has cases.
  const hasNoCases = total === 0 && !searchDebounced.trim();

  // NAV-HR-1: status-priority order — surface what needs HR action first.
  // Pending Action (Awaiting HR review > Rejected) > In Progress
  // (Intake > Not started > Created) > Completed > Canceled/archived.
  const STATUS_PRIORITY: Record<AssignmentSummary['status'], number> = {
    submitted: 0,
    rejected: 1,
    awaiting_intake: 2,
    assigned: 3,
    created: 4,
    approved: 5,
    closed: 6,
  };

  const formatSubmitted = (iso?: string | null): string | null => {
    if (!iso) return null;
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return null;
    return new Date(t).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  // Default-sort by status priority, then oldest-submitted first (waiting longest).
  // The "submitted between" range filters client-side on the loaded rows (the list
  // API exposes no date param — see appliedDateFrom/To above).
  const displayedAssignments = useMemo(() => {
    const inRange = (iso?: string | null) => {
      if (!appliedDateFrom && !appliedDateTo) return true;
      if (!iso) return false;
      const day = iso.slice(0, 10); // YYYY-MM-DD
      if (appliedDateFrom && day < appliedDateFrom) return false;
      if (appliedDateTo && day > appliedDateTo) return false;
      return true;
    };
    const rank = (s: AssignmentSummary['status']) => STATUS_PRIORITY[s] ?? 99;
    return assignments
      .filter((a) => inRange(a.submittedAt))
      .slice()
      .sort((a, b) => {
        const pr = rank(a.status) - rank(b.status);
        if (pr !== 0) return pr;
        const sa = a.submittedAt ?? '';
        const sb = b.submittedAt ?? '';
        if (sa && sb) return sa < sb ? -1 : sa > sb ? 1 : 0;
        if (sa) return -1;
        if (sb) return 1;
        return 0;
      });
    // STATUS_PRIORITY is a stable literal; assignments + applied dates drive recompute.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignments, appliedDateFrom, appliedDateTo]);

  // NAV-HR-1: shared column template so the header and rows stay in sync.
  // Cols: [Employee] [Destination] [Route] [Status] [Submitted] [Next deadline] [Compliance] [View].
  const gridCols = isManageMode
    ? 'grid-cols-[2rem,1.5fr,1fr,1.5fr,1fr,1fr,1fr,1fr,0.3fr]'
    : 'grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,1fr,1fr,0.3fr]';

  // One error channel: local mutation/validation errors take precedence, falling
  // back to the assignments-query failure message.
  const displayedError = error || (assignmentsError ? 'Unable to load assignments.' : '');

  return (
    <AppShell section="HR Operations" title="Cases" subtitle="Every cross-border relocation starts here. Create a case to build a plan, assign documents, and track progress — for each employee, from offer to arrival.">
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

        {displayedError && (
          <Alert variant="error">
            <span>{displayedError}</span>
            <Button
              variant="outline"
              className="ml-4 text-xs py-1 px-3"
              onClick={() => reloadAssignments()}
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
            placeholder="Search cases..."
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
                    {/* AIQ-1572: say what actually happened. Test-drive assignments no
                        longer send a Resend invite, and this panel previously asserted a
                        send purely because an assignmentId existed. */}
                    {inviteEmailSent ? (
                      <p className="text-sm leading-relaxed">
                        An <strong>invite email</strong> has been sent to <strong>{employeeIdentifier.trim()}</strong> with
                        a link to get started — they can <strong>register</strong> with that email (or <strong>sign in</strong>{' '}
                        if they already have an account), and the case attaches automatically when the login matches.
                      </p>
                    ) : (
                      <p className="text-sm leading-relaxed" data-testid="assign-no-invite-email">
                        <strong>No invite email was sent</strong> — <strong>{employeeIdentifier.trim()}</strong> is a test
                        account, and its login is already shown on the test-drive page. Sign in with that email (or{' '}
                        <strong>register</strong> it) and the case attaches automatically when the login matches.
                      </p>
                    )}
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
          {/* E1.3: the "Active relocation cases" header is a label for existing
              content — hide the whole toolbar when there are no cases yet. */}
          {!hasNoCases && (
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
                  <RefreshButton onClick={() => reloadAssignments()} label="Refresh" />
                  <Button variant="outline" onClick={() => setIsManageMode(true)}>Remove cases</Button>
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
          )}
          {hasMore && !isManageMode && (
            <div className="mb-3 text-xs text-[#6b7280] flex items-center gap-2">
              Showing {assignments.length} of {total} cases.
              <Button
                variant="outline"
                onClick={loadMore}
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
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="grid grid-cols-[1.5fr,1fr,1.5fr,1fr,1fr,1fr,1fr,0.3fr] gap-4 px-4 py-4 border-t border-[#e2e8f0] first:border-t-0">
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-32" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-24" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-16" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-20" />
                  <div className="h-5 rounded bg-[#e2e8f0] animate-pulse w-16" />
                  <div className="h-4 rounded bg-[#e2e8f0] animate-pulse w-4 ml-auto" />
                </div>
              ))}
            </div>
          )}
          {/* E1.1–E1.2: first-time HR (no cases at all) → onboarding empty state
              that explains what a case is and how to open the first one. */}
          {!isLoading && hasNoCases && (
            onboardingVariant === 'inferred'
              ? <InferredOnboardingPanel onCreateCase={openNewCaseForm} />
              : <CasesEmptyState onCreateCase={openNewCaseForm} />
          )}
          {/* Search/filter matched nothing, but the HR does have cases. */}
          {!isLoading && !hasNoCases && displayedAssignments.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="text-sm text-[#4b5563]">No cases match your search.</p>
              <p className="text-xs text-[#6b7280]">Clear the search or adjust your filters to see all cases.</p>
            </div>
          )}

          {!isLoading && displayedAssignments.length > 0 && (
            <div className="border border-[#e2e8f0] rounded-xl overflow-hidden">
              <div className={`grid gap-4 bg-[#f8fafc] px-4 py-3 text-[11px] uppercase tracking-wide text-[#6b7280] ${gridCols}`}>
                {isManageMode && <div></div>}
                <div>Employee name</div>
                <div>Destination</div>
                <div>Route (origin → dest)</div>
                <div>Status</div>
                <div>Submitted</div>
                <div>Next deadline</div>
                <div>Compliance</div>
                <div className="text-right">View</div>
              </div>
              {displayedAssignments.map((assignment) => {
                const isSelected = selectedForRemoval.has(assignment.id);
                return (
                  <div
                    key={assignment.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      if (isManageMode) {
                        toggleSelection(assignment.id);
                        return;
                      }
                      setSelectedCaseId(assignment.id);
                      navigate(buildRoute('hrCaseSummary', { caseId: assignment.id }));
                    }}
                    onKeyDown={(event: React.KeyboardEvent<HTMLDivElement>) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        if (isManageMode) {
                          toggleSelection(assignment.id);
                        } else {
                          setSelectedCaseId(assignment.id);
                          navigate(buildRoute('hrCaseSummary', { caseId: assignment.id }));
                        }
                      }
                    }}
                    className={`grid gap-4 px-4 py-4 border-t border-[#e2e8f0] items-center cursor-pointer ${gridCols} ${
                      isManageMode
                        ? (isSelected ? 'bg-red-50' : 'hover:bg-[#f8fafc]')
                        : 'hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-[#2563eb] focus-visible:outline-none'
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
                      {(() => {
                        const submitted = formatSubmitted(assignment.submittedAt);
                        return submitted
                          ? <div className="text-sm text-[#0b2b43]">{submitted}</div>
                          : <div className="text-sm text-slate-400">—</div>;
                      })()}
                    </div>
                    <div>
                      <div className="text-sm text-[#0b2b43]">
                        {assignment.nextDeadline?.trim() || '—'}
                      </div>
                      <div className="text-xs text-[#6b7280]">
                        {assignment.nextDeadline?.trim() ? 'Next milestone' : 'No upcoming date'}
                      </div>
                    </div>
                    <div>
                      {assignment.complianceStatus?.trim()
                        ? <span className="text-sm text-[#0b2b43] capitalize">{assignment.complianceStatus.replace(/_/g, ' ')}</span>
                        : <span className="text-sm text-slate-400">—</span>}
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
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Submitted between</div>
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    value={dateFrom}
                    max={dateTo || undefined}
                    onChange={(event) => setDateFrom(event.target.value)}
                    aria-label="Submitted from"
                    className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                  />
                  <span className="text-sm text-[#6b7280]">to</span>
                  <input
                    type="date"
                    value={dateTo}
                    min={dateFrom || undefined}
                    onChange={(event) => setDateTo(event.target.value)}
                    aria-label="Submitted to"
                    className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
                  />
                </div>
              </div>
              {/* NAV-HR-1: Relocation type and Assigned agent are intentionally not
                  offered — the /api/hr/assignments payload (AssignmentSummary) carries
                  neither, so filtering on them would require a backend change. */}
              <div className="flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setStatusFilter('all');
                    setDestinationFilter('');
                    setDateFrom('');
                    setDateTo('');
                    applyFiltersToUrl('all', '');
                    setAppliedDateFrom('');
                    setAppliedDateTo('');
                    setIsFilterOpen(false);
                  }}
                >
                  Reset
                </Button>
                <Button
                  onClick={() => {
                    applyFiltersToUrl(statusFilter, destinationFilter);
                    setAppliedDateFrom(dateFrom);
                    setAppliedDateTo(dateTo);
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
