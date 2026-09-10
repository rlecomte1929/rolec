/**
 * ImmigrationCaseCreatePage — MVG-6A
 *
 * HR form to create an immigration case for an existing relocation case.
 * Route: /hr/immigration/new
 */

import React, { useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { hrAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import api from '../../api/client';
import type { AssignmentSummary } from '../../types';
import { getCountryName } from '../../utils/countries';

// ── Types ────────────────────────────────────────────────────────────────────

type PermitType =
  | 'eu_blue_card'
  | 'work_permit'
  | 'skilled_worker_visa'
  | 'eea_registration'
  | 'other';

const PERMIT_TYPE_LABELS: Record<PermitType, string> = {
  eu_blue_card: 'EU Blue Card',
  work_permit: 'Work Permit',
  skilled_worker_visa: 'Skilled Worker Visa',
  eea_registration: 'EEA Registration',
  other: 'Other',
};

interface FormState {
  caseId: string;
  corridorFrom: string;
  corridorTo: string;
  permitType: PermitType | '';
  partnerName: string;
  expectedSubmissionDate: string;
  expectedGrantDate: string;
}

// ── Styled primitives (native HTML, Tailwind) ─────────────────────────────────

const fieldClass =
  'w-full rounded-lg bg-[#374151] border border-[#4b5563] text-[#f1f5f9] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#3b82f6] placeholder-[#9ca3af]';

// appearance-none removes OS-native select chrome so bg/text CSS is respected on all platforms
const selectClass =
  'w-full appearance-none rounded-lg bg-[#374151] border border-[#4b5563] text-[#f1f5f9] px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-[#3b82f6] cursor-pointer';

const labelClass = 'block text-sm font-medium text-slate-500 mb-1';

// Wrapper that adds a custom dropdown chevron for appearance-none selects
const SelectWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="relative">
    {children}
    <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#64748b]">
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </span>
  </div>
);

// ── Component ────────────────────────────────────────────────────────────────

export const ImmigrationCaseCreatePage: React.FC = () => {
  const navigate = useNavigate();

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successId, setSuccessId] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    caseId: '',
    corridorFrom: '',
    corridorTo: '',
    permitType: '',
    partnerName: '',
    expectedSubmissionDate: '',
    expectedGrantDate: '',
  });

  // ── Load active assignments ─────────────────────────────────────────────

  const assignmentsQuery = useQuery({
    queryKey: ['hr', 'assignments', { limit: 100 }],
    queryFn: async () => {
      const { assignments: list } = await hrAPI.listAssignments({ limit: 100 });
      return list;
    },
  });
  const assignments: AssignmentSummary[] = assignmentsQuery.data ?? [];
  const loadingAssignments = assignmentsQuery.isLoading;
  // `error` is also written by the submit handler, so keep the local state and
  // fold the read error into what we render.
  const displayedError = error || (assignmentsQuery.isError ? 'Failed to load cases. Please refresh.' : null);

  // ── Handle case selection — auto-fill corridor ──────────────────────────

  const handleCaseSelect = useCallback(
    (caseId: string) => {
      const selected = assignments.find((a) => a.caseId === caseId);
      const from = selected?.case?.home_country ?? '';
      const to = selected?.case?.host_country ?? '';
      setForm((f) => ({ ...f, caseId, corridorFrom: from, corridorTo: to }));
    },
    [assignments],
  );

  // ── Submit ──────────────────────────────────────────────────────────────

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!form.caseId || !form.permitType) {
        setError('Please select a case and permit type.');
        return;
      }
      setSubmitting(true);
      setError(null);
      try {
        const response = await api.post<{ id: string }>('/api/hr/immigration/cases', {
          case_id: form.caseId,
          corridor_from: form.corridorFrom,
          corridor_to: form.corridorTo,
          permit_type: form.permitType,
          partner_name: form.partnerName || null,
          expected_submission_date: form.expectedSubmissionDate || null,
          expected_grant_date: form.expectedGrantDate || null,
        });
        setSuccessId(response.data.id);
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : 'Failed to create immigration case.';
        setError(msg);
      } finally {
        setSubmitting(false);
      }
    },
    [form],
  );

  // ── Success state ───────────────────────────────────────────────────────

  if (successId) {
    return (
      <AppShell title="Immigration case created">
        <div className="max-w-lg mx-auto mt-12 text-center">
          <div className="text-4xl mb-4">✅</div>
          <h2 className="text-xl font-semibold text-[#f1f5f9] mb-2">
            Immigration case created
          </h2>
          <p className="text-slate-500 mb-6">
            Track permit progress from the status timeline.
          </p>
          <div className="flex gap-3 justify-center">
            <Button
              onClick={() =>
                navigate(
                  buildRoute('hrImmigrationCase', { immigrationCaseId: successId }),
                )
              }
            >
              View status timeline
            </Button>
            <Button variant="ghost" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
              Back to command center
            </Button>
          </div>
        </div>
      </AppShell>
    );
  }

  // ── Form ────────────────────────────────────────────────────────────────

  const corridorDisplay =
    form.corridorFrom && form.corridorTo
      ? `${form.corridorFrom} → ${form.corridorTo}`
      : '—';

  return (
    <AppShell title="New immigration case">
      <div className="max-w-xl mx-auto py-8 px-4">
        <h1 className="text-2xl font-semibold text-[#f1f5f9] mb-1">
          Open immigration case
        </h1>
        <p className="text-slate-500 mb-8">
          Create a permit tracking record for an employee relocation.
        </p>

        {displayedError && (
          <div
            role="alert"
            className="mb-6 rounded-lg bg-[#450a0a] border border-[#7f1d1d] text-[#fca5a5] px-4 py-3 text-sm"
          >
            {displayedError}
          </div>
        )}

        <Card className="p-6">
          <form onSubmit={handleSubmit} noValidate className="space-y-5">

            {/* Case selector */}
            <div>
              <label htmlFor="imm-case-select" className={labelClass}>
                Relocation case <span className="text-red-400">*</span>
              </label>
              {loadingAssignments ? (
                <p className="text-[#64748b] text-sm py-2">Loading cases…</p>
              ) : (
                <SelectWrapper>
                  <select
                    id="imm-case-select"
                    value={form.caseId}
                    onChange={(e) => handleCaseSelect(e.target.value)}
                    required
                    className={selectClass}
                    aria-label="Select relocation case"
                  >
                    <option value="">Select a case…</option>
                    {assignments.map((a) => (
                      <option key={a.caseId} value={a.caseId}>
                        {[
                          a.employeeFirstName,
                          a.employeeLastName,
                          a.case?.home_country && a.case?.host_country
                            ? `(${getCountryName(a.case.home_country)} → ${getCountryName(a.case.host_country)})`
                            : '',
                        ]
                          .filter(Boolean)
                          .join(' ') || a.caseId}
                      </option>
                    ))}
                  </select>
                </SelectWrapper>
              )}
            </div>

            {/* Corridor (auto-filled read-only) */}
            <div>
              <label htmlFor="imm-corridor" className={labelClass}>
                Corridor
              </label>
              <div
                id="imm-corridor"
                className="rounded-lg bg-[#1f2937] border border-[#374151] text-gray-500 px-3 py-2 text-sm"
              >
                {corridorDisplay}
              </div>
              <p className="mt-1 text-xs text-[#475569]">
                Auto-filled from the selected case.
              </p>
            </div>

            {/* Permit type */}
            <div>
              <label htmlFor="imm-permit-type" className={labelClass}>
                Permit type <span className="text-red-400">*</span>
              </label>
              <SelectWrapper>
                <select
                  id="imm-permit-type"
                  value={form.permitType}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, permitType: e.target.value as PermitType }))
                  }
                  required
                  className={selectClass}
                  aria-label="Select permit type"
                >
                  <option value="">Select permit type…</option>
                  {(Object.keys(PERMIT_TYPE_LABELS) as PermitType[]).map((k) => (
                    <option key={k} value={k}>
                      {PERMIT_TYPE_LABELS[k]}
                    </option>
                  ))}
                </select>
              </SelectWrapper>
            </div>

            {/* Immigration partner */}
            <div>
              <label htmlFor="imm-partner" className={labelClass}>
                Immigration partner
              </label>
              <Input unstyled
                id="imm-partner"
                type="text"
                placeholder="e.g. Fragomen, KPMG Law"
                value={form.partnerName}
                onChange={(v) =>
                  setForm((f) => ({ ...f, partnerName: v }))
                }
                className={fieldClass}
                aria-label="Immigration partner name"
              />
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="imm-submission-date" className={labelClass}>
                  Expected submission
                </label>
                <Input unstyled
                  id="imm-submission-date"
                  type="date"
                  value={form.expectedSubmissionDate}
                  onChange={(v) =>
                    setForm((f) => ({ ...f, expectedSubmissionDate: v }))
                  }
                  className={fieldClass}
                  aria-label="Expected submission date"
                />
              </div>
              <div>
                <label htmlFor="imm-grant-date" className={labelClass}>
                  Expected grant
                </label>
                <Input unstyled
                  id="imm-grant-date"
                  type="date"
                  value={form.expectedGrantDate}
                  onChange={(v) =>
                    setForm((f) => ({ ...f, expectedGrantDate: v }))
                  }
                  className={fieldClass}
                  aria-label="Expected permit grant date"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <Button
                type="submit"
                disabled={submitting || !form.caseId || !form.permitType}
              >
                {submitting ? 'Creating…' : 'Create immigration case'}
              </Button>
              <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>

        <p className="mt-4 text-xs text-[#64748b]">
          No real immigration partner API — status updates are manual for the demo.
        </p>
      </div>
    </AppShell>
  );
};
