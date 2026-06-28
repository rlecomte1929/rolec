/**
 * Employee Case Summary — intake snapshot: instructions, then profile/relocation basics (read-only).
 * Relocation tasks → Relocation plan tab. Policy Q&A → HR Policy (Policy Assistant). Not on this page.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Card, LoadingButton } from '../../components/antigravity';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { getAuthItem } from '../../utils/demo';
import { getCountryName } from '../../utils/countries';
import { AssignmentDebugPanel } from '../AssignmentDebugPanel';
import { EmployeeNextActionBar } from '../../components/employee/EmployeeNextActionBar';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';
import type { CaseDTO, CaseDraftDTO } from '../../types';
import { buildRoute } from '../../navigation/routes';

function SummarySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card padding="md" className="h-full border-[#e2e8f0] shadow-sm">
      <div className="text-sm font-semibold text-[#0b2b43] mb-2">{title}</div>
      <div className="text-sm text-[#4b5563] space-y-1">{children}</div>
    </Card>
  );
}

// AIQ-1271: render a "Label: value" row only when the value is non-empty — hides the
// row entirely instead of showing a bare "-" placeholder.
function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === false) return null;
  return <div>{label}: {value}</div>;
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
  const [caseStatus, setCaseStatus] = useState<string>('');

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
        setCaseStatus(data.case.status ?? '');
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
    void load();
  }, [load]);

  // Remember the user's last position so the dashboard's "Open case" can
  // route them back here instead of forcing a fresh wizard start.
  useTrackLastVisited(assignmentId || null);

  const b = draft?.relocationBasics || {};
  const ep = draft?.employeeProfile || {};
  const fm = draft?.familyMembers || {};
  const ac = draft?.assignmentContext || {};

  const hasAnyData =
    (b.originCountry || b.originCity || b.destCountry || b.destCity || b.purpose || b.targetMoveDate != null) ||
    (ep.fullName || ep.email || ep.nationality) ||
    (fm.spouse?.fullName || (fm.children?.length ?? 0) > 0) ||
    (ac.employerName || ac.jobTitle || ac.contractStartDate);

  const roadmapHref = assignmentId ? buildRoute('employeeCaseRoadmap', { caseId: assignmentId }) : buildRoute('employeeDashboard');
  const immigrationHref = assignmentId ? buildRoute('employeeCaseImmigration', { caseId: assignmentId }) : null;

  return (
    <AppShell title="My case" subtitle="Intake summary — what you’ve shared so far.">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <LoadingButton
          variant="outline"
          loading={wizardNavLoading}
          loadingLabel="Opening wizard…"
          onClick={async () => {
            setWizardNavLoading(true);
            try {
              await new Promise((r) => setTimeout(r, 120));
              navigate(buildRoute('employeeIntake'));
            } finally {
              setWizardNavLoading(false);
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

      {/* M-09 (AIQ-1267): confirm the intake actually reached HR. */}
      {caseStatus === 'submitted' && (
        <div className="mb-6">
          <Alert variant="success">
            ✓ Intake submitted — your HR team is reviewing your details. You’ll hear from them in your Inbox.
          </Alert>
        </div>
      )}

      {/* Immigration intake card */}
      {immigrationHref && !isLoading && (
        <Card padding="md" className="mb-6 border-[#e0f2fe] bg-[#f0f9ff]">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex-shrink-0 rounded-full bg-[#bae6fd] p-2">
                <svg className="h-4 w-4 text-[#0369a1]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">Immigration intake</div>
                <p className="text-xs text-[#475569] mt-0.5">
                  Provide your passport details, address history, and family information to start
                  your visa application. Takes about 10–15 minutes.
                </p>
              </div>
            </div>
            <Link
              to={immigrationHref}
              className="shrink-0 rounded-lg bg-[#0b2b43] px-4 py-2 text-xs font-semibold text-white hover:bg-[#1a3f5e] transition-colors"
            >
              Start →
            </Link>
          </div>
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 rounded-lg bg-[#e2e8f0] animate-pulse" />
            ))}
          </div>
        </div>
      )}

      {!isLoading && draft && (
        <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
          <SummarySection title="Relocation Basics">
            <Field label="Origin" value={[b.originCity, getCountryName(b.originCountry)].filter(Boolean).join(', ')} />
            <Field label="Destination" value={[b.destCity, getCountryName(b.destCountry)].filter(Boolean).join(', ')} />
            <Field label="Purpose" value={b.purpose} />
            <Field label="Target move date" value={b.targetMoveDate} />
            <Field label="Duration" value={b.durationMonths != null ? `${b.durationMonths} months` : null} />
          </SummarySection>
          <SummarySection title="Employee Profile">
            <Field label="Name" value={ep.fullName} />
            <Field label="Email" value={ep.email} />
            <Field label="Nationality" value={getCountryName(ep.nationality)} />
            <Field label="Passport country" value={getCountryName(ep.passportCountry)} />
            <Field label="Residence country" value={ep.residenceCountry} />
          </SummarySection>
          <SummarySection title="Family Members">
            <Field label="Spouse" value={fm.spouse?.fullName} />
            <Field label="Children" value={fm.children?.length ? `${fm.children.length} child(ren)` : null} />
          </SummarySection>
          <SummarySection title="Assignment / Context">
            <Field label="Employer" value={ac.employerName} />
            <Field label="Job title" value={ac.jobTitle} />
            <Field label="Contract start" value={ac.contractStartDate} />
            <Field label="Contract type" value={ac.contractType} />
          </SummarySection>
        </div>
      )}

      {!isLoading && draft && !hasAnyData && (
        <p className="text-sm text-[#6b7280] mt-4">No intake saved yet. Use Continue editing to complete it.</p>
      )}

      {/* M-11 (AIQ-1268): "What to do next" moved BELOW the data so the employee
          sees their own case details first, not guidance before content. */}
      {assignmentId && !isLoading && (
        <Card padding="md" className="mt-6 mb-6 border-[#bfdbfe] bg-[#eff6ff]">
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
              . Use <strong>Policy Assistant</strong> on that page for questions tied to your published policy.
            </li>
            <li>
              <strong>Tasks with HR</strong> (checklist, due dates) are on your{' '}
              <Link to={roadmapHref} className="font-medium text-[#0b2b43] underline">
                Roadmap
              </Link>{' '}
              tab.
            </li>
            {immigrationHref && (
              <li>
                <strong>Immigration intake</strong> — complete your visa profile (passport scan,
                personal details, address history) on the{' '}
                <Link to={immigrationHref} className="font-medium text-[#0b2b43] underline">
                  Immigration intake
                </Link>{' '}
                page.
              </li>
            )}
          </ul>
        </Card>
      )}

      {(import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true') && assignmentId && (
        <AssignmentDebugPanel assignmentIdFromRoute={assignmentId} />
      )}

      {/* Sticky next-action bar — eliminates the "what now?" dead-end on
          this page. If the user has done some intake but not all of it,
          the primary CTA goes back to the wizard. If they've finished
          intake, route them to the relocation plan (the aggregator). */}
      {assignmentId && !isLoading && (
        <EmployeeNextActionBar
          status={hasAnyData ? 'My case' : 'Nothing saved yet'}
          hint={
            hasAnyData
              ? "Pick up where you left off — the wizard remembers your inputs."
              : "Start your intake to unlock services and the relocation plan."
          }
          primaryLabel={hasAnyData ? 'View my roadmap →' : 'Start intake →'}
          primaryHref={
            hasAnyData
              ? roadmapHref
              : buildRoute('employeeIntake')
          }
          secondaryLabel={hasAnyData ? 'Continue editing intake' : undefined}
          secondaryHref={hasAnyData ? buildRoute('employeeIntake') : undefined}
        />
      )}
    </AppShell>
  );
};
