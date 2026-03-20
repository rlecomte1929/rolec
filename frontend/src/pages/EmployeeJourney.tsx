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
import { getApiErrorMessage } from '../utils/apiDetail';
import { formatRichMessage } from '../utils/richMessage';

const FLOW_STEPS = [
  '1. Fill your case',
  '2. Choose services',
  '3. Review budget vs policy',
  '4. (Soon) Request quotes',
  '5. Exchange with HR',
];

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

  const caseInitiated = Boolean(assignmentId && caseId);

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
    const load = async () => {
      try {
        const caseDetails = await getCaseDetailsByAssignmentId(assignmentId);
        const cid = caseDetails.data?.case?.id || null;
        setCaseId(cid);
        if (cid) {
          try {
            const relocation = await getRelocationCase(cid);
            setMissingCount(relocation.missing_fields?.length ?? 0);
          } catch {
            setMissingCount(null);
          }
        }
        const serviceRes = await employeeAPI.getAssignmentServices(assignmentId);
        const selected = (serviceRes.services || []).filter((svc) => Boolean(svc.selected)).length;
        setServicesSelected(selected);
        try {
          const policyRes = await employeeAPI.getPolicyBudget(assignmentId);
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
        } catch {
          setBudgetStatus(null);
          setBudgetComputed(false);
        }
      } catch (err: unknown) {
        const ax = err as { response?: { status?: number } };
        if (ax?.response?.status === 401) {
          safeNavigate(navigate, 'landing');
          return;
        }
        setError("Couldn't load your case. Refresh to try again.");
      }
    };
    load();
  }, [assignmentId, assignmentLoading, navigate]);

  const handlePrimaryCta = async () => {
    if (assignmentId) {
      navigate(`/employee/case/${assignmentId}/wizard/1`);
      return;
    }
    if (!claimId.trim() || !claimEmail.trim()) {
      setError('Use the email or username and assignment ID provided by HR.');
      return;
    }
    setError('');
    setIsClaiming(true);
    try {
      const res = await employeeAPI.claimAssignment(claimId.trim(), claimEmail.trim());
      const nextAssignment = res.assignmentId || claimId.trim();
      await refetchAssignment();
      navigate(`/employee/case/${nextAssignment}/wizard/1`);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Unable to claim assignment.'));
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
          with the same email or username HR used, pending cases usually attach automatically. If nothing appears, use the
          assignment ID HR sent you.
        </p>
        <div className="text-lg font-semibold text-[#0b2b43] mb-2">Your relocation flow</div>
        {flowchart}
      </Card>

      {!assignmentId && (
        <Card padding="lg" className="mb-6">
          <div className="text-lg font-semibold text-[#0b2b43]">No case on this dashboard yet</div>
          <div className="text-sm text-[#4b5563] mt-2 space-y-2">
            <p>
              <strong>Most common:</strong> sign in with the <strong>exact email or username</strong> your HR team
              entered on the assignment. If you just created your account, try <strong>Refresh</strong> — linking runs
              when you open this page.
            </p>
            <p>
              <strong>Already using the right login?</strong> Ask HR for the <strong>assignment ID</strong> and enter it
              below with the same email/username you use here (manual claim).
            </p>
          </div>
          <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              type="text"
              value={claimEmail}
              onChange={setClaimEmail}
              label="Email or username"
              placeholder="you@example.com or your_username"
              fullWidth
            />
            <Input
              value={claimId}
              onChange={setClaimId}
              label="Assignment ID"
              placeholder="Paste the assignment ID from HR"
              fullWidth
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <LoadingButton onClick={handlePrimaryCta} loading={isClaiming} loadingLabel="Starting…">
              Start
            </LoadingButton>
            <Button variant="outline" onClick={() => window.location.reload()}>Refresh</Button>
          </div>
        </Card>
      )}

      {caseInitiated && (
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
