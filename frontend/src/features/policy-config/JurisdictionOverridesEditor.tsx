/**
 * Section C: editor for jurisdiction-aware overrides on a single benefit row.
 *
 * Renders inside BenefitRowEditor below the base fields. Each override row
 * is a small sub-form: country picker (multi), employee level (single,
 * optional), assignment type (single, optional), amount + currency
 * (optional — empty = inherit from base). Tier ordering inside the
 * override's cap_rule_json is enforced by the backend; we surface
 * validation errors per row when they come back.
 *
 * Markdown editor for reimbursement_md / repayment_md and FX conversion
 * hint live in PR 4 — this PR ships the structural editor.
 */
import React from 'react';
import { Input, Select } from '../../components/antigravity';
import type { PolicyJurisdictionOverride } from './types';
import {
  POLICY_ASSIGNMENT_TYPE_OPTIONS,
  POLICY_EMPLOYEE_LEVEL_OPTIONS,
} from './policyTargeting';
import { POLICY_CURRENCY_OPTIONS } from './currencyOptions';
import { CountryMultiSelect } from './CountryMultiSelect';

type Props = {
  overrides: PolicyJurisdictionOverride[];
  disabled: boolean;
  onChange: (next: PolicyJurisdictionOverride[]) => void;
};

const blankOverride = (): PolicyJurisdictionOverride => ({
  jurisdiction_countries: [],
  employee_level: null,
  assignment_type: null,
  amount_value: null,
  currency_code: null,
  cap_rule_json: {},
  reimbursement_md: null,
  repayment_md: null,
  display_order: 0,
});

export const JurisdictionOverridesEditor: React.FC<Props> = ({
  overrides,
  disabled,
  onChange,
}) => {
  const updateAt = (idx: number, patch: Partial<PolicyJurisdictionOverride>) => {
    const next = overrides.map((ov, i) => (i === idx ? { ...ov, ...patch } : ov));
    onChange(next);
  };

  const removeAt = (idx: number) => {
    onChange(overrides.filter((_, i) => i !== idx));
  };

  const add = () => {
    onChange([...overrides, blankOverride()]);
  };

  // Detect duplicate (level, assignment_type) tuples client-side — backend
  // also rejects this with a 422, but flagging early prevents a save
  // round-trip just to discover the conflict.
  const duplicateIndices = React.useMemo(() => {
    const seen = new Map<string, number>();
    const dups = new Set<number>();
    overrides.forEach((ov, i) => {
      const key = `${ov.employee_level || ''}|${ov.assignment_type || ''}`;
      if (seen.has(key)) {
        dups.add(seen.get(key) as number);
        dups.add(i);
      } else {
        seen.set(key, i);
      }
    });
    return dups;
  }, [overrides]);

  return (
    <div className="space-y-3 mt-4 pt-4 border-t border-[#e5e7eb]">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-[#0b2b43]">
            Jurisdiction overrides
          </h4>
          <p className="text-xs text-[#6b7280] mt-0.5 max-w-xl">
            Apply different caps for specific countries or employee levels.
            Empty fields inherit from the base row above. Leave blank if the
            base values apply everywhere.
          </p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={add}
            className="text-sm font-medium text-[#0b2b43] hover:underline"
          >
            + Add override
          </button>
        )}
      </div>

      {overrides.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[#cbd5e1] py-3 px-4 text-xs text-[#6b7280]">
          No overrides. Base row values apply to every employee.
        </div>
      ) : (
        <ul className="space-y-3">
          {overrides.map((ov, i) => {
            const isDup = duplicateIndices.has(i);
            return (
              <li
                key={i}
                className={`rounded-lg border bg-[#f8fafc] p-3 ${
                  isDup ? 'border-[#fca5a5] bg-[#fef2f2]' : 'border-[#e2e8f0]'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs text-[#6b7280]">
                    Override #{i + 1}
                    {isDup && (
                      <span className="ml-2 text-[#dc2626] font-medium">
                        Same level + assignment type as another override —
                        merge or change one.
                      </span>
                    )}
                  </span>
                  {!disabled && (
                    <button
                      type="button"
                      onClick={() => removeAt(i)}
                      className="text-xs text-[#dc2626] hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  <div>
                    <label className="block text-xs font-medium text-[#374151] mb-1">
                      Countries (where this override applies)
                    </label>
                    <CountryMultiSelect
                      value={ov.jurisdiction_countries || []}
                      onChange={(next) =>
                        updateAt(i, { jurisdiction_countries: next })
                      }
                      disabled={disabled}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <Select
                      label="Employee level (blank = any)"
                      value={ov.employee_level || ''}
                      onChange={(v) =>
                        updateAt(i, { employee_level: v || null })
                      }
                      options={[
                        { value: '', label: 'Any level' },
                        ...POLICY_EMPLOYEE_LEVEL_OPTIONS,
                      ]}
                      fullWidth
                    />
                    <Select
                      label="Assignment type (blank = any)"
                      value={ov.assignment_type || ''}
                      onChange={(v) =>
                        updateAt(i, { assignment_type: v || null })
                      }
                      options={[
                        { value: '', label: 'Any assignment type' },
                        ...POLICY_ASSIGNMENT_TYPE_OPTIONS,
                      ]}
                      fullWidth
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-[2fr,1fr] gap-2">
                    <Input
                      label="Override amount (blank = inherit base)"
                      type="number"
                      value={ov.amount_value != null ? String(ov.amount_value) : ''}
                      onChange={(v) => {
                        if (v === '') {
                          updateAt(i, { amount_value: null });
                          return;
                        }
                        const n = Number(v);
                        if (!Number.isFinite(n)) return;
                        updateAt(i, { amount_value: n });
                      }}
                      placeholder="e.g. 12000"
                      disabled={disabled}
                      fullWidth
                    />
                    <Select
                      label="Currency (blank = inherit)"
                      value={ov.currency_code || ''}
                      onChange={(v) =>
                        updateAt(i, { currency_code: v || null })
                      }
                      options={[
                        { value: '', label: 'Inherit base' },
                        ...POLICY_CURRENCY_OPTIONS,
                      ]}
                      fullWidth
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
