import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { buildRoute } from '../navigation/routes';
import { Alert, Badge, Button, Card, Input, LoadingButton } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { getCaseDetailsByAssignmentId } from '../api/caseDetails';
import { getRelocationCase } from '../api/relocation';
import { safeNavigate } from '../navigation/safeNavigate';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../utils/demo';
import type { PostSignupReconciliation } from '../types';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';
import { formatRichMessage } from '../utils/richMessage';

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

export const EmployeeJourney: React.FC = () => {
  const navigate = useNavigate();
  const { assignmentId, isLoading: assignmentLoading, refetch: refetchAssignment } = useEmployeeAssignment();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [missingCount, setMissingCount] = useState<number | null>(null);
  const [servicesSelected, setServicesSelected] = useState<number | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<string | null>(null);
  const [budgetComputed, setBudgetComputed] = useState(false);
  const [error, setError] = useState('');
  const [claimId, setClaimId] = useState('');
  const [claimEmail, setClaimEmail] = useState(
    getAuthItem('relopass_email') || getAuthItem('relopass_username') || ''
  );
  const [isClaiming, setIsClaiming] = useState(false);
  const [linkRec, setLinkRec] = useState<PostSignupReconciliation | null>(null);
  const [caseStatsLoading, setCaseStatsLoading] = useState(false);

  const caseInitiated = Boolean(assignmentId && caseId);
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
    if (assignmentLoading) return;
    if (!assignmentId) {
      setCaseId(null);
      setMissingCount(null);
      setServicesSelected(null);
      setBudgetStatus(null);
      setBudgetComputed(false);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setCaseStatsLoading(true);
      try {
        const [caseDetails, serviceRes, policyRes] = await Promise.all([
          getCaseDetailsByAssignmentId(assignmentId),
          employeeAPI.getAssignmentServices(assignmentId),
          employeeAPI.getPolicyBudget(assignmentId).catch(() => null),
        ]);
        if (cancelled) return;
        const cid = caseDetails.data?.case?.id || null;
        setCaseId(cid);
        const selected = (serviceRes.services || []).filter((svc) => Boolean(svc.selected)).length;
        setServicesSelected(selected);

        const relo = cid ? await getRelocationCase(cid).catch(() => null) : null;
        if (cancelled) return;
        setMissingCount(relo ? (relo.missing_fields?.length ?? 0) : null);

        try {
          if (!policyRes) {
            setBudgetStatus(null);
            setBudgetComputed(false);
          } else {
            const caps = policyRes?.caps || {};
            const totals: Record<string, number> = {};
            serviceRes.services?.forEach((svc) => {
              if (!svc.selected) return;
              if (svc.estimated_cost === null || svc.estimated_cost === undefined) return;
              totals[svc.category] = (totals[svc.category] || 0) + Number(svc.estimated_cost);
            });
            let exceeding = false;
            Object.entries(totals).forEach(([category, total]) => {
              const cap = caps[category];
              if (cap !== undefined && total > cap) exceeding = true;
            });
            if (Object.keys(caps).length === 0) {
              setBudgetStatus('Policy not provided');
            } else {
              setBudgetStatus(exceeding ? 'Exceeding policy' : 'Within policy');
            }
            setBudgetComputed(true);
          }
        } catch {
          setBudgetStatus(null);
          setBudgetComputed(false);
        }
      } catch (err: unknown) {
        if (cancelled) return;
        const ax = err as { response?: { status?: number } };
        if (ax?.response?.status === 401) {
          safeNavigate(navigate, 'landing');
          return;
        }
        setError("Couldn't load your case. Refresh to try again.");
      } finally {
        if (!cancelled) setCaseStatsLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [assignmentId, assignmentLoading, navigate]);

  const handlePrimaryCta = async () => {
    if (assignmentId) {
      navigate(`/employee/case/${assignmentId}/wizard/1`);
      return;
    }
    if (!claimId.trim() || !claimEmail.trim()) {
      setError('Fill both fields: your login (left) and the assignment ID from HR (right).');
      return;
    }
    const idTrim = claimId.trim();
    const loginTrim = claimEmail.trim();
    if (ASSIGNMENT_ID_PATTERN.test(loginTrim) && !ASSIGNMENT_ID_PATTERN.test(idTrim)) {
      setError(
        'You pasted the assignment ID into the first field. Put the long ID (with dashes) in “Assignment ID” on the right, and your ReloPass email or username on the left.'
      );
      return;
    }
    if (idTrim.includes('@')) {
      setError(
        'The assignment ID is not an email address — use the UUID from HR in the right field only.'
      );
      return;
    }
    setError('');
    setIsClaiming(true);
    try {
      const res = await employeeAPI.claimAssignment(idTrim, loginTrim);
      const nextAssignment = res.assignmentId || idTrim;
      await refetchAssignment();
      navigate(`/employee/case/${nextAssignment}/wizard/1`);
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      setError(transport ?? getApiErrorMessage(err, 'Unable to claim assignment.'));
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
    if (assignmentId) {
      return (
        <Badge variant="success" size="sm">
          Linked — case on this account
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
  }, [assignmentId, linkRec]);

  return (
    <AppShell title="Welcome" subtitle="Here's what happens next with your relocation case.">
      {linkAlerts}
      {error && <Alert variant="error" className="mb-6">{error}</Alert>}

      <Card padding="lg" className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="text-lg font-semibold text-[#0b2b43]">Case link status</div>
          {linkStatusBadge}
        </div>
        <p className="text-sm text-[#4b5563] mb-4">
          HR can create your case before you register. After you <strong>sign up</strong> or <strong>sign in</strong>{' '}
          with the <strong>same email or username HR typed</strong> when they created the assignment, your case usually
          appears automatically. If the status above still says no case, use <strong>Refresh</strong> or manual claim
          below.
        </p>
        <div className="text-lg font-semibold text-[#0b2b43] mb-2">Your relocation flow</div>
        {flowchart}
      </Card>

      {assignmentId && (
        <Card padding="lg" className="mb-6 border border-[#0b2b43]/15 bg-[#f8fafc]">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="text-lg font-semibold text-[#0b2b43]">Your case is on this account</div>
              <p className="text-sm text-[#4b5563] mt-1">
                Continue intake in the wizard, or use <strong>My case</strong> in the top menu anytime. You do{' '}
                <strong>not</strong> need to claim again if this message is showing.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 shrink-0">
              <Button onClick={() => navigate(`/employee/case/${assignmentId}/wizard/1`)}>Continue to my case</Button>
              <Button variant="outline" onClick={() => void refetchAssignment()}>
                Refresh link status
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!assignmentId && (
        <Card padding="lg" className="mb-6">
          <div className="text-lg font-semibold text-[#0b2b43]">Link your case manually</div>
          <p className="text-sm text-[#4b5563] mt-2">
            Use this only if your case did not appear after sign-in. You need <strong>two different pieces of information</strong>:
            your ReloPass login (who you are) and the assignment ID (which case HR created).
          </p>

          <div
            className="mt-4 rounded-lg border border-[#93c5fd] bg-[#eff6ff] px-4 py-3 text-sm text-[#1e3a5f]"
            role="region"
            aria-label="How to fill the claim form"
          >
            <div className="font-semibold text-[#0b2b43] mb-2">Follow these steps exactly</div>
            <ol className="list-decimal pl-5 space-y-2 text-[#334155]">
              <li>
                <strong className="text-[#0b2b43]">Left box — your login only:</strong> Type the{' '}
                <strong>same email address or username you use to sign in to ReloPass</strong> (what HR should have
                entered when they assigned you). This is <strong>not</strong> the assignment ID.
              </li>
              <li>
                <strong className="text-[#0b2b43]">Right box — assignment ID only:</strong> Paste the long code HR gave
                you (letters, numbers, and hyphens — often shown in ReloPass as &quot;Assignment ID&quot;). Example shape:{' '}
                <span className="font-mono text-xs text-[#0b2b43]">a631bfd2-aac5-4f54-96bd-e60082157246</span>.
              </li>
            </ol>
            {signedInPrincipal ? (
              <p className="mt-3 text-xs text-[#64748b] border-t border-[#bfdbfe] pt-3">
                You are signed in as{' '}
                <span className="font-medium text-[#0b2b43]">{signedInPrincipal}</span>. The left box should match this
                account (or your username, if you log in with a username instead of email).
              </p>
            ) : null}
            <p className="mt-2 text-xs text-[#64748b]">
              <strong className="text-[#92400e]">Common mistake:</strong> pasting the assignment ID into the login field,
              or your email into the assignment ID field — the button will not work until each value is in the correct box.
            </p>
          </div>

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
            <LoadingButton onClick={handlePrimaryCta} loading={isClaiming} loadingLabel="Linking your case…">
              Link this case to my account
            </LoadingButton>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Refresh page
            </Button>
          </div>
        </Card>
      )}

      {assignmentId && caseStatsLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6" aria-busy="true">
          {[1, 2, 3].map((k) => (
            <Card key={k} padding="lg" className="animate-pulse">
              <div className="h-3 w-24 bg-[#e2e8f0] rounded mb-3" />
              <div className="h-8 w-16 bg-[#e2e8f0] rounded mb-2" />
              <div className="h-3 w-full bg-[#e2e8f0] rounded" />
            </Card>
          ))}
        </div>
      )}

      {assignmentId && !caseStatsLoading && caseInitiated && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <Card padding="lg">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Case completeness</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
              {missingCount === null ? 'Coming soon' : missingCount === 0 ? 'Complete' : `${missingCount} missing`}
            </div>
            <div className="text-sm text-[#6b7280] mt-2">
              Complete your case to unlock tailored services.
            </div>
          </Card>
          <Card padding="lg">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Services selected</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
              {servicesSelected === null ? 'Coming soon' : String(servicesSelected)}
            </div>
            <div className="text-sm text-[#6b7280] mt-2">
              Add or edit services anytime.
            </div>
          </Card>
          <Card padding="lg">
            <div className="text-xs uppercase tracking-wide text-[#6b7280]">Budget status</div>
            <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
              {!budgetComputed ? 'Coming soon' : (budgetStatus ?? '—')}
            </div>
            <div className="text-sm text-[#6b7280] mt-2">
              Compared to your company&apos;s published policy.{' '}
              <Link to={buildRoute('hrPolicy')} className="text-[#0b2b43] hover:underline">Assignment Package &amp; Limits</Link>
            </div>
          </Card>
        </div>
      )}

      {assignmentId && caseId && (
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">
            Case ID: <span className="font-semibold text-[#0b2b43]">{caseId}</span>
          </div>
        </Card>
      )}
    </AppShell>
  );
};
