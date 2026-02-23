/**
 * Employee Case Summary - Read-only view of intake wizard responses.
 * Shown when the user clicks "My Case" in the nav.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Card } from '../../components/antigravity';
import { getCase } from '../../api/cases';
import { getRelocationCase } from '../../api/relocation';
import { employeeAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
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
  const { caseId } = useParams<{ caseId: string }>();
  const [draft, setDraft] = useState<CaseDraftDTO | null>(null);
  const [feedback, setFeedback] = useState<Array<{ id: string; message: string; created_at: string }>>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!caseId) return;
    setIsLoading(true);
    setError('');
    try {
      const data = await getCase(caseId);
      setDraft(caseToWizardDraft(data));
    } catch {
      try {
        const relocation = await getRelocationCase(caseId);
        const fallbackCase: CaseDTO = {
          id: relocation.id,
          status: relocation.status || 'DRAFT',
          draft: buildDefaultDraft(),
          createdAt: relocation.created_at || new Date().toISOString(),
          updatedAt: relocation.updated_at || new Date().toISOString(),
          originCountry: relocation.home_country || undefined,
          destCountry: relocation.host_country || undefined,
        };
        setDraft(caseToWizardDraft(fallbackCase));
      } catch {
        setDraft(buildDefaultDraft());
        setError('Unable to load your case. You can try editing from the wizard.');
      }
    }

    try {
      const fb = await employeeAPI.getFeedback(caseId);
      setFeedback((fb ?? []).map((f) => ({ id: f.id, message: f.message, created_at: f.created_at })));
    } catch {
      setFeedback([]);
    }
    setIsLoading(false);
  }, [caseId]);

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

  return (
    <AppShell title="My Case" subtitle="Summary of your intake responses.">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Link
          to={caseId ? `/employee/case/${caseId}/wizard/1` : '/employee/journey'}
          className="inline-flex items-center justify-center font-medium rounded-lg px-4 py-2 border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] transition-colors"
        >
          Continue editing
        </Link>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading your case...</div>}

      {!isLoading && draft && (
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
      )}

      {!isLoading && draft && !hasAnyData && (
        <p className="text-sm text-[#6b7280]">You haven&apos;t filled in the intake wizard yet. Click &quot;Continue editing&quot; to get started.</p>
      )}
    </AppShell>
  );
};
