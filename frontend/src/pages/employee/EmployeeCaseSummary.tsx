/**
 * Employee Case Summary — intake snapshot: instructions, then profile/relocation basics (read-only).
 * Relocation tasks → Relocation plan tab. Policy Q&A → HR Policy (FAB). Policy Assistant removed from here.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Card, LoadingButton } from '../../components/antigravity';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { getAuthItem } from '../../utils/demo';
import { AssignmentDebugPanel } from '../AssignmentDebugPanel';
import type { CaseDTO, CaseDraftDTO } from '../../types';
import { buildRoute } from '../../navigation/routes';

function SummarySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card padding="md" className="mb-4">
      <div className="text-sm font-semibold text-[#0b2b43] mb-2">{title}</div>
      <div className="text-sm text-[#4b5563] space-y-1">{children}</div>
    </Card>
  );
}

function buildDefaultDraft(): CaseDraftDTO {
  const name = getAuthItem('relopass_name');
  const email = getAuthItem('relopass_email');
  const username = getAuthItem('relopass_username');
  const emailOrUsername = email || (username?.includes('@') ? username : undefined);
  return {
    relocationBasics: {},
    employeeProfile: {
      ...(name && { fullName: name }),
      ...(emailOrUsername && { email: emailOrUsername }),
    },
    familyMembers: {},
    assignmentContext: {},
  };
}

function caseToWizardDraft(caseData: CaseDTO | null): CaseDraftDTO {
  const base = buildDefaultDraft();
  if (!caseData) return base;

  const legacyBasics = {
    originCountry: caseData.originCountry,
    originCity: caseData.originCity,
    destCountry: caseData.destCountry,
    destCity: caseData.destCity,
    purpose: caseData.purpose,
    targetMoveDate: caseData.targetMoveDate,
  };

  return {
    relocationBasics: {
      ...base.relocationBasics,
      ...legacyBasics,
      ...(caseData.draft?.relocationBasics || {}),
    },
    employeeProfile: {
      ...base.employeeProfile,
      ...(caseData.draft?.employeeProfile || {}),
    },
    familyMembers: {
      ...base.familyMembers,
      ...(caseData.draft?.familyMembers || {}),
    },
    assignmentContext: {
      ...base.assignmentContext,
      ...(caseData.draft?.assignmentContext || {}),
    },
  };
}

export const EmployeeCaseSummary: React.FC = () => {
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();
  const assignmentId = caseId;
  const [draft, setDraft] = useState<CaseDraftDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [wizardNavLoading, setWizardNavLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!assignmentId) return;
    setIsLoading(true);
    setError('');
    try {
      const { data, error: loadError } = await getCaseDetailsByAssignmentId(assignmentId);
      if (loadError) {
        setDraft(buildDefaultDraft());
        setError(
          loadError.includes('Case row missing')
            ? loadError
            : 'Assignment not found or not visible under RLS. You can try editing from the wizard.'
        );
      } else if (data?.case) {
        setDraft(caseToWizardDraft(data.case));
      } else {
        setDraft(buildDefaultDraft());
        setError('Assignment not found or not visible under RLS.');
      }
    } catch {
      setDraft(buildDefaultDraft());
      setError('Assignment not found or not visible under RLS.');
    }
    setIsLoading(false);
  }, [assignmentId]);

  useEffect(() => {
    load();
  }, [load]);

  const b = draft?.relocationBasics || {};
  const ep = draft?.employeeProfile || {};
  const fm = draft?.familyMembers || {};
  const ac = draft?.assignmentContext || {};

  const hasAnyData =
    (b.originCountry || b.originCity || b.destCountry || b.destCity || b.purpose || b.targetMoveDate != null) ||
    (ep.fullName || ep.email || ep.nationality) ||
    (fm.spouse?.fullName || (fm.children?.length ?? 0) > 0) ||
    (ac.employerName || ac.jobTitle || ac.contractStartDate);

  const planHref = assignmentId ? buildRoute('employeeCasePlan', { caseId: assignmentId }) : buildRoute('employeeDashboard');

  return (
    <AppShell title="My case" subtitle="Intake summary — what you’ve shared so far.">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <LoadingButton
          variant="outline"
          loading={wizardNavLoading}
          loadingLabel="Opening wizard…"
          onClick={async () => {
            setWizardNavLoading(true);
            await new Promise((r) => setTimeout(r, 120));
            if (assignmentId) {
              navigate(`/employee/case/${assignmentId}/wizard/1`);
            } else {
              navigate('/employee/journey');
            }
          }}
        >
          Continue editing
        </LoadingButton>
        {assignmentId && (
          <LoadingButton variant="outline" loading={isLoading} loadingLabel="Refreshing…" onClick={() => load()}>
            Refresh
          </LoadingButton>
        )}
      </div>

      {assignmentId && !isLoading && (
        <Card padding="md" className="mb-6 border-[#bfdbfe] bg-[#eff6ff]">
          <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">What to do next</h2>
          <ul className="text-sm text-[#1e3a5f] space-y-2 list-disc pl-5 leading-relaxed">
            <li>
              <strong>Already in the intake wizard?</strong> Use <strong>Continue editing</strong> above to pick up where
              you left off.
            </li>
            <li>
              <strong>Not started yet?</strong> Use <strong>Continue editing</strong> to begin — you’ll go through
              relocation basics, your profile, family, and assignment details step by step. You can also start from your{' '}
              <Link to={buildRoute('employeeDashboard')} className="font-medium text-[#0b2b43] underline">
                Dashboard
              </Link>
              .
            </li>
            <li>
              <strong>Policy &amp; benefits</strong> from your employer (read-only) are on{' '}
              <Link to={buildRoute('hrPolicy')} className="font-medium text-[#0b2b43] underline">
                HR Policy
              </Link>
              . Tap the <strong>blue chat icon</strong> there to ask what your published policy covers.
            </li>
            <li>
              <strong>Tasks with HR</strong> (checklist, due dates) are on the{' '}
              <Link to={planHref} className="font-medium text-[#0b2b43] underline">
                Relocation plan
              </Link>{' '}
              tab.
            </li>
          </ul>
        </Card>
      )}

      {error && (
        <Alert variant="error">
          {error}
          {import.meta.env.DEV && assignmentId && (
            <div className="mt-2 text-xs font-mono text-[#6b7280]">assignmentId: {assignmentId}</div>
          )}
        </Alert>
      )}
      {isLoading && (
        <div className="space-y-4 mb-6" aria-busy="true">
          <div className="text-sm font-medium text-[#0b2b43]">Loading your saved case data…</div>
          <div className="grid grid-cols-1 gap-4 animate-pulse max-w-3xl">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-lg bg-[#e2e8f0]" />
            ))}
          </div>
        </div>
      )}

      {!isLoading && draft && (
        <div className="max-w-3xl space-y-2">
          <SummarySection title="Relocation Basics">
            <div>Origin: {[b.originCity, b.originCountry].filter(Boolean).join(', ') || '-'}</div>
            <div>Destination: {[b.destCity, b.destCountry].filter(Boolean).join(', ') || '-'}</div>
            <div>Purpose: {b.purpose || '-'}</div>
            <div>Target move date: {b.targetMoveDate || '-'}</div>
            <div>Duration: {b.durationMonths != null ? `${b.durationMonths} months` : '-'}</div>
          </SummarySection>
          <SummarySection title="Employee Profile">
            <div>Name: {ep.fullName || '-'}</div>
            <div>Email: {ep.email || '-'}</div>
            <div>Nationality: {ep.nationality || '-'}</div>
            <div>Passport country: {ep.passportCountry || '-'}</div>
            <div>Residence country: {ep.residenceCountry || '-'}</div>
          </SummarySection>
          <SummarySection title="Family Members">
            <div>Spouse: {fm.spouse?.fullName ? fm.spouse.fullName : '-'}</div>
            <div>Children: {fm.children?.length ? `${fm.children.length} child(ren)` : '-'}</div>
          </SummarySection>
          <SummarySection title="Assignment / Context">
            <div>Employer: {ac.employerName || '-'}</div>
            <div>Job title: {ac.jobTitle || '-'}</div>
            <div>Contract start: {ac.contractStartDate || '-'}</div>
            <div>Contract type: {ac.contractType || '-'}</div>
          </SummarySection>
        </div>
      )}

      {!isLoading && draft && !hasAnyData && (
        <p className="text-sm text-[#6b7280] mt-4">No intake saved yet. Use Continue editing to complete it.</p>
      )}

      {(import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true') && assignmentId && (
        <AssignmentDebugPanel assignmentIdFromRoute={assignmentId} />
      )}
    </AppShell>
  );
};
