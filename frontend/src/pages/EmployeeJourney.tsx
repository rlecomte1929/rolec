import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, Input, LoadingButton } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../utils/demo';
import type { PostSignupReconciliation } from '../types';
import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';
import { formatRichMessage } from '../utils/richMessage';
import { logEmployeeEntry } from '../utils/employeeJourneyPerf';
import { trackAssignmentFlow, ASSIGNMENT_FLOW_EVENTS } from '../perf/assignmentLinkingInstrumentation';
import { getApiErrorCode } from '../utils/apiDetail';

const FLOW_STEPS = [
  '1. Fill your case',
  '2. Choose services',
  '3. Review budget vs policy',
  '4. (Soon) Request quotes',
  '5. Exchange with HR',
];

/** Basic UUID shape — used to catch swapped claim fields. */
const ASSIGNMENT_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Dismissed pending-ID set per user (localStorage): when signature matches current pending rows, banner stays hidden. */
function pendingBannerStorageKey(): string {
  const uid = getAuthItem('relopass_user_id') || 'anon';
  return `relopass_employee_new_pending_banner_dismissed_${uid}`;
}

function formatOverviewDate(iso: string | null | undefined): string {
  if (!iso?.trim()) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function linkedStatusLabel(row: EmployeeLinkedOverviewRow): string {
  const parts = [row.status, row.current_stage].filter(Boolean);
  return parts.length ? parts.join(' · ') : '—';
}

function ManualClaimInstructions({ signedInPrincipal }: { signedInPrincipal: string | null }) {
  return (
    <div
      className="mt-4 rounded-lg border border-[#93c5fd] bg-[#eff6ff] px-4 py-3 text-sm text-[#1e3a5f]"
      role="region"
      aria-label="How to fill the claim form"
    >
      <div className="font-semibold text-[#0b2b43] mb-2">Follow these steps exactly</div>
      <ol className="list-decimal pl-5 space-y-2 text-[#334155]">
        <li>
          <strong className="text-[#0b2b43]">Left box — your login only:</strong> Type the{' '}
          <strong>same email address or username you use to sign in to ReloPass</strong> (what HR should have entered when
          they assigned you). This is <strong>not</strong> the assignment ID.
        </li>
        <li>
          <strong className="text-[#0b2b43]">Right box — assignment ID only:</strong> Paste the long code HR gave you
          (letters, numbers, and hyphens — often shown in ReloPass as &quot;Assignment ID&quot;). Example shape:{' '}
          <span className="font-mono text-xs text-[#0b2b43]">a631bfd2-aac5-4f54-96bd-e60082157246</span>.
        </li>
      </ol>
      {signedInPrincipal ? (
        <p className="mt-3 text-xs text-[#64748b] border-t border-[#bfdbfe] pt-3">
          You are signed in as <span className="font-medium text-[#0b2b43]">{signedInPrincipal}</span>. The left box should
          match this account (or your username, if you log in with a username instead of email).
        </p>
      ) : null}
      <p className="mt-2 text-xs text-[#64748b]">
        <strong className="text-[#92400e]">Common mistake:</strong> pasting the assignment ID into the login field, or your
        email into the assignment ID field — the button will not work until each value is in the correct box.
      </p>
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
  const [isClaiming, setIsClaiming] = useState(false);
  const [claimingPendingId, setClaimingPendingId] = useState<string | null>(null);
  const [linkRec, setLinkRec] = useState<PostSignupReconciliation | null>(null);
  /** Hub: collapsed manual UUID form unless user opens it (always expanded for primary fallback). */
  const [manualClaimExpanded, setManualClaimExpanded] = useState(false);
  const [bannerDismissNonce, setBannerDismissNonce] = useState(0);

  const hasLinked = linkedCount > 0;
  const hasPendingOnly = !hasLinked && pendingCount > 0;
  /** No linked and no auto-detected pending → full assignment-ID / manual claim experience. */
  const showPrimaryManualClaimPage = !hasLinked && !hasPendingOnly;
  const showPendingSection = pendingCount > 0;
  /** Secondary manual path: linked and/or pending hub — recovery & HR UUID without a parallel API. */
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

  const signedInPrincipal =
    (getAuthItem('relopass_email') || getAuthItem('relopass_username') || '').trim() || null;

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
      setError(transport ?? getApiErrorMessage(err, 'Unable to link this assignment.'));
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
      setError('Fill both fields: your login (left) and the assignment ID from HR (right).');
      return;
    }
    const idTrim = claimId.trim();
    const loginTrim = claimEmail.trim();
    if (ASSIGNMENT_ID_PATTERN.test(loginTrim) && !ASSIGNMENT_ID_PATTERN.test(idTrim)) {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimClientValidationFailed, {
        reason: 'assignment_id_in_login_field',
      });
      setError(
        'You pasted the assignment ID into the first field. Put the long ID (with dashes) in “Assignment ID” on the right, and your ReloPass email or username on the left.'
      );
      return;
    }
    if (idTrim.includes('@')) {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.manualClaimClientValidationFailed, {
        reason: 'email_in_assignment_field',
      });
      setError(
        'The assignment ID is not an email address — use the UUID from HR in the right field only.'
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
      setError(transport ?? getApiErrorMessage(err, 'Unable to claim assignment.'));
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

  const flowchart = useMemo(() => {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm text-[#0b2b43]">
        {FLOW_STEPS.map((step, idx) => (
          <div key={step} className="flex items-center gap-2">
            <div className="rounded-full border border-[#cbd5f5] bg-[#eef4f8] px-3 py-1 font-medium">{step}</div>
            {idx < FLOW_STEPS.length - 1 && <span className="text-[#94a3b8]">→</span>}
          </div>
        ))}
      </div>
    );
  }, []);


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
        <Alert key="attached" variant="success" className="mb-4" title="Relocation case linked">
          We linked {linkRec.attachedAssignmentIds.length} assignment
          {linkRec.attachedAssignmentIds.length > 1 ? 's' : ''} to your account. Open <strong>My case</strong> below
          when it appears, or tap Refresh.
        </Alert>
      );
    } else if (
      linkRec.linkedContactIds &&
      linkRec.linkedContactIds.length > 0 &&
      !(linkRec.attachedAssignmentIds && linkRec.attachedAssignmentIds.length)
    ) {
      blocks.push(
        <Alert key="profile" variant="info" className="mb-4" title="Profile connected">
          Your account is tied to your company contact. When HR assigns a relocation to you, it will show up here
          automatically after you refresh or sign in again.
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
        <Alert key="ambiguous" variant="warning" className="mb-4" title="Manual check may be needed">
          We could not attach everything automatically — another account may already be linked to the same contact
          record, or an assignment is owned by someone else. Contact HR with your work email and assignment ID so they
          can confirm the right account.
        </Alert>
      );
    }
    return blocks.length ? <div className="mb-6">{blocks}</div> : null;
  }, [linkRec]);

  const linkStatusBadge = useMemo(() => {
    if (hasLinked) {
      return (
        <Badge variant="success" size="sm">
          {linkedCount === 1 ? 'Linked — case on this account' : `Linked — ${linkedCount} assignments on this account`}
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
          Connected — waiting for an assignment from HR
        </Badge>
      );
    }
    return (
      <Badge variant="neutral" size="sm">
        No case linked yet — use email HR entered or claim below
      </Badge>
    );
  }, [linkRec, hasLinked, hasPendingOnly, linkedCount, pendingCount]);

  const shellTitle = assignmentLoading
    ? 'Welcome'
    : hasLinked
      ? 'My assignments'
      : hasPendingOnly
        ? 'Pending assignments'
        : 'Welcome';
  const shellSubtitle = assignmentLoading
    ? "Here's what happens next with your relocation case."
    : hasLinked
      ? 'Open a linked relocation or continue where you left off.'
      : hasPendingOnly
        ? 'Confirm each assignment in Section B to add it to your account — then open the case from Section A.'
        : "Here's what happens next with your relocation case.";

  return (
    <AppShell title={shellTitle} subtitle={shellSubtitle}>
      {linkAlerts}
      {assignmentLoading ? (
        <EmployeeAssignmentBootstrapCard
          title="Checking your assignments…"
          detail="Loading your case access. This usually takes a moment."
        />
      ) : null}

      {!assignmentLoading && overviewError ? (
        <Alert variant="warning" className="mb-6" title="Could not load assignment list">
          {overviewError}{' '}
          <Button variant="outline" className="ml-2 mt-2 sm:mt-0" onClick={() => void refetchAssignment()}>
            Try again
          </Button>
        </Alert>
      ) : null}

      {!assignmentLoading && error ? <Alert variant="error" className="mb-6">{error}</Alert> : null}

      {!assignmentLoading && showNewAssignmentBanner ? (
        <div className="mb-6 border border-[#93c5fd] bg-[#eff6ff] rounded-lg p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="min-w-0">
            <div className="font-semibold text-[#0b2b43]">A new assignment was found for your email</div>
            <p className="text-sm text-[#334155] mt-1">
              Link it in Section B when you are ready — your existing cases stay available in Section A. Nothing opens
              until you choose.
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

      {!assignmentLoading ? (
        <Card padding="lg" className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="text-lg font-semibold text-[#0b2b43]">Assignment status</div>
            {linkStatusBadge}
          </div>
          <p className="text-sm text-[#4b5563] mb-4">
            {hasLinked
              ? 'Assignments linked to your account appear in Section A. Pending work appears in Section B. If HR gave you a UUID and nothing matched automatically, use Enter assignment ID manually below.'
              : hasPendingOnly
                ? 'HR matched relocation work to your sign-in email. Section B lists work that still needs linking before you can open the case.'
                : 'HR can create your case before you register. After you sign in with the same email or username HR used, assignments usually appear automatically. If nothing appears, use manual assignment ID entry below — same secure claim as when HR auto-matches your email.'}
          </p>
          <div className="text-lg font-semibold text-[#0b2b43] mb-2">Your relocation flow</div>
          {flowchart}
        </Card>
      ) : null}

      {!assignmentLoading ? (
        <Card
          id="employee-hub-linked-assignments"
          padding="lg"
          className="mb-6 border border-[#e2e8f0] scroll-mt-6"
        >
          <div className="text-lg font-semibold text-[#0b2b43] mb-1">Section A — Linked assignments</div>
          <p className="text-sm text-[#64748b] mb-4">
            Already attached to your ReloPass account. Full case details load only when you open a row.
          </p>
          {linkedSummaries.length === 0 ? (
            <p className="text-sm text-[#4b5563] py-2">No linked assignments yet.</p>
          ) : (
            <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
              {linkedSummaries.map((row) => (
                <li
                  key={row.assignment_id}
                  className="p-4 flex flex-col sm:flex-row sm:items-stretch sm:justify-between gap-4"
                >
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="font-semibold text-[#0b2b43]">{row.company?.name || 'Company'}</div>
                    <div className="text-sm text-[#64748b]">{row.destination?.label || 'Destination TBD'}</div>
                    <div className="text-sm text-[#334155]">
                      <span className="text-[#64748b]">Status</span>{' '}
                      <span className="font-medium text-[#0b2b43]">{linkedStatusLabel(row)}</span>
                    </div>
                    <div className="text-sm text-[#334155]">
                      <span className="text-[#64748b]">Last updated</span>{' '}
                      <span className="font-medium text-[#0b2b43]">
                        {formatOverviewDate(row.updated_at || row.created_at)}
                      </span>
                    </div>
                    <div className="text-xs font-mono text-[#94a3b8] pt-1">{row.assignment_id}</div>
                  </div>
                  <div className="flex sm:flex-col sm:justify-center shrink-0">
                    <Button onClick={() => navigate(`/employee/case/${row.assignment_id}/summary`)}>Open case</Button>
                  </div>
                </li>
              ))}
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
          <div className="text-lg font-semibold text-[#0b2b43] mb-1">Section B — Pending assignments to link</div>
          <p className="text-sm text-[#4b5563] mb-4">
            HR created these against your contact, but they are not on your account until you link them. Nothing opens
            until you choose an action — we never pick a case for you.
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
                        New assignment found
                      </Badge>
                    </div>
                    <div className="font-semibold text-[#0b2b43] pt-1">{row.company?.name || 'Company'}</div>
                    <div className="text-sm text-[#64748b]">{row.destination?.label || 'Destination TBD'}</div>
                    <div className="text-sm text-[#334155]">
                      <span className="text-[#64748b]">Created</span>{' '}
                      <span className="font-medium text-[#0b2b43]">{formatOverviewDate(row.created_at)}</span>
                    </div>
                    {st ? (
                      <div className="text-xs text-[#94a3b8]">Claim state: {st}</div>
                    ) : null}
                    <div className="text-xs font-mono text-[#cbd5e1]">{row.assignment_id}</div>
                  </div>
                  <div className="flex sm:flex-col sm:justify-center shrink-0">
                    {blocked ? (
                      <p className="text-sm text-[#b45309] max-w-xs">
                        HR verification may be required — contact your HR contact or use manual assignment ID entry below
                        if they gave you a UUID.
                      </p>
                    ) : (
                      <LoadingButton
                        onClick={() => void handleClaimPendingRow(row.assignment_id)}
                        loading={claimingPendingId === row.assignment_id}
                        loadingLabel="Linking…"
                      >
                        Link assignment
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
          <div className="text-lg font-semibold text-[#0b2b43]">Link your case manually (assignment ID)</div>
          <p className="text-sm text-[#4b5563] mt-2">
            No assignments were auto-detected for your sign-in. Enter the UUID HR gave you. This uses the same{' '}
            <strong>claim</strong> service as every other link path — we locate the assignment, validate you may claim it,
            then attach it safely.
          </p>
          <ManualClaimInstructions signedInPrincipal={signedInPrincipal} />
          <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              type="text"
              value={claimEmail}
              onChange={setClaimEmail}
              label="Step 1 — Your ReloPass email or username"
              placeholder="Same as your login (e.g. you@company.com)"
              fullWidth
            />
            <Input
              value={claimId}
              onChange={setClaimId}
              label="Step 2 — Assignment ID from HR (UUID)"
              placeholder="Paste only the ID from HR, not your email"
              fullWidth
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <LoadingButton onClick={() => void handleManualClaimSubmit()} loading={isClaiming} loadingLabel="Linking your case…">
              Link this case to my account
            </LoadingButton>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Refresh page
            </Button>
          </div>
        </Card>
      ) : null}

      {!assignmentLoading && showSecondaryManualClaimCard ? (
        <Card padding="lg" className="mb-6 border border-dashed border-[#cbd5e1] bg-[#fafbfc]">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div>
              <div className="text-lg font-semibold text-[#0b2b43]">Enter assignment ID manually</div>
              <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
                Fallback if email matching missed a case or HR only shared a UUID. Uses the same{' '}
                <strong>manual claim</strong> endpoint as the primary assignment-ID path — not the pending-only link
                action in Section B.
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
          </div>
          {manualClaimExpanded ? (
            <div className="mt-6 border-t border-[#e2e8f0] pt-6">
              <ManualClaimInstructions signedInPrincipal={signedInPrincipal} />
              <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  type="text"
                  value={claimEmail}
                  onChange={setClaimEmail}
                  label="Step 1 — Your ReloPass email or username"
                  placeholder="Same as your login (e.g. you@company.com)"
                  fullWidth
                />
                <Input
                  value={claimId}
                  onChange={setClaimId}
                  label="Step 2 — Assignment ID from HR (UUID)"
                  placeholder="Paste only the ID from HR, not your email"
                  fullWidth
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <LoadingButton onClick={() => void handleManualClaimSubmit()} loading={isClaiming} loadingLabel="Linking your case…">
                  Link this case to my account
                </LoadingButton>
                <Button variant="outline" onClick={() => void refetchAssignment()}>
                  Refresh assignments
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
    </AppShell>
  );
};
