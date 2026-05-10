/**
 * Read-only theme-level drill-down for HR Policy Section 2
 * ("What employees see today") — PR #2 of the policy-page redesign.
 *
 * PR #1 shipped a collapsed one-row-per-theme summary. This component
 * adds expansion: click a theme to see the actual benefit rows in it
 * (label, status chip, cap, applicability, notes) without jumping to
 * the Detailed review drawer. Pure presentation — no editing, no
 * server calls. When HR actually wants to change a row, the existing
 * "View details" button into the Detailed review drawer is still the
 * path.
 *
 * We deliberately do NOT reuse the admin PolicyThemeAccordionList
 * here. That component is coupled to admin-editing props
 * (saveDraft, serverErrorsByBenefitKey, PolicyWorkspaceBenefitEditDrawer,
 * ...). Dragging those into HR read-only surfaces would be cross-
 * feature coupling for no gain. The rows shown here are a tight subset
 * HR actually glances at.
 */
import React, { useMemo, useState } from 'react';
import { Badge, Button } from '../../components/antigravity';
import type {
  PolicyConfigBenefitRow,
  PolicyConfigCategoryBlock,
  PolicyConfigWorkingPayload,
} from '../policy-config/types';
import { referenceToElementId } from './policyAssistantCitations';
import {
  humanizeAssignmentTypeLabel,
  humanizeFamilyStatusLabel,
  humanizeEmployeeLevelLabel,
} from '../policy-config/policyTargeting';

// --- helpers ---------------------------------------------------------------

function formatCap(row: PolicyConfigBenefitRow): string {
  if (row.amount_value != null && row.amount_value !== 0) {
    const cur = row.currency_code ? `${row.currency_code} ` : '';
    return `${cur}${row.amount_value}${row.unit_frequency ? ` · ${row.unit_frequency}` : ''}`;
  }
  if (row.percentage_value != null) {
    return `${row.percentage_value}%${row.unit_frequency ? ` · ${row.unit_frequency}` : ''}`;
  }
  return '—';
}

function applicabilityLabel(row: PolicyConfigBenefitRow): string {
  const parts: string[] = [];
  const at = row.assignment_types ?? [];
  const fs = row.family_statuses ?? [];
  const el = row.employee_levels ?? [];
  if (at.length) parts.push(at.map((v) => humanizeAssignmentTypeLabel(v)).join(', '));
  if (fs.length) parts.push(fs.map((v) => humanizeFamilyStatusLabel(v)).join(', '));
  if (el.length) parts.push(el.map((v) => humanizeEmployeeLevelLabel(v)).join(', '));
  return parts.length ? parts.join(' · ') : 'All assignments & profiles';
}

function statusForRow(row: PolicyConfigBenefitRow): {
  label: string;
  variant: 'success' | 'neutral' | 'warning';
} {
  const conditional =
    row.conditions_json && Object.keys(row.conditions_json).length > 0;
  if (row.covered === false) return { label: 'Excluded', variant: 'neutral' };
  if (conditional) return { label: 'Conditional', variant: 'warning' };
  return { label: 'Included', variant: 'success' };
}

// --- Types -----------------------------------------------------------------

type Props = {
  matrixPayload: PolicyConfigWorkingPayload | null;
  /** "Dive deeper" button — opens the Detailed review drawer on the parent.
   *  Omit on read-only surfaces (e.g. the employee policy page) where there
   *  is no editing drawer to open. */
  onRequestDetails?: () => void;
  /** Override the default heading. Employee surface uses
   *  "Your benefits at a glance"; HR keeps "What employees see today". */
  heading?: string;
  /** Override the subtitle. Same rationale as `heading`. */
  subtitle?: string;
};

// --- Component -------------------------------------------------------------

export const PolicyTopicSummaryList: React.FC<Props> = ({
  matrixPayload,
  onRequestDetails,
  heading = 'What employees see today',
  subtitle = 'Summary of the currently live relocation policy by theme. Click a theme to see its individual benefit rows — read-only here. Edits happen in the Detailed review drawer.',
}) => {
  const themes = useMemo(() => {
    const cats: PolicyConfigCategoryBlock[] = matrixPayload?.categories ?? [];
    return cats.map((c) => {
      const rows: PolicyConfigBenefitRow[] = c.benefits ?? [];
      const included = rows.filter((r) => r.covered).length;
      const excluded = rows.filter((r) => r.covered === false).length;
      const conditional = rows.filter(
        (r) => r.conditions_json && Object.keys(r.conditions_json).length > 0
      ).length;
      return {
        key: c.category_key ?? '',
        label: c.category_label ?? c.category_key ?? '',
        included,
        excluded,
        conditional,
        total: rows.length,
        rows,
      };
    });
  }, [matrixPayload]);

  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  if (themes.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-semibold text-[#0b2b43]">{heading}</h2>
        <p className="text-sm text-slate-600 mt-2">
          No structured matrix has been published yet. Build your first version below.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[#0b2b43]">{heading}</h2>
        {onRequestDetails && (
          <Button size="sm" variant="outline" onClick={onRequestDetails}>
            View details
          </Button>
        )}
      </div>
      <p className="text-sm text-slate-600 mt-1.5">{subtitle}</p>
      <ul className="mt-4 divide-y divide-slate-200" data-testid="policy-topic-summary-list">
        {themes.map((t) => {
          const isOpen = openKeys.has(t.key);
          return (
            <li key={t.key} className="py-1">
              <button
                type="button"
                onClick={() => toggle(t.key)}
                aria-expanded={isOpen}
                aria-controls={`topic-panel-${t.key}`}
                className="w-full flex items-center justify-between gap-3 py-1.5 text-left hover:bg-slate-50 rounded px-2"
              >
                <span className="flex items-center gap-2 min-w-0">
                  <span className="text-slate-500 w-3 text-center" aria-hidden>
                    {isOpen ? '▾' : '▸'}
                  </span>
                  <span className="font-medium text-[#0b2b43]">{t.label}</span>
                </span>
                <span className="flex items-center gap-2 text-xs shrink-0">
                  <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-medium">
                    {t.included} incl
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    {t.excluded} excl
                  </span>
                  {t.conditional > 0 && (
                    <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800">
                      {t.conditional} cond
                    </span>
                  )}
                </span>
              </button>
              {isOpen && (
                <div
                  id={`topic-panel-${t.key}`}
                  role="region"
                  aria-labelledby={`topic-header-${t.key}`}
                  className="mt-2 ml-6 border-l-2 border-slate-200 pl-4"
                >
                  {t.rows.length === 0 ? (
                    <p className="text-sm text-slate-500 py-2">
                      No structured rows under this theme yet.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {t.rows.map((row) => {
                        const st = statusForRow(row);
                        // Mirrors the RAG indexer's source_ref so Policy
                        // Assistant citation chips can scroll to this row.
                        const sourceRef = row.id ? `policy_config_benefits.${row.id}` : undefined;
                        // Anchor for Policy Assistant citation deep-linking
                        // (evidence.reference == benefit_key for matrix rows).
                        const policyAnchorId = row.benefit_key
                          ? referenceToElementId(row.benefit_key)
                          : undefined;
                        return (
                          <li
                            id={policyAnchorId}
                            key={`${row.benefit_key}-${row.targeting_signature ?? 'global'}`}
                            className="bg-slate-50/60 rounded-md px-3 py-2 border border-slate-200"
                            data-testid="policy-topic-row"
                            data-policy-source-ref={sourceRef}
                            data-policy-reference={row.benefit_key || undefined}
                          >
                            <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                              <div className="min-w-0 flex-1">
                                <div className="font-medium text-sm text-[#0b2b43]">
                                  {row.benefit_label ?? row.benefit_key ?? 'Unnamed row'}
                                </div>
                                <div className="text-xs text-slate-600 mt-0.5">
                                  Applies to: {applicabilityLabel(row)}
                                </div>
                                {row.notes && (
                                  <div className="text-xs text-slate-700 mt-1 italic">
                                    {row.notes}
                                  </div>
                                )}
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <Badge variant={st.variant} size="sm">
                                  {st.label}
                                </Badge>
                                <span className="text-sm text-slate-800 font-medium">
                                  {formatCap(row)}
                                </span>
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};
