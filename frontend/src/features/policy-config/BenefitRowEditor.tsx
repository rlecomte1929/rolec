import React, { useMemo } from 'react';
import { Input, Select } from '../../components/antigravity';
import type { PolicyConfigBenefitRow } from './types';
import { getBenefitDefinition, getBenefitTitle } from './benefitRowRegistry';
import { BenefitRowHelperFields } from './BenefitRowHelperFields';
import { glossaryIdForBenefitKey } from './compensationGlossary';
import { TermHelpIcon } from './TermHelpIcon';
import { validateBenefitRow } from './benefitRowValidation';
import { patchAdditionalTerms, readAdditionalTerms } from './benefitProgramDetails';
import {
  normalizeAssignmentType,
  normalizeAssignmentTypeList,
  normalizeFamilyStatus,
  normalizeFamilyStatusList,
  POLICY_ASSIGNMENT_TYPE_OPTIONS,
  POLICY_FAMILY_STATUS_OPTIONS,
  type PolicyAssignmentTypeValue,
  type PolicyFamilyStatusValue,
} from './policyTargeting';

const VALUE_TYPE_OPTIONS = [
  { value: 'none', label: 'Not a fixed amount' },
  { value: 'currency', label: 'Money amount' },
  { value: 'percentage', label: 'Percentage' },
  { value: 'text', label: 'Describe in words only' },
];

const UNIT_FREQUENCY_OPTIONS = [
  { value: 'one_time', label: 'One-time' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'per_trip', label: 'Per trip' },
  { value: 'per_day', label: 'Per day' },
  { value: 'per_dependent', label: 'Per dependent' },
  { value: 'custom', label: 'Custom (explain in notes)' },
];

type Props = {
  row: PolicyConfigBenefitRow;
  disabled: boolean;
  onChange: (next: PolicyConfigBenefitRow) => void;
  /** Dim row when HR preview filters exclude this benefit (still editable). */
  previewMuted?: boolean;
  /** Server-side validation message from last save (e.g. duplicate targeting). */
  serverError?: string;
};

const textareaClass =
  'w-full min-h-[88px] px-4 py-2 border border-[#d1d5db] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0b2b43] text-sm disabled:opacity-60';

export const BenefitRowEditor: React.FC<Props> = ({ row, disabled, onChange, previewMuted, serverError }) => {
  const def = getBenefitDefinition(row.benefit_key);
  const helper = def?.helper ?? 'none';
  const title = getBenefitTitle(row.benefit_key, row.benefit_label);
  const glossaryId = glossaryIdForBenefitKey(row.benefit_key);
  const covered = Boolean(row.covered);
  const vt = (row.value_type || 'none').toLowerCase();

  const issues = useMemo(() => validateBenefitRow(row), [row]);
  const issueByField = useMemo(() => {
    const m = new Map<string, string>();
    issues.forEach((i) => m.set(i.field, i.message));
    return m;
  }, [issues]);

  const assignmentSelected = useMemo(
    () => normalizeAssignmentTypeList(row.assignment_types),
    [row.assignment_types]
  );
  const familySelected = useMemo(() => normalizeFamilyStatusList(row.family_statuses), [row.family_statuses]);

  const droppedAssignmentTokens = useMemo(
    () => (row.assignment_types ?? []).filter((x) => !normalizeAssignmentType(x)),
    [row.assignment_types]
  );
  const droppedFamilyTokens = useMemo(
    () => (row.family_statuses ?? []).filter((x) => !normalizeFamilyStatus(x)),
    [row.family_statuses]
  );

  const toggleAssignment = (v: PolicyAssignmentTypeValue, checked: boolean) => {
    const s = new Set(assignmentSelected);
    if (checked) s.add(v);
    else s.delete(v);
    onChange({ ...row, assignment_types: Array.from(s).sort() });
  };

  const toggleFamily = (v: PolicyFamilyStatusValue, checked: boolean) => {
    const s = new Set(familySelected);
    if (checked) s.add(v);
    else s.delete(v);
    onChange({ ...row, family_statuses: Array.from(s).sort() });
  };

  const onValueTypeChange = (v: string) => {
    let next: PolicyConfigBenefitRow = { ...row, value_type: v };
    if (v === 'currency') {
      next = { ...next, percentage_value: null };
    } else if (v === 'percentage') {
      next = { ...next, amount_value: null, currency_code: null };
    } else if (v === 'text' || v === 'none') {
      next = { ...next, amount_value: null, currency_code: null, percentage_value: null };
    }
    onChange(next);
  };

  return (
    <div
      className={`rounded-lg border bg-white p-4 transition-opacity ${
        previewMuted ? 'border-dashed border-[#cbd5e1] opacity-60' : 'border-[#e2e8f0]'
      } ${disabled ? 'opacity-70' : ''}`}
    >
      <fieldset disabled={disabled} className="border-0 p-0 m-0 min-w-0 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="font-medium text-[#0b2b43] text-base">{title}</div>
              {glossaryId ? <TermHelpIcon glossaryId={glossaryId} /> : null}
            </div>
            <div className="text-xs text-[#94a3b8] font-mono mt-0.5">{row.benefit_key}</div>
            {serverError && (
              <p className="text-xs text-[#7a2a2a] mt-2 border border-[#fecaca] bg-[#fef2f2] rounded px-2 py-1">
                {serverError}
              </p>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm font-medium text-[#374151] shrink-0">
            <input
              type="checkbox"
              className="rounded border-[#cbd5e1]"
              checked={covered}
              onChange={(e) => onChange({ ...row, covered: e.target.checked })}
            />
            Covered by policy
          </label>
        </div>

        {previewMuted && (
          <p className="text-xs text-[#64748b] bg-[#fffbeb] border border-[#fde68a] rounded-lg px-3 py-2">
            Not included in the current preview selection at the top of the page. You can still edit this row; the
            policy itself does not change when you change the preview filters.
          </p>
        )}

        {!covered && (
          <p className="text-sm text-[#64748b] bg-[#f8fafc] border border-[#e2e8f0] rounded-lg px-3 py-2">
            When you are not covering this item, employees will not see it as an active allowance. Turn on
            &quot;Covered by policy&quot; to add amounts, limits, and who it applies to.
          </p>
        )}

        <div className="space-y-3 border-t border-[#e2e8f0] pt-4">
          <p className="text-sm font-medium text-[#374151]">Who this benefit applies to</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="text-xs font-medium text-[#64748b] uppercase tracking-wide">Assignment type</p>
              <div className="space-y-2">
                {POLICY_ASSIGNMENT_TYPE_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-start gap-2 text-sm text-[#374151] cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-[#cbd5e1] mt-0.5"
                      checked={assignmentSelected.includes(opt.value)}
                      onChange={(e) => toggleAssignment(opt.value, e.target.checked)}
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-[#94a3b8]">Leave all unchecked to mean every assignment type.</p>
              {droppedAssignmentTokens.length > 0 && (
                <p className="text-xs text-[#7a2a2a]">
                  Legacy values saved in the database were not recognized: {droppedAssignmentTokens.join(', ')}.
                  Re-select above and save to clean them up.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-[#64748b] uppercase tracking-wide">Family status</p>
              <div className="space-y-2">
                {POLICY_FAMILY_STATUS_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-start gap-2 text-sm text-[#374151] cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-[#cbd5e1] mt-0.5"
                      checked={familySelected.includes(opt.value)}
                      onChange={(e) => toggleFamily(opt.value, e.target.checked)}
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-[#94a3b8]">Leave all unchecked to mean every family situation.</p>
              {droppedFamilyTokens.length > 0 && (
                <p className="text-xs text-[#7a2a2a]">
                  Legacy values not recognized: {droppedFamilyTokens.join(', ')}. Re-select and save to update.
                </p>
              )}
            </div>
          </div>
        </div>

        {covered && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Select
                label="How this benefit is expressed"
                value={vt}
                onChange={onValueTypeChange}
                options={VALUE_TYPE_OPTIONS}
              />
              <Select
                label="How often it applies"
                value={row.unit_frequency || 'one_time'}
                onChange={(v) => onChange({ ...row, unit_frequency: v })}
                options={UNIT_FREQUENCY_OPTIONS}
              />
              <p className="text-xs text-[#64748b] md:col-span-2 -mt-2">
                Use <strong>Per dependent</strong> for allowances that are calculated per child or other dependent
                (for example dependent relocation or repatriation lines).
              </p>
            </div>
            {issueByField.get('unit_frequency') && (
              <p className="text-xs text-[#7a2a2a]">{issueByField.get('unit_frequency')}</p>
            )}

            {vt === 'currency' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Input
                    label="Amount or cap"
                    type="number"
                    value={row.amount_value != null ? String(row.amount_value) : ''}
                    onChange={(v) => {
                      if (v === '') {
                        onChange({ ...row, amount_value: null });
                        return;
                      }
                      const n = Number(v);
                      if (!Number.isFinite(n)) return;
                      onChange({ ...row, amount_value: n });
                    }}
                  />
                  {issueByField.get('amount_value') && (
                    <p className="text-xs text-[#7a2a2a] mt-1">{issueByField.get('amount_value')}</p>
                  )}
                </div>
                <div>
                  <Input
                    label="Currency"
                    value={row.currency_code ?? ''}
                    onChange={(v) => onChange({ ...row, currency_code: v || null })}
                  />
                  {issueByField.get('currency_code') && (
                    <p className="text-xs text-[#7a2a2a] mt-1">{issueByField.get('currency_code')}</p>
                  )}
                </div>
              </div>
            )}

            {vt === 'percentage' && (
              <div className="max-w-xs">
                <Input
                  label="Percentage of reference (0–100)"
                  type="number"
                  value={row.percentage_value != null ? String(row.percentage_value) : ''}
                  onChange={(v) => {
                    if (v === '') {
                      onChange({ ...row, percentage_value: null });
                      return;
                    }
                    const n = Number(v);
                    if (!Number.isFinite(n)) return;
                    onChange({ ...row, percentage_value: n });
                  }}
                />
                <p className="text-xs text-[#64748b] mt-1">
                  Enter a number from 0 to 100 (percent of the reference amount defined in your programme).
                </p>
                {issueByField.get('percentage_value') && (
                  <p className="text-xs text-[#7a2a2a] mt-1">{issueByField.get('percentage_value')}</p>
                )}
              </div>
            )}

            {vt === 'text' && (
              <p className="text-sm text-[#64748b]">
                Use the notes and conditions below to describe this benefit in plain language. Before publish, add
                at least a short note so employees see how the benefit works.
              </p>
            )}

            <BenefitRowHelperFields row={row} helper={helper} disabled={disabled} onChange={onChange} />

            <div className="space-y-2">
              <label className="block text-sm font-medium text-[#374151]">Notes for employees</label>
              <textarea
                className={textareaClass}
                value={row.notes ?? ''}
                onChange={(e) => onChange({ ...row, notes: e.target.value || null })}
                placeholder="Short summary employees will understand (optional)."
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-[#374151]">
                Eligibility &amp; extra conditions
              </label>
              <textarea
                className={textareaClass}
                value={readAdditionalTerms(row)}
                onChange={(e) => onChange(patchAdditionalTerms(row, e.target.value))}
                placeholder="Approval rules, carve-outs, or legal context (optional)."
              />
            </div>

          </>
        )}
      </fieldset>
    </div>
  );
};
