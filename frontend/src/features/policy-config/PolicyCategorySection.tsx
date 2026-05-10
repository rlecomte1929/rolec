import React, { useMemo, useState } from 'react';
import { BenefitRowEditor } from './BenefitRowEditor';
import type { PolicyConfigBenefitRow, PolicyConfigCategoryBlock } from './types';
import { rowMatchesTargetingPreview } from './policyTargeting';

type Props = {
  block: PolicyConfigCategoryBlock;
  disabled: boolean;
  assignmentTypeFilter: string | null;
  familyStatusFilter: string | null;
  onBenefitChange: (categoryKey: string, prev: PolicyConfigBenefitRow, next: PolicyConfigBenefitRow) => void;
  serverErrorsByBenefitKey?: Record<string, string>;
};

export const PolicyCategorySection: React.FC<Props> = ({
  block,
  disabled,
  assignmentTypeFilter,
  familyStatusFilter,
  onBenefitChange,
  serverErrorsByBenefitKey = {},
}) => {
  const [open, setOpen] = useState(true);
  const title = block.category_label || block.category_key || 'Category';

  const rows = block.benefits ?? [];
  const hasPreviewFilter = Boolean(assignmentTypeFilter || familyStatusFilter);

  const matchingCount = useMemo(() => {
    if (!hasPreviewFilter) return rows.length;
    return rows.filter((r) =>
      rowMatchesTargetingPreview(r.assignment_types, r.family_statuses, assignmentTypeFilter, familyStatusFilter)
    ).length;
  }, [rows, hasPreviewFilter, assignmentTypeFilter, familyStatusFilter]);

  return (
    <div className="border border-[#e2e8f0] rounded-xl bg-[#fafbfc] overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left bg-white hover:bg-[#f8fafc] border-b border-[#e2e8f0]"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="font-semibold text-[#0b2b43]">{title}</span>
        <span className="text-sm text-[#64748b]">
          {rows.length} benefit{rows.length === 1 ? '' : 's'}
          {hasPreviewFilter ? ` · ${matchingCount} match preview` : ''}
          {open ? ' ▲' : ' ▼'}
        </span>
      </button>
      {open && (
        <div className="p-4 space-y-4">
          {rows.length === 0 ? (
            <p className="text-sm text-[#64748b]">No benefits in this section.</p>
          ) : (
            rows.map((row) => {
              const matchesPreview = rowMatchesTargetingPreview(
                row.assignment_types,
                row.family_statuses,
                assignmentTypeFilter,
                familyStatusFilter
              );
              return (
                <BenefitRowEditor
                  key={`${row.benefit_key}-${row.targeting_signature ?? 'global'}`}
                  row={row}
                  disabled={disabled}
                  previewMuted={hasPreviewFilter && !matchesPreview}
                  serverError={
                    row.benefit_key ? serverErrorsByBenefitKey[row.benefit_key] : undefined
                  }
                  onChange={(next) => {
                    const ck = block.category_key;
                    if (ck) onBenefitChange(ck, row, next);
                  }}
                />
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
