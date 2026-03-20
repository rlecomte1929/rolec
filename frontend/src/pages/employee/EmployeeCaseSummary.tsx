/**
 * Employee Case Summary - Read-only view of intake wizard responses.
 * Shown when the user clicks "My Case" in the nav.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Card, LoadingButton } from '../../components/antigravity';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { employeeAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import { AssignmentDebugPanel } from '../AssignmentDebugPanel';
import { RelocationTaskTracker } from '../../features/timeline/RelocationTaskTracker';
import { MobilityCasePanels } from '../../components/employee/MobilityCasePanels';
import type { CaseDTO, CaseDraftDTO } from '../../types';

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
  const [searchParams] = useSearchParams();
  const assignmentId = caseId;
  const [draft, setDraft] = useState<CaseDraftDTO | null>(null);
  const [caseFlags, setCaseFlags] = useState<Record<string, unknown>>({});
  const [feedback, setFeedback] = useState<Array<{ id: string; message: string; created_at: string }>>([]);
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
        setCaseFlags({});
        setError(
          loadError.includes('Case row missing')
            ? loadError
            : 'Assignment not found or not visible under RLS. You can try editing from the wizard.'
        );
      } else if (data?.case) {
        setDraft(caseToWizardDraft(data.case));
        setCaseFlags(data.case.flags || {});
      } else {
        setDraft(buildDefaultDraft());
        setCaseFlags({});
        setError('Assignment not found or not visible under RLS.');
      }
    } catch {
      setDraft(buildDefaultDraft());
      setCaseFlags({});
      setError('Assignment not found or not visible under RLS.');
    }

    try {
      const fb = await employeeAPI.getFeedback(assignmentId);
      setFeedback((fb ?? []).map((f) => ({ id: f.id, message: f.message, created_at: f.created_at })));
    } catch {
      setFeedback([]);
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

  const mobilityCaseId = useMemo(() => {
    const q = searchParams.get('mcid')?.trim();
    if (q) return q;
    const fid = caseFlags.mobility_case_id;
    if (typeof fid === 'string' && fid.trim()) return fid.trim();
    const env = import.meta.env.VITE_DEMO_MOBILITY_CASE_ID as string | undefined;
    return env?.trim() || null;
  }, [searchParams, caseFlags]);

  const hasAnyData =
    (b.originCountry || b.originCity || b.destCountry || b.destCity || b.purpose || b.targetMoveDate != null) ||
    (ep.fullName || ep.email || ep.nationality) ||
    (fm.spouse?.fullName || (fm.children?.length ?? 0) > 0) ||
    (ac.employerName || ac.jobTitle || ac.contractStartDate);

  return (
    <AppShell title="My Case" subtitle="Summary of your intake responses.">
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
          <LoadingButton
            variant="outline"
            loading={isLoading}
            loadingLabel="Refreshing…"
            onClick={() => load()}
          >
            Refresh
          </LoadingButton>
        )}
      </div>

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
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-pulse">
            <div className="lg:col-span-2 space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-lg bg-[#e2e8f0]" />
              ))}
            </div>
            <div className="h-40 rounded-lg bg-[#e2e8f0]" />
          </div>
        </div>
      )}

      {assignmentId && (
        <div className="mb-6">
          <div className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-2">
            Relocation plan
          </div>
          <RelocationTaskTracker
            assignmentId={assignmentId}
            deferredEnsureWhenEmpty
            title="Your relocation plan & actions"
          />
        </div>
      )}

      {!isLoading && draft && (
        <>
        <div className="mb-6">
          <div className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-2">
            Case status & next steps
          </div>
          <MobilityCasePanels
            mobilityCaseId={mobilityCaseId}
            relocationBasics={b}
            familyMembers={fm}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-2">
            <SummarySection title="Relocation Basics">
              <div>Origin: {[b.originCity, b.originCountry].filter(Boolean).join(', ') || '—'}</div>
              <div>Destination: {[b.destCity, b.destCountry].filter(Boolean).join(', ') || '—'}</div>
              <div>Purpose: {b.purpose || '—'}</div>
              <div>Target move date: {b.targetMoveDate || '—'}</div>
              <div>Duration: {b.durationMonths != null ? `${b.durationMonths} months` : '—'}</div>
            </SummarySection>
            <SummarySection title="Employee Profile">
              <div>Name: {ep.fullName || '—'}</div>
              <div>Email: {ep.email || '—'}</div>
              <div>Nationality: {ep.nationality || '—'}</div>
              <div>Passport country: {ep.passportCountry || '—'}</div>
              <div>Residence country: {ep.residenceCountry || '—'}</div>
            </SummarySection>
            <SummarySection title="Family Members">
              <div>Spouse: {fm.spouse?.fullName ? fm.spouse.fullName : '—'}</div>
              <div>Children: {fm.children?.length ? `${fm.children.length} child(ren)` : '—'}</div>
            </SummarySection>
            <SummarySection title="Assignment / Context">
              <div>Employer: {ac.employerName || '—'}</div>
              <div>Job title: {ac.jobTitle || '—'}</div>
              <div>Contract start: {ac.contractStartDate || '—'}</div>
              <div>Contract type: {ac.contractType || '—'}</div>
            </SummarySection>
          </div>

          <div>
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43] mb-3">Feedback from HR</div>
              {feedback.length === 0 ? (
                <div className="text-sm text-[#9ca3af]">No feedback yet.</div>
              ) : (
                <div className="space-y-3">
                  {feedback.map((f) => (
                    <div key={f.id} className="text-sm">
                      <div className="text-[#6b7280] text-xs">
                        {new Date(f.created_at).toLocaleString()}
                      </div>
                      <div className="text-[#0b2b43] mt-0.5">{f.message}</div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
        </>
      )}

      {!isLoading && draft && !hasAnyData && (
        <p className="text-sm text-[#6b7280]">No intake yet. Use Continue editing to complete it.</p>
      )}

      {(import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true') && assignmentId && (
        <AssignmentDebugPanel assignmentIdFromRoute={assignmentId} />
      )}
    </AppShell>
  );
};
