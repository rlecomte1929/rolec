import { useMemo } from 'react';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';
import { ProviderStatusCell } from '../../../components/providers/ProviderStatusCell';
import type {
  CoordinationStatus,
  ProviderGridCells,
  ProviderGridRow,
} from '../../../api/client';

/**
 * Provider Grid V2 table behind the `provider_grid_resizable` flag.
 *
 * Same 8 columns as the legacy ProviderStatusGrid:
 *   - Employee (name + identifier sub)
 *   - Destination country
 *   - Move date
 *   - Overall coordination status badge
 *   - Housing / Immigration / Shipping / Other (one ProviderStatusCell each)
 *
 * Wraps <DataTable> so columns get resize + drag-reorder + per-table
 * localStorage persistence. ProviderStatusCell is reused as-is (already
 * clickable → navigates to case detail). The legacy ProviderStatusGrid
 * stays the default rendering path when the flag is off.
 */

const COORD_BADGE: Record<CoordinationStatus, { bg: string; text: string; label: string }> = {
  'not-started': { bg: '#f3f4f6', text: '#6b7280', label: 'Not started' },
  'in-progress': { bg: '#e0f2fe', text: '#0369a1', label: 'In progress' },
  'at-risk':     { bg: '#fef3c7', text: '#92400e', label: 'At risk' },
  complete:      { bg: '#d1fae5', text: '#065f46', label: 'Complete' },
};

const PROVIDER_COLUMNS: ReadonlyArray<{ key: keyof ProviderGridCells; label: string }> = [
  { key: 'housing', label: 'Housing' },
  { key: 'immigration', label: 'Immigration' },
  { key: 'shipping', label: 'Shipping' },
  { key: 'other', label: 'Other' },
];

export interface ProviderGridV2TableProps {
  rows: ProviderGridRow[];
  emptyState?: React.ReactNode;
}

export function ProviderGridV2Table({ rows, emptyState }: ProviderGridV2TableProps) {
  const columns = useMemo<DataTableColumn<ProviderGridRow>[]>(
    () => [
      {
        id: 'employee_name',
        header: 'Employee',
        defaultWidth: 200,
        minWidth: 140,
        sortValue: (row) => row.employee_name?.toLowerCase() ?? '',
        cell: (row) => (
          <div>
            <div className="font-medium text-slate-900">{row.employee_name}</div>
            {row.employee_identifier && row.employee_identifier !== row.employee_name && (
              <div className="text-[11px] text-slate-500 mt-0.5">{row.employee_identifier}</div>
            )}
          </div>
        ),
      },
      {
        id: 'dest_country',
        header: 'Destination',
        defaultWidth: 140,
        sortValue: (row) => row.dest_country ?? '',
        cell: (row) => <span className="text-slate-700">{row.dest_country ?? '—'}</span>,
      },
      {
        id: 'move_date',
        header: 'Move date',
        defaultWidth: 130,
        sortValue: (row) => (row.move_date ? Date.parse(row.move_date) : Number.MAX_SAFE_INTEGER),
        cell: (row) => (
          <span className="text-slate-700">
            {row.move_date
              ? new Date(row.move_date).toLocaleDateString([], {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })
              : '—'}
          </span>
        ),
      },
      {
        id: 'coordination_status',
        header: 'Overall',
        defaultWidth: 140,
        sortValue: (row) => row.coordination_status ?? '',
        cell: (row) => {
          const badge = COORD_BADGE[row.coordination_status] ?? COORD_BADGE['not-started'];
          return (
            <span
              className="inline-block rounded-full px-2.5 py-0.5 text-[11.5px] font-medium"
              style={{ backgroundColor: badge.bg, color: badge.text }}
            >
              {badge.label}
            </span>
          );
        },
      },
      ...PROVIDER_COLUMNS.map<DataTableColumn<ProviderGridRow>>((col) => ({
        id: col.key,
        header: col.label,
        defaultWidth: 140,
        minWidth: 110,
        // Provider cells are status indicators — sorting alphabetically by
        // GridCellStatus string isn't meaningful. Disable sort to avoid
        // confusing clicks.
        unsortable: true,
        cell: (row) => (
          <ProviderStatusCell
            status={row.cells[col.key]}
            caseId={row.case_id}
            providerType={col.label}
          />
        ),
      })),
    ],
    [],
  );

  return (
    <DataTable
      tableId="hr.provider-grid"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.case_id}
      ariaLabel="Provider status grid (resizable)"
      emptyState={emptyState ?? 'No provider assignments yet.'}
      footerSlot={
        <div className="flex items-center justify-end px-4 py-2 text-[11.5px] text-slate-500">
          <ResetColumnsLink tableId="hr.provider-grid" />
        </div>
      }
    />
  );
}

export default ProviderGridV2Table;
