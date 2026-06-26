/**
 * MyImmigrationData — IMM-19
 *
 * Employee-facing GDPR data-management screen. Lets the employee:
 *   - see every field ReloPass holds for their immigration case, grouped by
 *     section, with a provenance tag (HR-provided / Self-entered / OCR-extracted)
 *   - reveal the otherwise-masked passport number
 *   - download a full PDF export of their data (GDPR Art. 15)
 *   - withdraw optional consent (vendor sharing) (GDPR Art. 7(3))
 *   - request erasure of their data (GDPR Art. 17)
 *
 * Route: /employee/case/:caseId/my-data
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Checkbox } from '../antigravity/Checkbox';
import { AppShell } from '../AppShell';
import { Alert, Badge, Button, Card } from '../antigravity';
import api from '../../api/client';

const RETENTION_NOTICE =
  'Your data will be automatically deleted 36 months after your case closes.';

type FieldSource = 'hr_provided' | 'self_entered' | 'ocr';

interface ImmigrationProfile {
  id?: string;
  field_sources?: Record<string, FieldSource>;
  [key: string]: unknown;
}

interface ConsentRecord {
  purpose: string;
  consented: boolean;
  consent_version?: string;
  consented_at?: string;
  withdrawn_at?: string | null;
  withdrawn_reason?: string | null;
  active: boolean;
}

interface FieldDef {
  key: string;
  label: string;
}

interface SectionDef {
  title: string;
  fields: FieldDef[];
}

// Field groupings — must cover every vault field so nothing is hidden from the
// employee (GDPR transparency). Order mirrors the immigration intake flow.
const SECTIONS: SectionDef[] = [
  {
    title: 'Identity',
    fields: [
      { key: 'legal_first_name', label: 'Legal first name' },
      { key: 'legal_last_name', label: 'Legal last name' },
      { key: 'middle_names', label: 'Middle names' },
      { key: 'date_of_birth', label: 'Date of birth' },
      { key: 'place_of_birth', label: 'Place of birth' },
      { key: 'nationality', label: 'Nationality' },
      { key: 'second_nationality', label: 'Second nationality' },
      { key: 'gender', label: 'Gender' },
      { key: 'marital_status', label: 'Marital status' },
    ],
  },
  {
    title: 'Passport & visa',
    fields: [
      { key: 'passport_number', label: 'Passport number' },
      { key: 'passport_country', label: 'Passport country' },
      { key: 'passport_issue_date', label: 'Passport issue date' },
      { key: 'passport_expiry', label: 'Passport expiry' },
      { key: 'existing_visa_type', label: 'Existing visa type' },
      { key: 'existing_visa_expiry', label: 'Existing visa expiry' },
      { key: 'prior_visa_refusals', label: 'Prior visa refusals' },
    ],
  },
  {
    title: 'Address history',
    fields: [
      { key: 'current_address', label: 'Current address' },
      { key: 'address_history', label: 'Previous addresses' },
    ],
  },
  {
    title: 'Employment & education',
    fields: [
      { key: 'employer_name', label: 'Employer' },
      { key: 'job_title', label: 'Job title' },
      { key: 'employment_start_date', label: 'Employment start date' },
      { key: 'salary_amount', label: 'Salary' },
      { key: 'salary_currency', label: 'Salary currency' },
      { key: 'contract_type', label: 'Contract type' },
      { key: 'highest_qualification', label: 'Highest qualification' },
      { key: 'institution', label: 'Institution' },
      { key: 'graduation_year', label: 'Graduation year' },
    ],
  },
  {
    title: 'Family',
    fields: [
      { key: 'spouse_name', label: 'Spouse name' },
      { key: 'spouse_nationality', label: 'Spouse nationality' },
      { key: 'spouse_dob', label: 'Spouse date of birth' },
      { key: 'dependents', label: 'Dependents' },
    ],
  },
];

const SOURCE_LABELS: Record<FieldSource, string> = {
  hr_provided: 'HR-provided',
  self_entered: 'Self-entered',
  ocr: 'OCR-extracted',
};

function maskPassport(value: string): string {
  if (value.length <= 5) return '•'.repeat(value.length);
  return `${value.slice(0, 3)}${'•'.repeat(Math.max(value.length - 5, 1))}${value.slice(-2)}`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) {
    if (value.length === 0) return '—';
    return value
      .map((item) =>
        typeof item === 'object' && item !== null
          ? Object.values(item as Record<string, unknown>)
              .filter((v) => v !== null && v !== undefined && v !== '')
              .join(', ')
          : String(item),
      )
      .join(' · ');
  }
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>)
      .filter((v) => v !== null && v !== undefined && v !== '')
      .join(', ') || '—';
  }
  return String(value);
}

export const MyImmigrationData: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [profile, setProfile] = useState<ImmigrationProfile | null>(null);
  const [consent, setConsent] = useState<ConsentRecord[]>([]);

  const [showFullPassport, setShowFullPassport] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);

  const load = useCallback(async () => {
    if (!caseId) {
      setLoadError('No case ID in the URL.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [profileResp, consentResp] = await Promise.all([
        api.get<{ profile: ImmigrationProfile | null }>(
          `/api/employee/cases/${caseId}/profile`,
        ),
        api.get<{ consent_records: ConsentRecord[] }>(
          `/api/employee/cases/${caseId}/consent`,
        ),
      ]);
      setProfile(profileResp.data.profile);
      setConsent(consentResp.data.consent_records || []);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load your data. Please try again.';
      setLoadError(detail);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDownload = async () => {
    if (!caseId) return;
    setDownloading(true);
    setActionError(null);
    setActionNotice(null);
    try {
      const response = await api.get(`/api/employee/cases/${caseId}/my-data/export`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data as BlobPart], { type: 'application/pdf' });
      const objectUrl = URL.createObjectURL(blob);
      const cd = (response.headers as Record<string, string>)['content-disposition'] ?? '';
      const match = /filename="?([^";\n]+)"?/.exec(cd);
      const filename = match?.[1] ?? `relopass-data-export-${caseId}.pdf`;
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
      setActionNotice('Your data export has been downloaded.');
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not generate your data export. Please try again.';
      setActionError(detail);
    } finally {
      setDownloading(false);
    }
  };

  const handleWithdrawVendorSharing = async () => {
    if (!caseId) return;
    setWithdrawing(true);
    setActionError(null);
    setActionNotice(null);
    try {
      await api.post(`/api/employee/cases/${caseId}/consent/withdraw`, {
        purpose: 'vendor_sharing',
      });
      setActionNotice('Your consent for sharing data with providers has been withdrawn.');
      await load();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not withdraw consent. Please try again.';
      setActionError(detail);
    } finally {
      setWithdrawing(false);
    }
  };

  const handleRequestDeletion = async () => {
    if (!caseId) return;
    setDeleteSubmitting(true);
    setActionError(null);
    setActionNotice(null);
    try {
      await api.post(`/api/employee/cases/${caseId}/my-data/erasure-request`, {});
      setShowDeleteModal(false);
      setDeleteConfirmed(false);
      setActionNotice(
        'Your deletion request has been recorded. Your HR team will review it and respond within 30 days.',
      );
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not submit your deletion request. Please try again.';
      setActionError(detail);
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const fieldSources = profile?.field_sources || {};
  const vendorConsent = consent.find((c) => c.purpose === 'vendor_sharing');
  const processingConsent = consent.find((c) => c.purpose === 'immigration_processing');

  return (
    <AppShell
      title="Manage my data"
      subtitle="See, download, or delete the personal data ReloPass holds for your immigration case."
    >
      {loading && (
        <div className="text-sm text-[#6b7280] py-12 text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-[#e2e8f0] border-t-[#0b2b43]" />
          Loading your data…
        </div>
      )}

      {!loading && loadError && (
        <div className="max-w-lg mx-auto">
          <Alert variant="error" className="mb-4">{loadError}</Alert>
          <Button variant="outline" onClick={() => void load()}>Try again</Button>
        </div>
      )}

      {!loading && !loadError && (
        <div className="max-w-3xl mx-auto space-y-6">
          {actionNotice && <Alert variant="success">{actionNotice}</Alert>}
          {actionError && <Alert variant="error">{actionError}</Alert>}

          {/* Data sections */}
          {!profile && (
            <Card padding="lg">
              <p className="text-sm text-[#475569]">
                We don't hold any immigration data for you yet. Once you complete your
                immigration profile, it will appear here.
              </p>
            </Card>
          )}

          {profile && SECTIONS.map((section) => {
            const rows = section.fields.filter((f) => {
              const v = profile[f.key];
              return v !== null && v !== undefined && v !== '';
            });
            if (rows.length === 0) return null;
            return (
              <Card key={section.title} padding="lg">
                <h2 className="text-base font-semibold text-[#0b2b43] mb-4">{section.title}</h2>
                <dl className="divide-y divide-[#f1f5f9]">
                  {rows.map((f) => {
                    const raw = profile[f.key];
                    const source = fieldSources[f.key];
                    const isPassport = f.key === 'passport_number';
                    const displayValue = isPassport
                      ? (showFullPassport ? formatValue(raw) : maskPassport(String(raw)))
                      : formatValue(raw);
                    return (
                      <div key={f.key} className="py-3 flex items-start justify-between gap-4">
                        <dt className="text-sm text-[#64748b] w-2/5 flex-shrink-0">{f.label}</dt>
                        <dd className="text-sm text-[#0f172a] flex-1 flex items-center justify-between gap-3 flex-wrap">
                          <span className="break-words">
                            {displayValue}
                            {isPassport && (
                              <Button unstyled
                                type="button"
                                onClick={() => setShowFullPassport((s) => !s)}
                                className="ml-2 text-xs font-medium text-[#0b2b43] underline hover:text-[#1f8e8b]"
                                aria-label={showFullPassport ? 'Hide full passport number' : 'Show full passport number'}
                              >
                                {showFullPassport ? 'Hide' : 'Show full'}
                              </Button>
                            )}
                          </span>
                          {source && (
                            <Badge
                              size="sm"
                              variant={source === 'hr_provided' ? 'info' : 'neutral'}
                            >
                              {SOURCE_LABELS[source]}
                            </Badge>
                          )}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </Card>
            );
          })}

          {/* Consent */}
          <Card padding="lg">
            <h2 className="text-base font-semibold text-[#0b2b43] mb-4">Your consent</h2>
            {consent.length === 0 && (
              <p className="text-sm text-[#475569]">No consent records found for this case.</p>
            )}
            <div className="space-y-4">
              {processingConsent && (
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-[#0f172a]">
                      Processing my data for immigration purposes
                    </p>
                    <p className="text-xs text-[#64748b] mt-0.5">
                      {processingConsent.active
                        ? `Consent given${processingConsent.consented_at ? ` on ${new Date(processingConsent.consented_at).toLocaleDateString()}` : ''}.`
                        : 'Withdrawn.'}{' '}
                      This consent is required to process your visa application.
                    </p>
                  </div>
                  <Badge variant={processingConsent.active ? 'success' : 'neutral'} size="sm">
                    {processingConsent.active ? 'Active' : 'Withdrawn'}
                  </Badge>
                </div>
              )}

              {vendorConsent && (
                <div className="flex items-start justify-between gap-4 border-t border-[#f1f5f9] pt-4">
                  <div>
                    <p className="text-sm font-medium text-[#0f172a]">
                      Sharing my data with approved immigration providers
                    </p>
                    <p className="text-xs text-[#64748b] mt-0.5">
                      {vendorConsent.active
                        ? `Consent given${vendorConsent.consented_at ? ` on ${new Date(vendorConsent.consented_at).toLocaleDateString()}` : ''}. This is optional — you can withdraw it at any time.`
                        : `Withdrawn${vendorConsent.withdrawn_at ? ` on ${new Date(vendorConsent.withdrawn_at).toLocaleDateString()}` : ''}.`}
                    </p>
                  </div>
                  {vendorConsent.active ? (
                    <Button
                      variant="outline"
                      onClick={() => void handleWithdrawVendorSharing()}
                      disabled={withdrawing}
                    >
                      {withdrawing ? 'Withdrawing…' : 'Withdraw consent'}
                    </Button>
                  ) : (
                    <Badge variant="neutral" size="sm">Withdrawn</Badge>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Export + retention */}
          <Card padding="lg">
            <h2 className="text-base font-semibold text-[#0b2b43] mb-2">Download your data</h2>
            <p className="text-sm text-[#475569] mb-4">
              Download a PDF containing all the personal data ReloPass holds for your
              immigration case, including your consent history and an access log.
            </p>
            <Button
              variant="primary"
              onClick={() => void handleDownload()}
              disabled={downloading}
            >
              {downloading ? 'Preparing…' : 'Download my data'}
            </Button>
            <p className="text-xs text-[#94a3b8] mt-4">{RETENTION_NOTICE}</p>
          </Card>

          {/* Deletion */}
          <Card padding="lg">
            <h2 className="text-base font-semibold text-[#0b2b43] mb-2">Request data deletion</h2>
            <p className="text-sm text-[#475569] mb-4">
              You can ask us to delete the personal data we hold for your immigration case.
              Your HR team will review the request.
            </p>
            <Button
              variant="outline"
              className="border-[#7a2a2a] text-[#7a2a2a] hover:bg-[#f4e9e9]"
              onClick={() => setShowDeleteModal(true)}
              aria-label="Request deletion of my immigration data"
            >
              Request data deletion
            </Button>
          </Card>
        </div>
      )}

      {/* Deletion confirmation modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
            <div className="p-6">
              <h3 id="delete-modal-title" className="text-lg font-semibold text-[#0b2b43]">
                Request deletion of your data?
              </h3>
              <div className="mt-3 rounded-lg border border-[#f4d9d9] bg-[#fdf5f5] px-4 py-3 text-sm text-[#7a2a2a] space-y-2">
                <p className="font-medium">This affects your active visa application.</p>
                <p>
                  If your immigration case is still in progress, deleting your data may stop
                  ReloPass and the immigration authorities from being able to process your
                  visa or work permit. This action cannot be undone.
                </p>
              </div>
              <p className="text-sm text-[#475569] mt-4">
                Your request will be recorded and reviewed by your HR team, who will respond
                within 30 days as required by GDPR.
              </p>
              <label className="flex items-start gap-2 mt-4 cursor-pointer">
                <Checkbox
                  checked={deleteConfirmed}
                  onChange={(e) => setDeleteConfirmed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-[#94a3b8] text-[#7a2a2a] focus:ring-[#7a2a2a]"
                />
                <span className="text-sm text-[#334155]">
                  I understand the impact and want to request deletion of my data.
                </span>
              </label>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-[#e2e8f0] px-6 py-4">
              <Button
                variant="ghost"
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteConfirmed(false);
                }}
                disabled={deleteSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="outline"
                className="border-[#7a2a2a] text-[#7a2a2a] hover:bg-[#f4e9e9]"
                onClick={() => void handleRequestDeletion()}
                disabled={!deleteConfirmed || deleteSubmitting}
              >
                {deleteSubmitting ? 'Submitting…' : 'Confirm deletion request'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default MyImmigrationData;
