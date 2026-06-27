/**
 * Draft vs Live diff view (PR #4).
 *
 * Renders what changed between the current draft and the live matrix
 * version for a company, color-coded by change type, with one-click
 * per-row revert. Replaces the stub in HrPolicyPageV2's Section 4.
 *
 * Data comes from /api/hr/policy-config/diff. The component is
 * deliberately lean — it only shows summary counts + per-category
 * change lists. Full-fidelity editing still happens in the Detailed
 * review drawer; this view is for "what did I change?" glances.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { policyConfigMatrixAPI } from '../../api/client';
import {
  CollapsibleCategory,
  groupByCategory,
  shouldDefaultOpen,
} from './diffCategoryGrouping';

// --- Types ------------------------------------------------------------------

type BenefitRow = {
  id?: string | null;
  benefit_key?: string;
  benefit_label?: string;
  category?: string;
  covered?: boolean;
  amount_value?: number | null;
  currency_code?: string | null;
  percentage_value?: number | null;
  unit_frequency?: string;
  notes?: string | null;
  targeting_signature?: string;
  assignment_types?: string[];
  family_statuses?: string[];
  employee_levels?: string[];
};

type ChangedEntry = {
  before: BenefitRow;
  after: BenefitRow;
  changed_fields: string[];
};

type DiffPayload = {
  live?: { version?: { version_number?: number; status?: string; effective_date?: string } | null };
  draft?: { version?: { version_number?: number; status?: string; effective_date?: string } | null };
  diff?: {
    added: BenefitRow[];
    removed: BenefitRow[];
    changed: ChangedEntry[];
    unchanged_count: number;
    summary: { added: number; removed: number; changed: number; unchanged: number };
  };
};

type Props = {
  /** Admin impersonation. Matches the other HR-page components. */
  adminCompanyId?: string | null;
  /** Bumped by the parent when other flows (publish, normalize) change the draft. */
  refreshTrigger?: number;
};

// --- Helpers ----------------------------------------------------------------

const FIELD_LABELS: Record<string, string> = {
  benefit_label: 'Label',
  category: 'Category',
  covered: 'Covered by policy',
  value_type: 'Value type',
  amount_value: 'Amount',
  currency_code: 'Currency',
  percentage_value: 'Percentage',
  unit_frequency: 'Frequency',
  cap_rule_json: 'Cap rule',
  conditions_json: 'Conditions',
  notes: 'Notes',
  is_active: 'Active',
  display_order: 'Display order',
};

function formatAmount(row: BenefitRow): string {
  if (row.amount_value == null) return row.percentage_value != null ? `${row.percentage_value}%` : '—';
  const cur = row.currency_code ? `${row.currency_code} ` : '';
  return `${cur}${row.amount_value}${row.unit_frequency ? ` · ${row.unit_frequency}` : ''}`;
}

function rowLabel(row: BenefitRow): string {
  return row.benefit_label?.trim() || row.benefit_key?.trim() || 'Unnamed row';
}

// --- Render -----------------------------------------------------------------

type DiffSummary = NonNullable<DiffPayload['diff']>['summary'];

const SummaryBadges: React.FC<{ summary: DiffSummary | undefined }> = ({ summary }) => {
  if (!summary) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      <Badge variant="success" size="sm">+{summary.added} added</Badge>
      <Badge variant="warning" size="sm">~{summary.changed} changed</Badge>
      <Badge variant="error" size="sm">−{summary.removed} removed</Badge>
      <Badge variant="neutral" size="sm">{summary.unchanged} unchanged</Badge>
    </div>
  );
};

const AddedRow: React.FC<{
  row: BenefitRow;
  reverting: boolean;
  onRevert: () => void;
}> = ({ row, reverting, onRevert }) => (
  <li
    className="border-l-4 border-emerald-500 bg-emerald-50/60 px-3 py-2.5 rounded-r-md"
    data-testid="policy-diff-added-row"
  >
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-xs font-semibold text-emerald-800 uppercase tracking-wide">New</div>
        <div className="font-medium text-[#0b2b43]">{rowLabel(row)}</div>
        <div className="text-sm text-slate-700 mt-0.5">{formatAmount(row)}</div>
        {row.notes && <div className="text-xs text-slate-600 mt-1">{row.notes}</div>}
      </div>
      <Button size="sm" variant="outline" onClick={onRevert} disabled={reverting}>
        {reverting ? 'Reverting…' : 'Revert'}
      </Button>
    </div>
  </li>
);

const RemovedRow: React.FC<{
  row: BenefitRow;
  reverting: boolean;
  onRevert: () => void;
}> = ({ row, reverting, onRevert }) => (
  <li
    className="border-l-4 border-red-500 bg-red-50/60 px-3 py-2.5 rounded-r-md"
    data-testid="policy-diff-removed-row"
  >
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-xs font-semibold text-red-800 uppercase tracking-wide">Removed</div>
        <div className="font-medium text-[#0b2b43] line-through decoration-red-400">
          {rowLabel(row)}
        </div>
        <div className="text-sm text-slate-700 mt-0.5">
          Was: {formatAmount(row)}
        </div>
      </div>
      <Button size="sm" variant="outline" onClick={onRevert} disabled={reverting}>
        {reverting ? 'Restoring…' : 'Restore'}
      </Button>
    </div>
  </li>
);

const displayStr = (v: unknown): string => {
  if (v == null) return '—';
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
  return '—';
};

const ChangedRow: React.FC<{
  entry: ChangedEntry;
  reverting: boolean;
  onRevert: () => void;
}> = ({ entry, reverting, onRevert }) => {
  const { before, after, changed_fields } = entry;
  return (
    <li
      className="border-l-4 border-amber-500 bg-amber-50/60 px-3 py-2.5 rounded-r-md"
      data-testid="policy-diff-changed-row"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold text-amber-800 uppercase tracking-wide">Changed</div>
          <div className="font-medium text-[#0b2b43]">{rowLabel(after)}</div>
          <ul className="mt-2 space-y-1">
            {changed_fields.map((field) => {
              const lhs = (before as Record<string, unknown>)[field];
              const rhs = (after as Record<string, unknown>)[field];
              return (
                <li key={field} className="text-sm">
                  <span className="text-xs font-medium text-slate-600">
                    {FIELD_LABELS[field] ?? field}:
                  </span>{' '}
                  <span className="text-red-700 line-through decoration-red-300">
                    {displayStr(lhs)}
                  </span>{' '}
                  <span className="text-slate-500">→</span>{' '}
                  <span className="text-emerald-800 font-medium">
                    {displayStr(rhs)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
        <Button size="sm" variant="outline" onClick={onRevert} disabled={reverting}>
          {reverting ? 'Reverting…' : 'Revert'}
        </Button>
      </div>
    </li>
  );
};

// --- Main component ---------------------------------------------------------

export const PolicyDiffView: React.FC<Props> = ({ adminCompanyId, refreshTrigger }) => {
  const [payload, setPayload] = useState<DiffPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [revertingKey, setRevertingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await policyConfigMatrixAPI.hrDiff(adminCompanyId ?? undefined);
      setPayload(res);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string | { message?: string } } } };
      const d = ax.response?.data?.detail;
      setErr(
        typeof d === 'string'
          ? d
          : (d && typeof d === 'object' && 'message' in d && (d).message) ||
              'Could not load the Draft vs Live diff. Try again.'
      );
    } finally {
      setLoading(false);
    }
  }, [adminCompanyId]);

  useEffect(() => {
    void load();
  }, [load, refreshTrigger]);

  const revert = useCallback(
    async (row: { benefit_key?: string; targeting_signature?: string }) => {
      const bk = (row.benefit_key ?? '').trim();
      const ts = (row.targeting_signature ?? 'global').trim() || 'global';
      if (!bk) return;
      const key = `${bk}::${ts}`;
      setRevertingKey(key);
      setErr(null);
      try {
        const res = await policyConfigMatrixAPI.hrRevertRow(
          { benefit_key: bk, targeting_signature: ts },
          adminCompanyId ?? undefined
        );
        setPayload(res);
      } catch (e: unknown) {
        const ax = e as { response?: { data?: { detail?: string | { message?: string } } } };
        const d = ax.response?.data?.detail;
        setErr(
          typeof d === 'string'
            ? d
            : (d && typeof d === 'object' && 'message' in d && (d).message) ||
                'Revert failed. Try again.'
        );
      } finally {
        setRevertingKey(null);
      }
    },
    [adminCompanyId]
  );

  if (loading && !payload) {
    return (
      <Card padding="lg">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Draft vs Live</h2>
        <p className="text-sm text-slate-600 mt-2">Loading changes…</p>
      </Card>
    );
  }

  const diff = payload?.diff;
  const summary = diff?.summary;
  const totalChanges = summary ? summary.added + summary.removed + summary.changed : 0;

  if (!payload?.draft?.version) {
    return (
      <Card padding="lg" className="border-dashed">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Draft vs Live</h2>
        {err ? (
          <Alert variant="error" className="mt-3">
            {err}
          </Alert>
        ) : (
          <p className="text-sm text-slate-600 mt-2">
            No draft in progress. When you edit the matrix, you&apos;ll see what changed here
            before publishing.
          </p>
        )}
      </Card>
    );
  }

  const liveLabel = payload?.live?.version
    ? `Live v${payload.live.version.version_number ?? '?'}`
    : 'No live version';
  const draftLabel = `Draft v${payload.draft.version.version_number ?? '?'}`;

  return (
    <Card padding="lg">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[#0b2b43]">
            Draft vs Live — {draftLabel} vs {liveLabel}
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            Preview of every change your draft introduces before employees see it. Revert
            any row back to the live value; the draft is updated in place.
          </p>
          <SummaryBadges summary={summary} />
        </div>
        <Button size="sm" variant="outline" onClick={() => void load()} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {err && (
        <Alert variant="error" className="mt-4">
          {err}
        </Alert>
      )}

      {totalChanges === 0 ? (
        <p className="text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-3 py-2 mt-4">
          Your draft matches the live version field-for-field. Nothing to publish yet —
          edit rows in the Detailed review below to build your next version.
        </p>
      ) : (
        <div className="mt-4 space-y-6">
          {diff!.changed.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">
                Changed rows ({diff!.changed.length})
              </h3>
              <div className="space-y-2">
                {groupByCategory(diff!.changed, (e) => e.after.category).map((group) => (
                  <CollapsibleCategory
                    key={group.key}
                    group={group}
                    accentClassName="border-l-4 border-l-amber-400"
                    defaultOpen={shouldDefaultOpen(diff!.changed.length)}
                    testId="policy-diff-changed-group"
                    renderRow={(entry) => {
                      const key = `${entry.after.benefit_key}::${entry.after.targeting_signature ?? 'global'}`;
                      return (
                        <ChangedRow
                          entry={entry}
                          reverting={revertingKey === key}
                          onRevert={() => void revert(entry.after)}
                        />
                      );
                    }}
                  />
                ))}
              </div>
            </section>
          )}

          {diff!.added.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">
                Added rows ({diff!.added.length})
              </h3>
              <div className="space-y-2">
                {groupByCategory(diff!.added, (r) => r.category).map((group) => (
                  <CollapsibleCategory
                    key={group.key}
                    group={group}
                    accentClassName="border-l-4 border-l-emerald-400"
                    defaultOpen={shouldDefaultOpen(diff!.added.length)}
                    testId="policy-diff-added-group"
                    renderRow={(row) => {
                      const key = `${row.benefit_key}::${row.targeting_signature ?? 'global'}`;
                      return (
                        <AddedRow
                          row={row}
                          reverting={revertingKey === key}
                          onRevert={() => void revert(row)}
                        />
                      );
                    }}
                  />
                ))}
              </div>
            </section>
          )}

          {diff!.removed.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">
                Removed rows ({diff!.removed.length})
              </h3>
              <div className="space-y-2">
                {groupByCategory(diff!.removed, (r) => r.category).map((group) => (
                  <CollapsibleCategory
                    key={group.key}
                    group={group}
                    accentClassName="border-l-4 border-l-red-400"
                    defaultOpen={shouldDefaultOpen(diff!.removed.length)}
                    testId="policy-diff-removed-group"
                    renderRow={(row) => {
                      const key = `${row.benefit_key}::${row.targeting_signature ?? 'global'}`;
                      return (
                        <RemovedRow
                          row={row}
                          reverting={revertingKey === key}
                          onRevert={() => void revert(row)}
                        />
                      );
                    }}
                  />
                ))}
              </div>
            </section>
          )}

          <p className="text-xs text-slate-500">
            {diff!.unchanged_count} unchanged rows not shown.
          </p>
        </div>
      )}
    </Card>
  );
};
