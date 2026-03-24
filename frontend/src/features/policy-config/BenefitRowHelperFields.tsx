import React from 'react';
import { Input, Select } from '../../components/antigravity';
import { TermHelpIcon } from './TermHelpIcon';
import type { BenefitHelperKind } from './benefitRowRegistry';
import type { PolicyConfigBenefitRow } from './types';
import {
  patchProgramDetails,
  readProgramDetails,
  patchEligibilityNotes,
  readEligibilityNotes,
  type ProgramDetails,
} from './benefitProgramDetails';

const TRAVEL_CLASS_OPTIONS = [
  { value: 'economy', label: 'Economy' },
  { value: 'premium_economy', label: 'Premium economy' },
  { value: 'business', label: 'Business' },
  { value: 'first', label: 'First class' },
];

const PAYROLL_MODE_OPTIONS = [
  { value: 'home', label: 'Home country payroll' },
  { value: 'split', label: 'Split payroll' },
  { value: 'host', label: 'Host country payroll' },
];

type Props = {
  row: PolicyConfigBenefitRow;
  helper: BenefitHelperKind;
  disabled: boolean;
  onChange: (next: PolicyConfigBenefitRow) => void;
};

function coerceFiniteNumberOrSkip(v: string, apply: (n: number | null) => void) {
  if (v === '') {
    apply(null);
    return;
  }
  const n = Number(v);
  if (!Number.isFinite(n)) return;
  apply(n);
}

export const BenefitRowHelperFields: React.FC<Props> = ({ row, helper, disabled, onChange }) => {
  const pd = readProgramDetails(row);

  if (helper === 'none') return null;

  const sectionTitle = (t: string) => (
    <h4 className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mt-2 mb-2">{t}</h4>
  );

  if (helper === 'pre_visit') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Visit details')}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            label="Number of days covered"
            type="number"
            value={pd.visit_days != null ? String(pd.visit_days) : ''}
            onChange={(v) =>
              coerceFiniteNumberOrSkip(v, (n) =>
                onChange(patchProgramDetails(row, { visit_days: n }))
              )
            }
          />
          <Select
            label="Typical travel class (guideline)"
            value={pd.travel_class ?? ''}
            onChange={(v) =>
              onChange(
                patchProgramDetails(row, {
                  travel_class: v || null,
                })
              )
            }
            options={[{ value: '', label: 'Not specified' }, ...TRAVEL_CLASS_OPTIONS]}
          />
        </div>
      </div>
    );
  }

  if (helper === 'training_hours') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Training')}
        <Input
          label="Hours included (policy guideline)"
          type="number"
          value={pd.training_hours != null ? String(pd.training_hours) : ''}
          onChange={(v) =>
            coerceFiniteNumberOrSkip(v, (n) =>
              onChange(patchProgramDetails(row, { training_hours: n }))
            )
          }
        />
      </div>
    );
  }

  if (helper === 'shipment_volume') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Shipment')}
        <Input
          label="Volume cap (e.g. 20 ft container, 15 m³)"
          value={pd.shipment_volume_cap ?? ''}
          onChange={(v) =>
            onChange(
              patchProgramDetails(row, {
                shipment_volume_cap: v || null,
              })
            )
          }
        />
      </div>
    );
  }

  if (helper === 'storage_duration_volume') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Storage')}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            label="Duration included (months)"
            type="number"
            value={pd.storage_duration_months != null ? String(pd.storage_duration_months) : ''}
            onChange={(v) =>
              coerceFiniteNumberOrSkip(v, (n) =>
                onChange(patchProgramDetails(row, { storage_duration_months: n }))
              )
            }
          />
          <Input
            label="Volume guideline"
            value={pd.storage_volume_cap ?? ''}
            onChange={(v) =>
              onChange(
                patchProgramDetails(row, {
                  storage_volume_cap: v || null,
                })
              )
            }
          />
        </div>
      </div>
    );
  }

  if (helper === 'temp_living_days') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Temporary housing')}
        <Input
          label="Maximum days covered"
          type="number"
          value={pd.temporary_living_max_days != null ? String(pd.temporary_living_max_days) : ''}
          onChange={(v) =>
            coerceFiniteNumberOrSkip(v, (n) =>
              onChange(patchProgramDetails(row, { temporary_living_max_days: n }))
            )
          }
        />
      </div>
    );
  }

  if (helper === 'child_education_tuition') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Education arrangement')}
        <label className="block text-sm font-medium text-[#374151] mb-1">
          Tuition &amp; fee difference logic (how you compare host vs home costs)
        </label>
        <textarea
          disabled={disabled}
          className="w-full min-h-[100px] px-4 py-2 border border-[#d1d5db] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0b2b43] text-sm disabled:opacity-60"
          value={readEligibilityNotes(row)}
          onChange={(e) => onChange(patchEligibilityNotes(row, e.target.value))}
          placeholder="e.g. Reimburse documented tuition difference up to cap; international schools only."
        />
      </div>
    );
  }

  if (helper === 'home_leave_trips') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Home leave')}
        <Input
          label="Round trips per year (policy guideline)"
          type="number"
          value={pd.home_leave_trips_per_year != null ? String(pd.home_leave_trips_per_year) : ''}
          onChange={(v) =>
            coerceFiniteNumberOrSkip(v, (n) =>
              onChange(patchProgramDetails(row, { home_leave_trips_per_year: n }))
            )
          }
        />
      </div>
    );
  }

  if (helper === 'extra_holiday_days') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Extra leave')}
        <Input
          label="Additional calendar days"
          type="number"
          value={pd.extra_holiday_days_count != null ? String(pd.extra_holiday_days_count) : ''}
          onChange={(v) =>
            coerceFiniteNumberOrSkip(v, (n) =>
              onChange(patchProgramDetails(row, { extra_holiday_days_count: n }))
            )
          }
        />
      </div>
    );
  }

  if (helper === 'payroll_structure') {
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        <div className="flex flex-wrap items-center gap-2 mt-2 mb-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-[#64748b] m-0">Payroll model</h4>
          <TermHelpIcon glossaryId="split_payroll" />
        </div>
        <Select
          label="Default structure (guideline)"
          value={pd.payroll_structure_mode ?? ''}
          onChange={(v) => {
            const mode = (v || null) as ProgramDetails['payroll_structure_mode'];
            onChange(patchProgramDetails(row, { payroll_structure_mode: mode }));
          }}
          options={[{ value: '', label: 'Not specified' }, ...PAYROLL_MODE_OPTIONS]}
        />
        <p className="text-xs text-[#64748b]">
          Split payroll means pay is delivered through more than one payroll or country. Pick the option that best
          matches your standard programme; employees still rely on formal letters and payroll for specifics.
        </p>
      </div>
    );
  }

  if (helper === 'banking_monthly_transfer') {
    const checked = Boolean(pd.banking_monthly_transfer_reimbursement);
    return (
      <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-3 space-y-3">
        {sectionTitle('Transfers')}
        <label className="flex items-center gap-2 text-sm text-[#374151]">
          <input
            type="checkbox"
            disabled={disabled}
            checked={checked}
            onChange={(e) =>
              onChange(
                patchProgramDetails(row, {
                  banking_monthly_transfer_reimbursement: e.target.checked ? true : null,
                })
              )
            }
          />
          Include monthly transfer / FX reimbursement (when applicable)
        </label>
      </div>
    );
  }

  return null;
};
