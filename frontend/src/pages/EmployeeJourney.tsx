import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card, Input, LoadingButton } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { getCaseDetailsByAssignmentId } from '../api/caseDetails';
import { getRelocationCase } from '../api/relocation';
import { safeNavigate } from '../navigation/safeNavigate';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../utils/demo';

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

  const caseInitiated = Boolean(assignmentId && caseId);

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
        setError('We could not load your case summary yet. Please refresh to retry.');
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
      setError('Enter your email or username and the assignment ID provided by HR.');
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
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'Unable to claim assignment.');
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


  return (
    <AppShell title="Welcome" subtitle="Here's what happens next with your relocation case.">
      {error && <Alert variant="error" className="mb-6">{error}</Alert>}

      <Card padding="lg" className="mb-6">
        <div className="text-lg font-semibold text-[#0b2b43] mb-2">Your relocation flow</div>
        {flowchart}
      </Card>

      {!assignmentId && (
        <Card padding="lg" className="mb-6">
          <div className="text-lg font-semibold text-[#0b2b43]">No case assigned yet</div>
          <div className="text-sm text-[#4b5563] mt-2">
            If HR has shared an assignment ID, enter it below to start your case.
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
              Compare selected services against policy caps.
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
