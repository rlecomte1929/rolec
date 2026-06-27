/**
 * ImmigrationChecklistPage — MVG-6B
 *
 * Employee-facing document checklist for their immigration case.
 * Route: /employee/case/:caseId/immigration/checklist
 *
 * Shows required documents per permit type with status badges and upload placeholder.
 */

import React, { useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card, StatusPill } from '../../components/antigravity';
import type { JourneyStatus } from '../../components/antigravity';
import { buildRoute } from '../../navigation/routes';
import { CaseDocumentsPanel } from '../../components/case/CaseDocumentsPanel';
import api from '../../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

type DocStatus = 'not_started' | 'uploaded' | 'verified';

interface ImmigrationCase {
  id: string;
  case_id: string;
  corridor_from: string;
  corridor_to: string;
  permit_type: string;
  status: string;
  document_statuses: Record<string, DocStatus>;
}

// ── Document lists per permit type ────────────────────────────────────────────

const REQUIRED_DOCS: Record<string, string[]> = {
  eu_blue_card: [
    'Valid passport (min 6 months validity)',
    'University degree certificate (recognised)',
    'Signed employment contract',
    'Proof of salary above Blue Card threshold',
    'Health insurance confirmation',
  ],
  work_permit: [
    'Valid passport',
    'Employer sponsorship letter',
    'Signed employment contract',
    'Proof of qualifications',
    'Recent payslips (last 3 months)',
    'Health insurance certificate',
  ],
  skilled_worker_visa: [
    'Valid passport',
    'Recognised qualification certificate',
    'Signed employment contract',
    'Proof of German language skills (A1+)',
    'Health insurance confirmation',
  ],
  eea_registration: [
    'Valid EU passport or national ID card',
    'Proof of employment or self-employment',
    'Proof of address at destination',
  ],
  other: [
    'Valid passport',
    'Signed employment contract',
    'Employer letter',
  ],
};

const PERMIT_LABELS: Record<string, string> = {
  eu_blue_card: 'EU Blue Card',
  work_permit: 'Work Permit',
  skilled_worker_visa: 'Skilled Worker Visa',
  eea_registration: 'EEA Registration',
  other: 'Other',
};

// Map each DocStatus → an antigravity StatusPill status + label (E light language).
const STATUS_CONFIG: Record<DocStatus, { label: string; status: JourneyStatus }> = {
  not_started: { label: 'Action needed', status: 'action' },
  uploaded: { label: 'Uploaded', status: 'submitted' },
  verified: { label: 'Verified', status: 'ready' },
};

// ── Component ────────────────────────────────────────────────────────────────

export const ImmigrationChecklistPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [uploadToast, setUploadToast] = useState<string | null>(null);

  const immigrationQuery = useQuery({
    queryKey: ['employee', 'immigration-case', caseId],
    queryFn: async () => {
      const res = await api.get(`/api/employee/cases/${caseId}/immigration`);
      return res.data as ImmigrationCase;
    },
    enabled: !!caseId,
  });
  const immCase = immigrationQuery.data ?? null;
  // Preserve the original: with no caseId the page stays in its loading state.
  const loading = !caseId || immigrationQuery.isLoading;
  const error = immigrationQuery.isError
    ? 'Could not load your immigration case. Please contact HR.'
    : null;

  const handleUpload = useCallback((docName: string) => {
    setUploadToast(`Upload coming soon — please send "${docName}" directly to your immigration partner.`);
    setTimeout(() => setUploadToast(null), 4000);
  }, []);

  if (loading) {
    return (
      <AppShell title="Document checklist">
        <p className="text-[#6b7280] p-8">Loading your document checklist…</p>
      </AppShell>
    );
  }

  if (error || !immCase) {
    return (
      <AppShell title="Document checklist">
        <div className="p-8">
          <Alert variant="error">
            {error ?? 'No immigration case found for this relocation. Contact your HR team.'}
          </Alert>
          <Button
            className="mt-4"
            variant="ghost"
            onClick={() => navigate(buildRoute('employeeDashboard'))}
          >
            Back to dashboard
          </Button>
        </div>
      </AppShell>
    );
  }

  const docs = REQUIRED_DOCS[immCase.permit_type] ?? REQUIRED_DOCS.other ?? [];
  const statuses = immCase.document_statuses ?? {};
  const completedCount = docs.filter(
    (_, i) => statuses[String(i)] === 'uploaded' || statuses[String(i)] === 'verified',
  ).length;

  return (
    <AppShell title="Document checklist">
      <div className="max-w-xl mx-auto py-8 px-4">

        {/* Header */}
        <h1 className="text-2xl font-semibold text-navy-800 mb-1">
          Your document checklist
        </h1>

        {/* Permit context card */}
        <Card className="p-4 mb-6">
          <p className="text-sm text-[#6b7280]">Your permit</p>
          <p className="text-lg font-semibold text-navy-800">
            {PERMIT_LABELS[immCase.permit_type] ?? immCase.permit_type}
          </p>
          <p className="text-sm text-[#374151] mt-0.5">
            {immCase.corridor_from} → {immCase.corridor_to}
          </p>
          <p className="text-xs text-[#9aa6b2] mt-2">
            Based on your role and salary — confirmed by your relocation team.
          </p>
        </Card>

        {/* Completion strip */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-2 rounded-full bg-[#e2e8f0] overflow-hidden">
            <div
              className="h-full bg-[#0b2b43] rounded-full transition-all"
              style={{ width: `${docs.length ? (completedCount / docs.length) * 100 : 0}%` }}
              aria-label={`${completedCount} of ${docs.length} documents ready`}
            />
          </div>
          <span className="text-sm text-[#6b7280] whitespace-nowrap">
            {completedCount} of {docs.length} documents ready
          </span>
        </div>

        {/* Content-honesty note */}
        <Alert variant="warning" className="mb-8">
          Indicative — your case officer confirms the final document requirements with the
          immigration authority.
        </Alert>

        {/* Toast */}
        {uploadToast && (
          <div
            role="status"
            className="mb-4 rounded-lg bg-[#eef4f8] border border-[#c7d8e6] text-[#0b2b43] px-4 py-3 text-sm"
          >
            {uploadToast}
          </div>
        )}

        {/* Document list */}
        <div className="space-y-3">
          {docs.map((doc, idx) => {
            const docStatus: DocStatus = statuses[String(idx)] ?? 'not_started';
            const cfg = STATUS_CONFIG[docStatus];

            return (
              <Card key={idx} className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm text-navy-800 font-medium">{doc}</p>
                    <StatusPill status={cfg.status} className="mt-1.5">
                      {cfg.label}
                    </StatusPill>
                  </div>
                  {docStatus === 'not_started' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleUpload(doc)}
                      aria-label={`Upload ${doc}`}
                    >
                      Upload
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>

        {/* Footer note */}
        <p className="mt-6 text-xs text-[#6b7280]">
          Upload securely — only your relocation team can see these documents. Document status is
          updated by your HR team and immigration partner; use the Upload button to flag a document
          as ready and your partner will verify it.
        </p>

        {/* BL-OCR.4 / AIQ-750 — upload documents + AI extraction status */}
        <section className="mt-8">
          <h2 className="text-sm font-semibold text-navy-800 mb-3">Upload documents</h2>
          <CaseDocumentsPanel caseId={caseId} canUpload />
        </section>

        <div className="mt-6">
          <Button
            variant="ghost"
            onClick={() =>
              navigate(buildRoute('employeeCaseRoadmap', { caseId: caseId }))
            }
          >
            ← Back to roadmap
          </Button>
        </div>
      </div>
    </AppShell>
  );
};
