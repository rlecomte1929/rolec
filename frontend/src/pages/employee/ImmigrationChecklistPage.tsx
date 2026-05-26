/**
 * ImmigrationChecklistPage — MVG-6B
 *
 * Employee-facing document checklist for their immigration case.
 * Route: /employee/case/:caseId/immigration/checklist
 *
 * Shows required documents per permit type with status badges and upload placeholder.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Badge, Button, Card } from '../../components/antigravity';
import { buildRoute } from '../../navigation/routes';
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

const STATUS_CONFIG: Record<DocStatus, { label: string; variant: 'neutral' | 'success' | 'info' }> = {
  not_started: { label: 'Not started', variant: 'neutral' },
  uploaded: { label: 'Uploaded', variant: 'info' },
  verified: { label: 'Verified', variant: 'success' },
};

// ── Component ────────────────────────────────────────────────────────────────

export const ImmigrationChecklistPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [immCase, setImmCase] = useState<ImmigrationCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadToast, setUploadToast] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    const load = async () => {
      try {
        // Fetch the immigration case for this relocation case
        const res = await api.get(`/api/employee/cases/${caseId}/immigration`);
        if (!cancelled) setImmCase(res.data as ImmigrationCase);
      } catch {
        if (!cancelled) setError('Could not load your immigration case. Please contact HR.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [caseId]);

  const handleUpload = useCallback((docName: string) => {
    setUploadToast(`Upload coming soon — please send "${docName}" directly to your immigration partner.`);
    setTimeout(() => setUploadToast(null), 4000);
  }, []);

  if (loading) {
    return (
      <AppShell title="Document checklist">
        <p className="text-[#94a3b8] p-8">Loading your document checklist…</p>
      </AppShell>
    );
  }

  if (error || !immCase) {
    return (
      <AppShell title="Document checklist">
        <div className="p-8">
          <p className="text-[#fca5a5]">
            {error ?? 'No immigration case found for this relocation. Contact your HR team.'}
          </p>
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

  const docs = REQUIRED_DOCS[immCase.permit_type] ?? REQUIRED_DOCS.other;
  const statuses = immCase.document_statuses ?? {};
  const completedCount = docs.filter(
    (_, i) => statuses[String(i)] === 'uploaded' || statuses[String(i)] === 'verified',
  ).length;

  return (
    <AppShell title="Document checklist">
      <div className="max-w-xl mx-auto py-8 px-4">

        {/* Header */}
        <h1 className="text-2xl font-semibold text-[#f1f5f9] mb-1">
          Your document checklist
        </h1>
        <p className="text-[#94a3b8] text-sm mb-1">
          {immCase.corridor_from} → {immCase.corridor_to} ·{' '}
          {PERMIT_LABELS[immCase.permit_type] ?? immCase.permit_type}
        </p>

        {/* Progress indicator */}
        <div className="flex items-center gap-3 mb-8">
          <div className="flex-1 h-2 rounded-full bg-[#1e293b] overflow-hidden">
            <div
              className="h-full bg-[#3b82f6] rounded-full transition-all"
              style={{ width: `${docs.length ? (completedCount / docs.length) * 100 : 0}%` }}
              aria-label={`${completedCount} of ${docs.length} documents complete`}
            />
          </div>
          <span className="text-sm text-[#94a3b8] whitespace-nowrap">
            {completedCount} of {docs.length} documents
          </span>
        </div>

        {/* Toast */}
        {uploadToast && (
          <div
            role="status"
            className="mb-4 rounded-lg bg-[#1e3a5f] border border-[#1d4ed8] text-[#93c5fd] px-4 py-3 text-sm"
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
                  <div className="flex items-start gap-3">
                    <span
                      className={[
                        'mt-0.5 flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center text-xs',
                        docStatus === 'verified'
                          ? 'bg-[#14532d] border-[#22c55e] text-[#4ade80]'
                          : docStatus === 'uploaded'
                          ? 'bg-[#1e3a5f] border-[#3b82f6] text-[#60a5fa]'
                          : 'bg-transparent border-[#475569]',
                      ].join(' ')}
                      aria-hidden="true"
                    >
                      {docStatus === 'verified' ? '✓' : docStatus === 'uploaded' ? '↑' : ''}
                    </span>
                    <div>
                      <p className="text-sm text-[#e2e8f0] font-medium">{doc}</p>
                      <Badge variant={cfg.variant} size="sm">
                        {cfg.label}
                      </Badge>
                    </div>
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
        <p className="mt-6 text-xs text-[#64748b]">
          Document status is updated by your HR team and immigration partner. Use the Upload
          button to flag a document as ready — your partner will verify it.
        </p>

        <div className="mt-6">
          <Button
            variant="ghost"
            onClick={() =>
              navigate(buildRoute('employeeCaseRoadmap', { caseId: caseId! }))
            }
          >
            ← Back to roadmap
          </Button>
        </div>
      </div>
    </AppShell>
  );
};
