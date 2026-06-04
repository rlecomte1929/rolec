/**
 * ImmigrationConsentScreen — IMM-07
 *
 * GDPR consent gate shown to the employee before the immigration interview starts.
 * Two checkboxes:
 *   1. Required  — consent to process personal data for immigration purposes.
 *   2. Optional  — consent to share relevant data with approved immigration providers.
 *
 * "Continue" is disabled until the required checkbox is checked.
 * On submit, POSTs to /api/employee/cases/:caseId/consent and calls onConsented().
 *
 * If consent already exists (the parent detects it via profile fetch or status),
 * callers should skip this screen entirely by checking the `alreadyConsented` flag.
 */

import React, { useState } from 'react';
import { Alert, Card, LoadingButton } from '../../components/antigravity';
import api from '../../api/client';

interface ImmigrationConsentScreenProps {
  caseId: string;
  employeeId: string;
  onConsented: () => void;
}

const CONSENT_TEXT_VERSION = 'v1.0-2026-05';

/**
 * SHA-256 hex of the canonical consent text version string.
 * Generated once and pinned so the backend audit trail stays consistent.
 */
async function hashConsentText(version: string, purpose: string): Promise<string> {
  const enc = new TextEncoder();
  const buf = await window.crypto.subtle.digest('SHA-256', enc.encode(`${version}:${purpose}`));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export const ImmigrationConsentScreen: React.FC<ImmigrationConsentScreenProps> = ({
  caseId,
  employeeId,
  onConsented,
}) => {
  const [requiredChecked, setRequiredChecked] = useState(false);
  const [optionalChecked, setOptionalChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!requiredChecked) return;
    setSubmitting(true);
    setError(null);
    try {
      const purposes = ['immigration_processing'];
      if (optionalChecked) purposes.push('vendor_sharing');

      const consentHash = await hashConsentText(CONSENT_TEXT_VERSION, 'immigration_processing');

      await api.post(`/api/employee/cases/${caseId}/consent`, {
        employee_id: employeeId,
        purposes,
        consent_text_hash: consentHash,
      });
      onConsented();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to record consent. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <Card padding="lg">
        <div className="flex items-start gap-3 mb-5">
          <div className="mt-0.5 flex-shrink-0 rounded-full bg-[#e0f2fe] p-2">
            <svg className="h-5 w-5 text-[#0369a1]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">Immigration data consent</h2>
            <p className="text-sm text-[#475569] mt-1">
              Before we collect your immigration documents and personal details, we need your consent
              under the General Data Protection Regulation (GDPR) and applicable data protection law.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-4 text-sm text-[#334155] space-y-3 max-h-[45vh] overflow-y-auto">
          <p>
            <strong>What we collect:</strong> Passport details, date of birth, place of birth, address history,
            marital status, nationality, educational qualifications, and information about family members relocating
            with you.
          </p>
          <p>
            <strong>Why we collect it:</strong> To assess your immigration pathway, prepare visa and work permit
            applications, and support your relocation case. This data is required by immigration authorities and
            cannot be omitted.
          </p>
          <p>
            <strong>How it is stored:</strong> Your data is encrypted at rest and in transit. Sensitive fields
            (passport number, date of birth) use field-level encryption. Access is logged for audit purposes.
          </p>
          <p>
            <strong>How long we keep it:</strong> Your data will be deleted 36 months after your case closes,
            or sooner on your request.
          </p>
          <p>
            <strong>Your rights:</strong> You may request access, correction, or erasure of your data at any time
            from your account settings. Withdrawal of consent will prevent us from processing your immigration case.
          </p>
        </div>

        <div className="mt-6 space-y-4">
          {/* Required consent */}
          <label className="flex items-start gap-3 cursor-pointer group">
            <div className="mt-0.5">
              <input
                type="checkbox"
                checked={requiredChecked}
                onChange={(e) => setRequiredChecked(e.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0b2b43] focus:ring-[#0b2b43]"
              />
            </div>
            <div>
              <span className="text-sm font-medium text-[#0f172a]">
                I consent to the processing of my personal data for immigration purposes
              </span>
              <span className="ml-1.5 inline-flex items-center rounded-full bg-[#fef3c7] px-1.5 py-0.5 text-[10px] font-semibold text-[#92400e] uppercase tracking-wide">
                Required
              </span>
              <p className="text-xs text-[#64748b] mt-0.5">
                Your data will be processed by ReloPass and shared only with the relevant immigration
                authority as required to complete your visa application.
              </p>
            </div>
          </label>

          {/* Optional consent */}
          <label className="flex items-start gap-3 cursor-pointer group">
            <div className="mt-0.5">
              <input
                type="checkbox"
                checked={optionalChecked}
                onChange={(e) => setOptionalChecked(e.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0b2b43] focus:ring-[#0b2b43]"
              />
            </div>
            <div>
              <span className="text-sm font-medium text-[#0f172a]">
                I consent to sharing relevant details with approved immigration service providers
              </span>
              <span className="ml-1.5 inline-flex items-center rounded-full bg-[#f1f5f9] px-1.5 py-0.5 text-[10px] font-medium text-[#475569] uppercase tracking-wide">
                Optional
              </span>
              <p className="text-xs text-[#64748b] mt-0.5">
                Allows ReloPass to share your profile with vetted immigration lawyers or consultants
                coordinating your case. You can withdraw this consent at any time.
              </p>
            </div>
          </label>
        </div>

        {error && (
          <Alert variant="error" className="mt-4">
            {error}
          </Alert>
        )}

        <div className="mt-6 flex items-center justify-between gap-3 border-t border-[#e2e8f0] pt-4">
          <p className="text-xs text-[#94a3b8]">
            Consent recorded with version {CONSENT_TEXT_VERSION}. You can review or withdraw consent
            from your account settings.
          </p>
          <LoadingButton
            variant="primary"
            loading={submitting}
            loadingLabel="Recording consent…"
            disabled={!requiredChecked}
            onClick={handleSubmit}
          >
            I agree — continue
          </LoadingButton>
        </div>
      </Card>
    </div>
  );
};
