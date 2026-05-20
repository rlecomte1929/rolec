import { useMemo } from 'react';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';
import type { CompanyV2 } from './adapter';
import { RowActionMenu } from './RowActionMenu';
import {
  CompanyLogo,
  PLAN_PILL,
  Pill,
  SeatCell,
  STATUS_DOT,
  STATUS_PILL,
  relativeDate,
} from './CompaniesV2';

/**
 * `CompaniesV2` table behind the `platform_v2_companies_resizable` flag.
 *
 * Same visual cells as the legacy V2 table (gradient logos, pills, seat bars,
 * row action menu) — just wrapped in <DataTable> so columns get the
 * resize + drag-reorder + per-table localStorage persistence.
 *
 * Parent (`CompaniesV2`) still owns:
 *   - filter state (rows arrive pre-filtered)
 *   - active-row state for the slide-out detail panel
 *   - busyId state for in-flight archive/delete spinners
 *   - the modal mount points (Add / Edit / Delete dialog)
 *
 * Flag-off path remains untouched — that's still rendered by the hand-written
 * <table> inside CompaniesV2.tsx.
 */
export interface CompaniesV2TableProps {
  rows: CompanyV2[];
  activeId: string | null;
  busyId: string | null;
  emptyState?: React.ReactNode;
  onRowClick: (c: CompanyV2) => void;
  onEdit: (c: CompanyV2) => void;
  onArchive: (c: CompanyV2) => void;
  onDelete: (c: CompanyV2) => void;
}

export function CompaniesV2Table({
  rows,
  activeId,
  busyId,
  emptyState,
  onRowClick,
  onEdit,
  onArchive,
  onDelete,
}: CompaniesV2TableProps) {
  const columns = useMemo<DataTableColumn<CompanyV2>[]>(
    () => [
      {
        id: 'name',
        header: 'Company',
        defaultWidth: 220,
        minWidth: 150,
        cell: (c) => (
          <div className="flex items-center gap-2.5">
            <CompanyLogo name={c.name} tone={c.tone} />
            <div className="min-w-0">
              <div className="font-medium text-slate-900 truncate">{c.name}</div>
              {c.legal_name && c.legal_name !== c.name && (
                <div className="text-xs text-slate-500 truncate">{c.legal_name}</div>
              )}
            </div>
          </div>
        ),
      },
      {
        id: 'plan',
        header: 'Plan',
        defaultWidth: 100,
        minWidth: 80,
        cell: (c) => <Pill className={PLAN_PILL[c.plan_tier]}>{c.plan_tier}</Pill>,
      },
      {
        id: 'status',
        header: 'Status',
        defaultWidth: 120,
        minWidth: 90,
        cell: (c) => (
          <Pill className={STATUS_PILL[c.status]}>
            <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[c.status]}`} />
            {c.status}
          </Pill>
        ),
      },
      {
        id: 'country',
        header: 'Country',
        defaultWidth: 130,
        cell: (c) => <span className="text-slate-700">{c.country ?? '—'}</span>,
      },
      {
        id: 'size',
        header: 'Size',
        defaultWidth: 100,
        cell: (c) => <span className="text-slate-700">{c.size_band ?? '—'}</span>,
      },
      {
        id: 'hr_seats',
        header: 'HR seats',
        defaultWidth: 140,
        minWidth: 110,
        cell: (c) => <SeatCell count={c.hr_users_count} limit={c.hr_seat_limit} />,
      },
      {
        id: 'employee_seats',
        header: 'Employee seats',
        defaultWidth: 160,
        minWidth: 130,
        cell: (c) => <SeatCell count={c.employee_count} limit={c.employee_seat_limit} />,
      },
      {
        id: 'cases',
        header: 'Cases',
        defaultWidth: 80,
        minWidth: 60,
        cellClassName: 'text-right',
        cell: (c) => (
          <span className="font-semibold tabular-nums text-slate-700">{c.assignments_count}</span>
        ),
      },
      {
        id: 'contact',
        header: 'Contact',
        defaultWidth: 170,
        cell: (c) => (
          <>
            <div className="text-slate-700">{c.primary_contact_name ?? '—'}</div>
            {c.hr_contact && (
              <div className="text-xs text-slate-500 truncate max-w-[14rem]">{c.hr_contact}</div>
            )}
          </>
        ),
      },
      {
        id: 'created',
        header: 'Created',
        defaultWidth: 110,
        cell: (c) => <span className="text-xs text-slate-500">{relativeDate(c.created_at)}</span>,
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">Actions</span>,
        defaultWidth: 56,
        minWidth: 56,
        maxWidth: 56,
        unsortable: true,
        // Actions column stays pinned at the right — drag-reordering it would
        // be confusing UX (where do you drop "actions"?).
        unmovable: true,
        cellClassName: 'text-right',
        cell: (c) =>
          busyId === c.id ? (
            <span className="text-[11px] text-slate-400">…</span>
          ) : (
            <RowActionMenu
              onEdit={() => onEdit(c)}
              onArchive={() => onArchive(c)}
              onDelete={() => onDelete(c)}
              disableArchive={c.status === 'archived'}
              ariaLabel={`Open actions for ${c.name}`}
            />
          ),
      },
    ],
    [busyId, onEdit, onArchive, onDelete],
  );

  return (
    <DataTable
      tableId="admin.companies-v2"
      columns={columns}
      rows={rows}
      onRowClick={onRowClick}
      isRowActive={(c) => c.id === activeId}
      rowKey={(c) => c.id}
      ariaLabel="Companies table (resizable)"
      emptyState={emptyState ?? 'No companies match your filters.'}
      footerSlot={
        <div className="flex items-center justify-end px-4 py-2 text-[11.5px] text-slate-500">
          <ResetColumnsLink tableId="admin.companies-v2" />
        </div>
      }
    />
  );
}

export default CompaniesV2Table;
