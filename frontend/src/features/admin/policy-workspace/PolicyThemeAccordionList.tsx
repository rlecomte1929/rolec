import React, { useCallback, useMemo, useState } from 'react';
import { POLICY_CONFIG_CATEGORIES } from '../../policy-config/constants';
import type { PolicyConfigCategoryBlock, PolicyConfigWorkingPayload } from '../../policy-config/types';
import { normalizeCategoryBlocks } from '../../policy-config/policyConfigUtils';
import {
  POLICY_ASSIGNMENT_TYPE_OPTIONS,
  POLICY_FAMILY_STATUS_OPTIONS,
} from '../../policy-config/policyTargeting';
import { themeDescriptionForCategoryKey } from './policyWorkspaceCanonical';
import { mergeCanonicalBaselineBlocks, type WorkspaceDisplayRow } from './policyWorkspaceModel';
import { PolicyThemeAccordion } from './PolicyThemeAccordion';
import { PolicyWorkspaceBenefitEditDrawer } from './PolicyWorkspaceBenefitEditDrawer';
import { Button, Select } from '../../../components/antigravity';

function snapshotRow(r: WorkspaceDisplayRow): WorkspaceDisplayRow {
  return JSON.parse(JSON.stringify(r)) as WorkspaceDisplayRow;
}

type Props = {
  categories: PolicyConfigCategoryBlock[] | undefined;
  policyEditorHref: string;
  readOnly?: boolean;
  assignmentTypesSupported?: string[];
  familyStatusesSupported?: string[];
  basePayload: PolicyConfigWorkingPayload | null;
  saveDraft: (override?: PolicyConfigWorkingPayload) => Promise<PolicyConfigWorkingPayload | null>;
  onRequestCreateDraft: () => Promise<void>;
  setWorkspaceError: (msg: string | null) => void;
  serverErrorsByBenefitKey: Record<string, string>;
  /** Working GET returned published read-only clone (not an editable draft). */
  matrixInspectOnly: boolean;
};

export const PolicyThemeAccordionList: React.FC<Props> = ({
  categories,
  policyEditorHref,
  readOnly,
  assignmentTypesSupported,
  familyStatusesSupported,
  basePayload,
  saveDraft,
  onRequestCreateDraft,
  setWorkspaceError,
  serverErrorsByBenefitKey,
  matrixInspectOnly,
}) => {
  const mergedBlocks = useMemo(
    () => mergeCanonicalBaselineBlocks(normalizeCategoryBlocks(categories)),
    [categories]
  );

  const allKeys = useMemo(() => mergedBlocks.map((b) => b.category_key as string), [mergedBlocks]);

  const [openKeys, setOpenKeys] = useState<Set<string>>(
    () => new Set([POLICY_CONFIG_CATEGORIES[0]?.key ?? 'pre_assignment_support'])
  );

  const [showOnlyIncluded, setShowOnlyIncluded] = useState(false);
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [familyFilter, setFamilyFilter] = useState('');
  const [inspect, setInspect] = useState<{
    row: WorkspaceDisplayRow;
    baseline: WorkspaceDisplayRow;
    categoryKey: string;
    categoryLabel: string;
  } | null>(null);

  const assignmentOptions = useMemo(() => {
    const supported = assignmentTypesSupported?.filter(Boolean) ?? [];
    const base =
      supported.length > 0
        ? POLICY_ASSIGNMENT_TYPE_OPTIONS.filter((o) => supported.includes(o.value))
        : POLICY_ASSIGNMENT_TYPE_OPTIONS;
    return base.map((o) => ({ value: o.value, label: o.label }));
  }, [assignmentTypesSupported]);

  const familyOptions = useMemo(() => {
    const supported = familyStatusesSupported?.filter(Boolean) ?? [];
    const base =
      supported.length > 0
        ? POLICY_FAMILY_STATUS_OPTIONS.filter((o) => supported.includes(o.value))
        : POLICY_FAMILY_STATUS_OPTIONS;
    return base.map((o) => ({ value: o.value, label: o.label }));
  }, [familyStatusesSupported]);

  const toggle = useCallback((key: string) => {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    setOpenKeys(new Set(allKeys.filter(Boolean)));
  }, [allKeys]);

  const collapseAll = useCallback(() => {
    setOpenKeys(new Set());
  }, []);

  const onInspectRow = useCallback((categoryKey: string, categoryLabel: string, row: WorkspaceDisplayRow) => {
    setInspect({
      row,
      baseline: snapshotRow(row),
      categoryKey,
      categoryLabel,
    });
  }, []);

  const drawerReadOnly = Boolean(readOnly || matrixInspectOnly);

  const serverError =
    inspect?.row?.benefit_key && serverErrorsByBenefitKey[inspect.row.benefit_key]
      ? serverErrorsByBenefitKey[inspect.row.benefit_key]
      : undefined;

  return (
    <div>
      <div className="mb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-[#0b2b43]">Structured baseline by theme</h2>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={expandAll}>
            Expand all
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={collapseAll}>
            Collapse all
          </Button>
          <Button
            type="button"
            size="sm"
            variant={showOnlyIncluded ? 'secondary' : 'outline'}
            onClick={() => setShowOnlyIncluded((v) => !v)}
          >
            {showOnlyIncluded ? 'Show all rows' : 'Show only included'}
          </Button>
        </div>
        </div>
        <p className="text-xs text-[#64748b] mt-2 max-w-3xl leading-snug">
          This structured baseline will govern downstream employee visibility and budget checks once published.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div className="min-w-[12rem]">
          <Select
            label="Assignment type"
            value={assignmentFilter}
            onChange={setAssignmentFilter}
            options={assignmentOptions}
            placeholder="All types"
          />
        </div>
        <div className="min-w-[12rem]">
          <Select
            label="Family status"
            value={familyFilter}
            onChange={setFamilyFilter}
            options={familyOptions}
            placeholder="All profiles"
          />
        </div>
        {(assignmentFilter || familyFilter) && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setAssignmentFilter('');
              setFamilyFilter('');
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      <div className="space-y-2">
        {mergedBlocks.map((block) => {
          const key = block.category_key ?? '';
          const def = POLICY_CONFIG_CATEGORIES.find((c) => c.key === key);
          const title = block.category_label || def?.label || key;
          const description = themeDescriptionForCategoryKey(key);
          const benefits = (block.benefits ?? []) as WorkspaceDisplayRow[];
          return (
            <PolicyThemeAccordion
              key={key}
              categoryKey={key}
              title={title}
              themeDescription={description}
              benefits={benefits}
              open={openKeys.has(key)}
              onToggle={() => toggle(key)}
              policyEditorHref={policyEditorHref}
              readOnly={drawerReadOnly}
              showOnlyIncluded={showOnlyIncluded}
              assignmentFilter={assignmentFilter}
              familyFilter={familyFilter}
              onInspectRow={(row) => onInspectRow(key, title, row)}
            />
          );
        })}
      </div>

      <PolicyWorkspaceBenefitEditDrawer
        open={Boolean(inspect)}
        onClose={() => setInspect(null)}
        categoryKey={inspect?.categoryKey ?? ''}
        categoryLabel={inspect?.categoryLabel ?? ''}
        row={inspect?.row ?? null}
        baselineRow={inspect?.baseline ?? null}
        readOnly={drawerReadOnly}
        basePayload={basePayload}
        saveDraft={saveDraft}
        onRequestCreateDraft={onRequestCreateDraft}
        setWorkspaceError={setWorkspaceError}
        serverError={serverError}
      />
    </div>
  );
};
