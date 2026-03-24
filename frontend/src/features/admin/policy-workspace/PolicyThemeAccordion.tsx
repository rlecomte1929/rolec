import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button } from '../../../components/antigravity';
import { TermHelpIcon } from '../../policy-config/TermHelpIcon';
import { glossaryIdForBenefitKey } from '../../policy-config/compensationGlossary';
import {
  deriveRowBucket,
  deriveThemeStats,
  formatApplicabilitySummary,
  formatCapValueSummary,
  notesPreview,
  rowMatchesAssignmentFilter,
  rowMatchesFamilyFilter,
  type ThemeStats,
  type WorkspaceDisplayRow,
} from './policyWorkspaceModel';

type Props = {
  categoryKey: string;
  title: string;
  themeDescription: string;
  benefits: WorkspaceDisplayRow[];
  open: boolean;
  onToggle: () => void;
  policyEditorHref: string;
  readOnly?: boolean;
  showOnlyIncluded: boolean;
  assignmentFilter: string;
  familyFilter: string;
  onInspectRow: (row: WorkspaceDisplayRow) => void;
};

function bucketVariant(b: ReturnType<typeof deriveRowBucket>): 'success' | 'neutral' | 'warning' {
  if (b === 'included') return 'success';
  if (b === 'excluded') return 'neutral';
  return 'warning';
}

function bucketLabel(b: ReturnType<typeof deriveRowBucket>): string {
  if (b === 'included') return 'Included';
  if (b === 'excluded') return 'Excluded';
  return 'Conditional';
}

export const PolicyThemeAccordion: React.FC<Props> = ({
  categoryKey,
  title,
  themeDescription,
  benefits,
  open,
  onToggle,
  policyEditorHref,
  readOnly,
  showOnlyIncluded,
  assignmentFilter,
  familyFilter,
  onInspectRow,
}) => {
  const stats: ThemeStats = useMemo(
    () => deriveThemeStats({ category_key: categoryKey, benefits }),
    [categoryKey, benefits]
  );

  const visibleRows = useMemo(() => {
    return benefits.filter((row) => {
      if (showOnlyIncluded && deriveRowBucket(row) !== 'included') return false;
      if (!rowMatchesAssignmentFilter(row, assignmentFilter || null)) return false;
      if (!rowMatchesFamilyFilter(row, familyFilter || null)) return false;
      return true;
    });
  }, [benefits, showOnlyIncluded, assignmentFilter, familyFilter]);

  const hasAnyRows = benefits.length > 0;
  const emptyTheme = !hasAnyRows;

  return (
    <div className="border border-[#e2e8f0] rounded-lg bg-white overflow-hidden">
      <div className="flex items-stretch gap-0">
        <button
          type="button"
          onClick={onToggle}
          className="flex-1 min-w-0 flex flex-wrap items-start gap-2 px-3 py-2.5 text-left hover:bg-[#f8fafc] transition-colors"
          aria-expanded={open}
          id={`policy-theme-${categoryKey}-header`}
          aria-controls={`policy-theme-${categoryKey}-panel`}
        >
          <span
            className={`mt-0.5 shrink-0 text-[#64748b] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            aria-hidden
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-[#0b2b43]">{title}</div>
            <p className="text-xs text-[#64748b] mt-0.5 leading-snug line-clamp-2">{themeDescription}</p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1.5 text-xs text-[#64748b]">
              <span>
                <span className="text-green-700 font-medium">{stats.included}</span> included
              </span>
              <span>
                <span className="text-[#475569] font-medium">{stats.excluded}</span> excluded
              </span>
              <span>
                <span className="text-amber-800 font-medium">{stats.conditional}</span> conditional
              </span>
            </div>
          </div>
        </button>
        {!readOnly ? (
          <div className="flex items-center pr-2 py-2 shrink-0 border-l border-transparent">
            <Link
              to={policyEditorHref}
              onClick={(e) => e.stopPropagation()}
              className="text-xs font-medium text-[#0b2b43] hover:underline px-2 py-1 rounded whitespace-nowrap"
            >
              Edit theme
            </Link>
          </div>
        ) : null}
      </div>

      {open && (
        <div
          id={`policy-theme-${categoryKey}-panel`}
          role="region"
          aria-labelledby={`policy-theme-${categoryKey}-header`}
          className="border-t border-[#f1f5f9] bg-[#fafbfc]"
        >
          {emptyTheme ? (
            <p className="text-sm text-[#64748b] px-3 py-4">No structured items configured yet.</p>
          ) : visibleRows.length === 0 ? (
            <p className="text-sm text-[#64748b] px-3 py-4">No rows match the current filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs sm:text-sm">
                <thead>
                  <tr className="text-left text-[#64748b] border-b border-[#e2e8f0] bg-white">
                    <th className="py-2 pl-3 pr-2 font-medium whitespace-nowrap">Benefit</th>
                    <th className="py-2 pr-2 font-medium whitespace-nowrap">Status</th>
                    <th className="py-2 pr-2 font-medium whitespace-nowrap hidden md:table-cell">Cap / value</th>
                    <th className="py-2 pr-2 font-medium min-w-[8rem] hidden lg:table-cell">Applicability</th>
                    <th className="py-2 pr-2 font-medium min-w-[6rem] hidden xl:table-cell">Notes</th>
                    <th className="py-2 pr-3 font-medium text-right whitespace-nowrap"> </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row, idx) => {
                    const key = row.id || row.benefit_key || `row-${idx}`;
                    const bucket = deriveRowBucket(row);
                    const label = (row.benefit_label || row.benefit_key || 'Benefit').trim() || 'Benefit';
                    const glossaryId = glossaryIdForBenefitKey(row.benefit_key);
                    return (
                      <tr key={String(key)} className="border-b border-[#eef2f7] hover:bg-white/80">
                        <td className="py-2 pl-3 pr-2 align-top">
                          <span className="inline-flex items-center gap-1 flex-wrap max-w-[14rem]">
                            <span className="text-[#0b2b43] font-medium">{label}</span>
                            {glossaryId ? <TermHelpIcon glossaryId={glossaryId} className="shrink-0" /> : null}
                          </span>
                          {row._workspace_virtual ? (
                            <span className="block text-[10px] text-amber-800 mt-0.5">Baseline slot · not saved</span>
                          ) : null}
                        </td>
                        <td className="py-2 pr-2 align-top">
                          <Badge variant={bucketVariant(bucket)} size="sm">
                            {bucketLabel(bucket)}
                          </Badge>
                        </td>
                        <td className="py-2 pr-2 align-top text-[#475569] hidden md:table-cell max-w-[10rem]">
                          {formatCapValueSummary(row)}
                        </td>
                        <td className="py-2 pr-2 align-top text-[#475569] hidden lg:table-cell max-w-[14rem]">
                          {formatApplicabilitySummary(row)}
                        </td>
                        <td className="py-2 pr-2 align-top text-[#64748b] hidden xl:table-cell max-w-[12rem] truncate" title={notesPreview(row, 500)}>
                          {notesPreview(row)}
                        </td>
                        <td className="py-2 pr-3 align-top text-right">
                          <Button size="sm" variant="outline" type="button" onClick={() => onInspectRow(row)}>
                            {readOnly ? 'View' : 'Edit'}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
