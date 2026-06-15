import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, Input, LoadingButton } from '../components/antigravity';
import { RefreshButton } from '../components/RefreshButton';
import { employeeAPI } from '../api/client';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { JourneySpine } from '../features/employee-journey/JourneySpine';
import { EmployeeNoCaseOnboarding } from '../features/employee-journey/EmployeeNoCaseOnboarding';
import { INTAKE_TOTAL_STEPS } from '../features/platform-v2/intake/intakeSteps';
import { buildRoute } from '../navigation/routes';
import { getAuthItem } from '../utils/demo';
import type { PostSignupReconciliation } from '../types';
import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';
import { formatDestinationLabel, formatCaseReference } from '../types/employeeAssignmentOverview';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';
import { formatRichMessage } from '../utils/richMessage';
import { logEmployeeEntry } from '../utils/employeeJourneyPerf';
import { trackAssignmentFlow, ASSIGNMENT_FLOW_EVENTS } from '../perf/assignmentLinkingInstrumentation';
import { statusLabel } from '../lib/statusLabel';
import { getApiErrorCode } from '../utils/apiDetail';
import { trackFirstMeaningfulContent, trackRouteEntry, trackShellRender } from '../perf/pagePerf';
import { getLastVisited } from '../utils/employeeCaseProgress';

/**
 * Resolve where to send the user when they click "Open case" on the
 * dashboard. Honor the last route they visited inside this assignment
 * (so re-entering doesn't force them through the wizard again). Falls
 * back to the case summary page when no last-visited is recorded.
 *
 * Both `assigned` (fresh assignment from HR, employee hasn't started
 * intake yet) and `awaiting_intake` (employee started intake but hasn't
 * submitted) are pre-intake states whose entry point is the intake wizard.
 *
 * AIQ-976: route pre-intake to the CASE-SCOPED intake (/employee/case/{id}/intake)
 * rather than the bare /employee/intake. The bare route renders the v2
 * EmployeeIntakePage against the *primary* case from EmployeeAssignmentContext,
 * so for a multi-case employee every row opened the same (first) case. The
 * case-scoped route makes EmployeeIntakePage read the clicked case from the URL.
 */
function openCaseHref(assignmentId: string, status?: string | null): string {
  if (status === 'awaiting_intake' || status === 'assigned') {
    return `/employee/case/${assignmentId}/intake`;
  }
  return getLastVisited(assignmentId) || `/employee/case/${assignmentId}/summary`;
}

/** Pattern to detect a case code pasted into the wrong field. */
const ASSIGNMENT_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Dismissed pending-ID set per user (localStorage): when signature matches current pending rows, banner stays hidden. */
function pendingBannerStorageKey(): string {
  const uid = getAuthItem('relopass_user_id') || 'anon';
  return `relopass_employee_new_pending_banner_dismissed_${uid}`;
}

function formatOverviewDate(iso: string | null | undefined): string {
  if (!iso?.trim()) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function linkedStatusLabel(row: EmployeeLinkedOverviewRow): string {
  const parts = [row.status, row.current_stage].filter(Boolean);
  return parts.length ? parts.join(' · ') : '-';
}

/** Maps backend claim-state codes to human-readable strings.
 *  Delegates to the shared statusLabel() utility (AUDIT-A5 / AIQ-358). */
function claimStateLabel(state: string): string {
  return statusLabel(state);
}

function ManualClaimInstructions({ signedInPrincipal }: { signedInPrincipal: string | null }) {
  return (
    <div
      className="mt-4 rounded-lg border border-[#93c5fd] bg-[#eff6ff] px-4 py-3 text-sm text-[#1e3a5f]"
      role="region"
      aria-label="How to fill the claim form"
    >
      <div className="font-semibold text-[#0b2b43] mb-2">How to connect your case</div>
      <ol className="list-decimal pl-5 space-y-2 text-[#334155]">
        <li>
          <strong className="text-[#0b2b43]">Your email:</strong> The work email HR used when they set up your move.
        </li>
        <li>
          <strong className="text-[#0b2b43]">Code from HR:</strong> The case code HR sent you (looks like a long series
          of letters and numbers).
        </li>
      </ol>
      {signedInPrincipal ? (
        <p className="mt-3 text-xs text-[#64748b] border-t border-[#bfdbfe] pt-3">
          Signed in as <span className="font-medium text-[#0b2b43]">{signedInPrincipal}</span>. Use the same email in
          the first field.
        </p>
      ) : null}
    </div>
  );
}

function EmployeeAssignmentBootstrapCard({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="mb-6" role="status" aria-live="polite" aria-busy="true">
      <Card
        padding="lg"
        className="border border-[#e2e8f0] flex flex-col items-center text-center py-12"
      >
        <div
          className="h-10 w-10 rounded-full border-2 border-[#0b2b43] border-t-transparent animate-spin mb-4"
          aria-hidden
        />
        <p className="text-base font-semibold text-[#0b2b43]">{title}</p>
        {detail ? <p className="text-sm text-[#64748b] mt-2 max-w-md">{detail}</p> : null}
      </Card>
    </div>
  );
}

export const EmployeeJourney: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const {
    assignmentId,
    isLoading: assignmentLoading,
    refetch: refetchAssignment,
    linkedCount,
    pendingCount,
    linkedSummaries,
    pendingSummaries,
    overviewError,
  } = useEmployeeAssignment();
  const [error, setError] = useState('');
  const [claimId, setClaimId] = useState('');
  const [claimEmail, setClaimEmail] = useState(
    getAuthItem('relopass_email') || getAuthItem('relopass_username') || ''
  );
  /** Magic-link auto-claim: true while resolving a ?token= from the URL. */
  const [tokenClaimInProgress, setTokenClaimInProgress] = useState(false);
  const tokenClaimAttempted = useRef(false);
  const [isClaiming, setIsClaiming] = useState(false);
  const [claimingPendingId, setClaimingPendingId] = useState<string | null>(null);
  const [linkRec, setLinkRec] = useState<PostSignupReconciliation | null>(null);
  /** Hub: collapsed manual claim form unless user opens it (always expanded for primary fallback). */
  const [manualClaimExpanded, setManualClaimExpanded] = useState(false);
  const [bannerDismissNonce, setBannerDismissNonce] = useState(0);

  const hasLinked = linkedCount > 0;
  const hasPendingOnly = !hasLinked && pendingCount > 0;
  /** No linked and no auto-detected pending → full assignment-ID / manual claim experience. */
  const showPrimaryManualClaimPage = !hasLinked && !hasPendingOnly;
  const showPendingSection = pendingCount > 0;
  /** Secondary manual path: linked and/or pending hub: recovery & HR case code without a parallel API. */
  const showSecondaryManualClaimCard = hasLinked || hasPendingOnly;

  const pendingIdsSignature = useMemo(
    () =>
      [...pendingSummaries.map((r) => r.assignment_id)]
        .filter(Boolean)
        .sort()
        .join('\n'),
    [pendingSummaries]
  );

  useEffect(() => {
    if (hasPendingOnly) setManualClaimExpanded(true);
  }, [hasPendingOnly]);

  const showNewAssignmentBanner = useMemo(() => {
    if (assignmentLoading || !hasLinked || pendingCount === 0 || !pendingIdsSignature) return false;
    try {
      const dismissed = localStorage.getItem(pendingBannerStorageKey()) ?? '';
      return dismissed !== pendingIdsSignature;
    } catch {
      return true;
    }
  }, [assignmentLoading, hasLinked, pendingCount, pendingIdsSignature, bannerDismissNonce]);

  const dismissNewAssignmentBanner = () => {
    try {
      localStorage.setItem(pendingBannerStorageKey(), pendingIdsSignature);
    } catch {
      /* ignore */
    }
    setBannerDismissNonce((n) => n + 1);
  };

  const scrollToPendingSection = () => {
    document.getElementById('employee-hub-pending-assignments')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const entryStartedAt = useRef<number | null>(null);
  const loggedAssignmentResolution = useRef(false);
  const routePerfStartedAt = useRef<number | null>(null);

  const signedInPrincipal =
    (getAuthItem('relopass_email') || getAuthItem('relopass_username') || '').trim() || null;

  useEffect(() => {
    routePerfStartedAt.current = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackRouteEntry('/employee/journey');
    trackShellRender('/employee/journey');
  }, []);

  useEffect(() => {
    if (assignmentLoading) return;
    const startedAt = routePerfStartedAt.current;
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackFirstMeaningfulContent('/employee/journey', startedAt != null ? now - startedAt : undefined);
  }, [assignmentLoading]);

  useEffect(() => {
    try {
      const raw =
        sessionStorage.getItem('post_auth_claim_reconciliation') ||
        sessionStorage.getItem('post_signup_reconciliation');
      if (!raw) return;
      sessionStorage.removeItem('post_auth_claim_reconciliation');
      sessionStorage.removeItem('post_signup_reconciliation');
      const data = JSON.parse(raw) as PostSignupReconciliation;
      setLinkRec(data);
      void refetchAssignment();
    } catch {
      /* ignore */
    }
  }, [refetchAssignment]);

  useEffect(() => {
    entryStartedAt.current = performance.now();
    loggedAssignmentResolution.current = false;
    logEmployeeEntry('employee_dashboard_entry', {});
  }, []);

  // Magic-link auto-claim: consume ?token= on first render (once per mount).
  useEffect(() => {
    const token = searchParams.get('token');
    if (!token || tokenClaimAttempted.current) return;
    tokenClaimAttempted.current = true;

    // Pre-fill the assignment_id field from ?assignment_id= while the token resolves
    const urlAssignmentId = searchParams.get('assignment_id');
    if (urlAssignmentId) setClaimId(urlAssignmentId);

    setTokenClaimInProgress(true);
    setError('');

    employeeAPI.claimByToken(token)
      .then(async (res) => {
        const targetId = res.assignmentId;
        await refetchAssignment();
        if (targetId) {
          navigate(`/employee/case/${targetId}/summary`, { replace: true });
        }
      })
      .catch((err: unknown) => {
        setError(getApiErrorMessage(err, 'Could not link your case from the invite link. Enter your details below.'));
      })
      .finally(() => {
        setTokenClaimInProgress(false);
        // Remove the token from the URL to avoid re-triggering on refresh
        const next = new URLSearchParams(searchParams);
        next.delete('token');
        const qs = next.toString();
        window.history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Pre-fill ?assignment_id= (no token present — HR sent a plain link with the case code)
  useEffect(() => {
    const urlAssignmentId = searchParams.get('assignment_id');
    if (urlAssignmentId && !claimId) setClaimId(urlAssignmentId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (assignmentLoading) {
      loggedAssignmentResolution.current = false;
      return;
    }
    if (loggedAssignmentResolution.current) return;
    loggedAssignmentResolution.current = true;
    const t0 = entryStartedAt.current;
    const scenario = overviewError
      ? 'overview_error'
      : hasLinked
        ? 'linked'
        : hasPendingOnly
          ? 'pending_only'
          : 'manual_fallback';
    logEmployeeEntry('assignment_resolution_complete', {
      msSinceEntry: t0 != null ? Math.round(performance.now() - t0) : undefined,
      hasLinkedAssignment: hasLinked,
      linkedCount,
      pendingCount,
      skippedManualAssignmentIdPage: hasLinked || hasPendingOnly,
      scenario,
    });
    trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.hubResolution, {
      scenario,
      linkedCount,
      pendingCount,
      skippedManualAssignmentIdPage: hasLinked || hasPendingOnly,
      showPrimaryManualClaimPage,
      showPendingSection,
      msSinceEntry: t0 != null ? Math.round(performance.now() - t0) : undefined,
    });
  }, [
    assignmentLoading,
    assignmentId,
    hasLinked,
    hasPendingOnly,
    linkedCount,
    pendingCount,
    overviewError,
    showPrimaryManualClaimPage,
    showPendingSection,
  ]);

  const handleClaimPendingRow = async (pendingAssignmentId: string) => {
    const loginTrim = (getAuthItem('relopass_email') || getAuthItem('relopass_username') || '').trim();
    if (!loginTrim) {
      setError('Sign-in email or username is missing. Sign out and sign in again, then retry.');
      return;
    }
    setError('');
    setClaimingPendingId(pendingAssignmentId);
    trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.linkPendingAttempt, {
      assignmentId: pendingAssignmentId,
    });
    try {
      const res = await employeeAPI.linkPendingAssignment(pendingAssignmentId, loginTrim);
      const nextAssignment = res.assignmentId || pendingAssignmentId;
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.linkPendingComplete, {
        ok: true,
        assignmentId: nextAssignment,
        alreadyLinked: Boolean(res.alreadyLinked),
      });
      await refetchAssignment();
      navigate(`/employee/case/${nextAssignment}/summary`);
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      setError(transport ?? getApiErrorMessage(err, "We couldn't link this case. Check the code from HR and try again, or contact your HR team if the issue persists."));
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.linkPendingComplete, {
        ok: false,
        assignmentId: pendingAssignmentId,
        errorCode: getApiErrorCode(err),
        transportError: Boolean(transport),
      });
    } finally {
      setClaimingPendingId(null);
    }
  };

  const handleManualClaimSubmit = async () => {
    if (!claimId.trim() || !claimEmail.trim()) {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimClientValidationFailed, {
        reason: 'missing_fields',
      });
      setError('Fill in both fields: your login email on the left, and the case code from HR on the right.');
      return;
    }
    const idTrim = claimId.trim();
    const loginTrim = claimEmail.trim();
    if (ASSIGNMENT_ID_PATTERN.test(loginTrim) && !ASSIGNMENT_ID_PATTERN.test(idTrim)) {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimClientValidationFailed, {
        reason: 'assignment_id_in_login_field',
      });
      setError(
        'That case code goes in the second field. Put your ReloPass email or username on the left, and the case code from HR on the right.'
      );
      return;
    }
    if (idTrim.includes('@')) {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimClientValidationFailed, {
        reason: 'email_in_assignment_field',
      });
      setError(
        'That looks like an email address — paste the case code from HR instead. It looks like abc-123-….'
      );
      return;
    }
    setError('');
    setIsClaiming(true);
    trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimAttempt, {
      assignmentId: idTrim,
    });
    try {
      const res = await employeeAPI.claimAssignment(idTrim, loginTrim);
      const nextAssignment = res.assignmentId || idTrim;
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimComplete, {
        ok: true,
        assignmentId: nextAssignment,
      });
      await refetchAssignment();
      navigate(`/employee/case/${nextAssignment}/summary`);
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      if (transport) {
        setError(transport);
      } else {
        const code = getApiErrorCode(err);
        const perModeMessages: Record<string, string> = {
          CLAIM_ACCOUNT_IDENTIFIER_MISMATCH:
            "Your email doesn't match what HR registered. Try the email on your offer letter, or ask HR to update it.",
          CLAIM_PENDING_CONTACT_MISMATCH:
            "Your email doesn't match what HR registered. Try the email on your offer letter, or ask HR to update it.",
          CLAIM_ASSIGNMENT_ALREADY_CLAIMED:
            'This case code is already claimed by another account. If that wasn\'t you, contact your HR team.',
          CLAIM_ASSIGNMENT_NOT_PENDING:
            'This case code is already claimed by another account. If that wasn\'t you, contact your HR team.',
          CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH:
            'We couldn\'t find that case code. Double-check the email from HR — codes look like `abc-123-…`.',
          CLAIM_MISSING_REQUEST_IDENTIFIER:
            'We couldn\'t find that case code. Double-check the email from HR — codes look like `abc-123-…`.',
        };
        const friendlyMessage = (code && perModeMessages[code])
          ?? getApiErrorMessage(err, 'Something went wrong linking your case. Please try again or contact HR.');
        setError(friendlyMessage);
      }
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimComplete, {
        ok: false,
        assignmentId: idTrim,
        errorCode: getApiErrorCode(err),
        transportError: Boolean(transport),
      });
    } finally {
      setIsClaiming(false);
    }
  };



  const linkAlerts = useMemo(() => {
    if (!linkRec) return null;
    const blocks: React.ReactNode[] = [];
    if (linkRec.headline?.trim() || linkRec.message?.trim()) {
      blocks.push(
        <Alert key="primary" variant="success" className="mb-4" title={linkRec.headline?.trim() || undefined}>
          {linkRec.message?.trim() ? formatRichMessage(linkRec.message) : null}
        </Alert>
      );
    } else if (linkRec.attachedAssignmentIds && linkRec.attachedAssignmentIds.length > 0) {
      blocks.push(
        <Alert key="attached" variant="success" className="mb-4" title="Case linked">
          {linkRec.attachedAssignmentIds.length} assignment
          {linkRec.attachedAssignmentIds.length > 1 ? 's' : ''} linked to this account. Open it below or refresh.
        </Alert>
      );
    } else if (
      linkRec.linkedContactIds &&
      linkRec.linkedContactIds.length > 0 &&
      !(linkRec.attachedAssignmentIds && linkRec.attachedAssignmentIds.length)
    ) {
      blocks.push(
        <Alert key="profile" variant="info" className="mb-4" title="Contact matched">
          Your login matches a company contact. New assignments from HR should show here after refresh or the next sign-in.
        </Alert>
      );
    }
    if ((linkRec.skippedRevokedInvites ?? 0) > 0) {
      blocks.push(
        <Alert key="revoked" variant="warning" className="mb-4" title="Invitation no longer active">
          At least one pending invitation was cancelled by HR. If you still need access, contact your HR contact.
        </Alert>
      );
    }
    if (
      (linkRec.skippedContactsLinkedToOtherUser ?? 0) > 0 ||
      (linkRec.skippedAssignmentsLinkedToOtherUser ?? 0) > 0
    ) {
      blocks.push(
        <Alert key="ambiguous" variant="warning" className="mb-4" title="Could not link automatically">
          Another account may already own this case. Send HR your work email and the case code to confirm
          the correct login.
        </Alert>
      );
    }
    return blocks.length ? <div className="mb-6">{blocks}</div> : null;
  }, [linkRec]);

  const linkStatusBadge = useMemo(() => {
    if (hasLinked) {
      return (
        <Badge variant="success" size="sm">
          {linkedCount === 1 ? 'Linked to you: 1 case' : `Linked to you: ${linkedCount} cases`}
        </Badge>
      );
    }
    if (hasPendingOnly) {
      return (
        <Badge variant="info" size="sm">
          {pendingCount === 1 ? 'Pending assignment to link' : `${pendingCount} pending assignments to link`}
        </Badge>
      );
    }
    if (linkRec?.linkedContactIds?.length && !(linkRec.attachedAssignmentIds && linkRec.attachedAssignmentIds.length)) {
      return (
        <Badge variant="info" size="sm">
          Connected: waiting for an assignment from HR
        </Badge>
      );
    }
    return (
      <Badge variant="neutral" size="sm">
        No case linked yet: use email HR entered or claim below
      </Badge>
    );
  }, [linkRec, hasLinked, hasPendingOnly, linkedCount, pendingCount]);

  const shellTitle = assignmentLoading
    ? 'Welcome'
    : hasLinked
      ? 'My assignments'
      : hasPendingOnly
        ? 'Pending assignments'
        : 'Your relocation';
  const shellSubtitle = assignmentLoading
    ? 'Loading your assignment list.'
    : hasLinked
      ? 'Open a case or pick up where you left off.'
      : hasPendingOnly
        ? 'Accept your pending case below, then open it to get started.'
        : 'Enter the case code from HR to link your case, or wait for HR to match your email.';

  return (
    <AppShell title={shellTitle} subtitle={shellSubtitle} wide>
      {linkAlerts}
      {tokenClaimInProgress ? (
        <EmployeeAssignmentBootstrapCard
          title="Linking your case…"
          detail="Following your invite link — just a moment."
        />
      ) : null}
      {!tokenClaimInProgress && assignmentLoading ? (
        <EmployeeAssignmentBootstrapCard title="Checking assignments…" detail="One moment." />
      ) : null}

      {!assignmentLoading && overviewError ? (
        <Alert variant="warning" className="mb-6" title="Could not load assignments">
          {overviewError}{' '}
          <Button variant="outline" className="ml-2 mt-2 sm:mt-0" onClick={() => void refetchAssignment()}>
            Try again
          </Button>
        </Alert>
      ) : null}

      {(!assignmentLoading || tokenClaimInProgress) && error ? <Alert variant="error" className="mb-6">{error}</Alert> : null}

      {!assignmentLoading && showNewAssignmentBanner ? (
        <div className="mb-6 border border-[#93c5fd] bg-[#eff6ff] rounded-lg p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="min-w-0">
            <div className="font-semibold text-[#0b2b43]">New assignment for your email</div>
            <p className="text-sm text-[#334155] mt-1">
              Accept it below when you're ready. Your existing case is unchanged.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <Button onClick={scrollToPendingSection}>Review and link</Button>
            <Button variant="outline" onClick={dismissNewAssignmentBanner}>
              Dismiss
            </Button>
          </div>
        </div>
      ) : null}

      {!assignmentLoading && showPrimaryManualClaimPage ? <EmployeeNoCaseOnboarding /> : null}

      {!assignmentLoading ? (
        <Card padding="lg" className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="text-lg font-semibold text-[#0b2b43]">Assignment status</div>
            {linkStatusBadge}
          </div>
          <p className="text-sm text-[#4b5563] mb-4">
            {hasLinked
              ? 'Your active cases are below. If HR sent you a separate code, use manual entry at the bottom.'
              : hasPendingOnly
                ? 'HR has set up a case for you. Accept it below to get started.'
                : 'Sign in with the email HR used for your move, or enter the case code HR sent you.'}
          </p>
          {linkedSummaries.length > 0 ? (
            <JourneySpine
              intakeStep={linkedSummaries[0].intake_step ?? 0}
              intakeTotalSteps={INTAKE_TOTAL_STEPS}
              onContinueIntake={() => navigate(`/employee/case/${linkedSummaries[0].assignment_id}/intake`)}
              onPreviewBenefits={() => navigate(buildRoute('employeeBenefitsComparison'))}
            />
          ) : null}
        </Card>
      ) : null}

      {!assignmentLoading ? (
        <Card
          id="employee-hub-linked-assignments"
          padding="lg"
          className="mb-6 border border-[#e2e8f0] scroll-mt-6"
        >
          <div className="text-lg font-semibold text-[#0b2b43] mb-1">Your active cases</div>
          <p className="text-sm text-[#64748b] mb-4">Cases linked to your account. Open one to continue.</p>
          {linkedSummaries.length === 0 ? (
            <p className="text-sm text-[#4b5563] py-2">No linked assignments yet.</p>
          ) : (
            <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
              {linkedSummaries.map((row) => {
                // Intake form progress is persisted per-assignment by the
                // wizard (POST /api/employee/assignments/{id}/intake-progress).
                // The wizard is the only writer of intake_step, so it's the
                // single source of truth — case.status is NOT a reliable
                // proxy because many statuses (`created`, `linked`, etc.)
                // sit between "fresh" and "submitted" without indicating
                // wizard progress either way.
                // Wizard is the single source of truth for the total (see intakeSteps.ts).
                // Do not trust the stored intake_total_steps — historical rows hold a stale 7.
                const totalSteps = INTAKE_TOTAL_STEPS;
                const currentStep = row.intake_step ?? 0;
                const intakeSubmitted = totalSteps > 0 && currentStep >= totalSteps;
                const intakeStarted = currentStep > 0 && !intakeSubmitted;
                return (
                  <li
                    key={row.assignment_id}
                    className="p-4 flex flex-col sm:flex-row sm:items-stretch sm:justify-between gap-4"
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="font-semibold text-[#0b2b43]">{row.company?.name || 'Company'}</div>
                      <div className="text-sm text-[#64748b]">{formatDestinationLabel(row.destination)}</div>
                      <div className="text-sm text-[#334155]">
                        <span className="text-[#64748b]">Status</span>{' '}
                        <span className="font-medium text-[#0b2b43]">{linkedStatusLabel(row)}</span>
                      </div>
                      {formatCaseReference(row) ? (
                        <div className="text-sm text-[#334155]">
                          <span className="text-[#64748b]">Reference</span>{' '}
                          <span className="font-mono font-medium text-[#0b2b43]">{formatCaseReference(row)}</span>
                        </div>
                      ) : null}
                      <div className="text-sm text-[#334155] flex flex-wrap items-center gap-2">
                        <span className="text-[#64748b]">Intake form</span>{' '}
                        {intakeSubmitted ? (
                          <Badge variant="success" size="sm">Submitted</Badge>
                        ) : intakeStarted ? (
                          <>
                            <Badge variant="info" size="sm">
                              {currentStep} / {totalSteps} steps
                            </Badge>
                            <Link
                              to={`/employee/case/${row.assignment_id}/intake`}
                              className="text-[#2563eb] underline underline-offset-2 font-medium hover:text-[#1d4ed8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563eb] rounded-sm"
                            >
                              Continue
                            </Link>
                          </>
                        ) : (
                          <>
                            <Badge variant="warning" size="sm">Not started</Badge>
                            <Link
                              to={`/employee/case/${row.assignment_id}/intake`}
                              className="text-[#2563eb] underline underline-offset-2 font-medium hover:text-[#1d4ed8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563eb] rounded-sm"
                            >
                              Start
                            </Link>
                          </>
                        )}
                      </div>
                      <div className="text-sm text-[#334155]">
                        <span className="text-[#64748b]">Last updated</span>{' '}
                        <span className="font-medium text-[#0b2b43]">
                          {formatOverviewDate(row.updated_at || row.created_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex sm:flex-col sm:justify-center shrink-0">
                      <Button onClick={() => navigate(openCaseHref(row.assignment_id, row.status))}>Open case</Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      ) : null}

      {!assignmentLoading && showPendingSection ? (
        <Card
          id="employee-hub-pending-assignments"
          padding="lg"
          className="mb-6 border border-[#93c5fd] bg-[#f8fafc] scroll-mt-6"
        >
          <div className="text-lg font-semibold text-[#0b2b43] mb-1">Cases waiting to be accepted</div>
          <p className="text-sm text-[#4b5563] mb-4">
            HR has started a relocation for you. Click below to accept it and begin your intake.
          </p>
          <ul className="space-y-4">
            {pendingSummaries.map((row) => {
              const st = row.claim?.state || '';
              const blocked = st === 'invite_revoked' || row.claim?.extra_verification_required;
              return (
                <li
                  key={row.assignment_id}
                  className="rounded-lg border border-[#e2e8f0] bg-white p-4 flex flex-col sm:flex-row sm:items-stretch sm:justify-between gap-4"
                >
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="w-fit">
                      <Badge variant="info" size="sm">
                        Pending
                      </Badge>
                    </div>
                    <div className="font-semibold text-[#0b2b43] pt-1">{row.company?.name || 'Company'}</div>
                    <div className="text-sm text-[#64748b]">{formatDestinationLabel(row.destination)}</div>
                    <div className="text-sm text-[#334155]">
                      <span className="text-[#64748b]">Created</span>{' '}
                      <span className="font-medium text-[#0b2b43]">{formatOverviewDate(row.created_at)}</span>
                    </div>
                    {formatCaseReference(row) ? (
                      <div className="text-sm text-[#334155]">
                        <span className="text-[#64748b]">Reference</span>{' '}
                        <span className="font-mono font-medium text-[#0b2b43]">{formatCaseReference(row)}</span>
                      </div>
                    ) : null}
                    {st ? (
                      <div className="text-xs text-[#94a3b8]">{claimStateLabel(st)}</div>
                    ) : null}
                  </div>
                  <div className="flex sm:flex-col sm:justify-center shrink-0">
                    {blocked ? (
                      <p className="text-sm text-[#b45309] max-w-xs">
                        Needs HR follow-up. Use the form below if you have the case code from HR.
                      </p>
                    ) : (
                      <LoadingButton
                        onClick={() => void handleClaimPendingRow(row.assignment_id)}
                        loading={claimingPendingId === row.assignment_id}
                        loadingLabel="Accepting…"
                      >
                        Accept relocation
                      </LoadingButton>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}

      {!assignmentLoading && showPrimaryManualClaimPage ? (
        <Card padding="lg" className="mb-6 border border-[#cbd5e1]">
          <div className="text-lg font-semibold text-[#0b2b43]">No relocation assigned yet</div>
          <p className="text-sm text-[#4b5563] mt-2">
            Ask your HR team to create your case. Once they do, it appears here automatically — no code needed.
          </p>
          <div className="mt-6 border-t border-[#e2e8f0] pt-5 text-base font-semibold text-[#0b2b43]">
            Already have a case code from HR?
          </div>
          <p className="text-sm text-[#4b5563] mt-1">
            Enter the email HR used and the code HR sent you.
          </p>
          <ManualClaimInstructions signedInPrincipal={signedInPrincipal} />
          <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              type="text"
              value={claimEmail}
              onChange={setClaimEmail}
              label="Step 1: Your ReloPass email or username"
              placeholder="Same as your login (e.g. you@company.com)"
              fullWidth
            />
            <Input
              value={claimId}
              onChange={setClaimId}
              label="Step 2: Case code from HR"
              placeholder="The code HR sent you — it looks like abc-123-…"
              fullWidth
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <LoadingButton onClick={() => void handleManualClaimSubmit()} loading={isClaiming} loadingLabel="Linking…">
              Link case
            </LoadingButton>
            <RefreshButton onClick={() => window.location.reload()} label="Refresh page" />
          </div>
        </Card>
      ) : null}

      {!assignmentLoading && showSecondaryManualClaimCard ? (
        <Card padding="lg" className="mb-6 border border-dashed border-[#cbd5e1] bg-[#fafbfc]">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            {showPendingSection ? (
              // An email-matched case is already shown above with a primary
              // "Accept relocation" button — the case-code path is a quiet
              // fallback here, not a competing primary action.
              <button
                type="button"
                onClick={() => setManualClaimExpanded((v) => !v)}
                className="text-sm font-medium text-[#2563eb] underline underline-offset-2 hover:text-[#1d4ed8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563eb] rounded-sm text-left"
              >
                {manualClaimExpanded ? 'Hide case-code form' : 'Have a case code instead? Enter it here.'}
              </button>
            ) : (
              <>
                <div>
                  <div className="text-lg font-semibold text-[#0b2b43]">Enter your case code manually</div>
                  <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
                    Use if your case didn't appear automatically or HR sent you a code directly.
                  </p>
                </div>
                {!manualClaimExpanded ? (
                  <Button variant="outline" className="shrink-0" onClick={() => setManualClaimExpanded(true)}>
                    Show form
                  </Button>
                ) : (
                  <Button variant="outline" className="shrink-0" onClick={() => setManualClaimExpanded(false)}>
                    Hide form
                  </Button>
                )}
              </>
            )}
          </div>
          {manualClaimExpanded ? (
            <div className="mt-6 border-t border-[#e2e8f0] pt-6">
              <ManualClaimInstructions signedInPrincipal={signedInPrincipal} />
              <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  type="text"
                  value={claimEmail}
                  onChange={setClaimEmail}
                  label="Step 1: Your ReloPass email or username"
                  placeholder="Same as your login (e.g. you@company.com)"
                  fullWidth
                />
                <Input
                  value={claimId}
                  onChange={setClaimId}
                  label="Step 2: Code from HR"
                  placeholder="The code HR sent you (long string of letters and numbers)"
                  fullWidth
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <LoadingButton onClick={() => void handleManualClaimSubmit()} loading={isClaiming} loadingLabel="Linking…">
                  Link case
                </LoadingButton>
                <RefreshButton onClick={() => void refetchAssignment()} label="Refresh assignments" />
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
    </AppShell>
  );
};
