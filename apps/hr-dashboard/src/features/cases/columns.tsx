import { ColumnDef } from '@tanstack/react-table';
import { StatusBadge } from './StatusBadge';
import type { CaseRow } from './types';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  // Render in user's locale, short form. Robust against bad input.
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatCorridor(row: CaseRow): string {
  if (row.corridor) return row.corridor.replace('_', ' → ');
  const origin = row.origin_country_code;
  const dest = row.dest_country_code;
  if (origin && dest) return `${origin} → ${dest}`;
  return '—';
}

export const caseColumns: ColumnDef<CaseRow>[] = [
  {
    id: 'employee',
    header: 'Employee',
    accessorFn: (row) => row.employee_name ?? row.employee_id,
    cell: ({ row }) => {
      const display = row.original.employee_name ?? row.original.employee_id;
      return <span className="font-medium text-foreground">{display}</span>;
    },
    enableSorting: true,
  },
  {
    id: 'corridor',
    header: 'Corridor',
    accessorFn: formatCorridor,
    cell: ({ row }) => (
      <span className="text-muted-foreground">{formatCorridor(row.original)}</span>
    ),
    enableSorting: true,
  },
  {
    id: 'status',
    header: 'Status',
    accessorKey: 'status',
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
    enableSorting: true,
  },
  {
    id: 'target_start_date',
    header: 'Target start',
    accessorFn: (row) => row.target_start_date ?? '',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{formatDate(row.original.target_start_date)}</span>
    ),
    enableSorting: true,
    sortDescFirst: true,
  },
  {
    id: 'updated_at',
    header: 'Last activity',
    accessorKey: 'updated_at',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{formatDate(row.original.updated_at)}</span>
    ),
    enableSorting: true,
    sortDescFirst: true,
  },
  {
    id: 'open_contradictions',
    header: 'Open',
    accessorFn: (row) => row.open_contradictions_count ?? 0,
    cell: ({ row }) => {
      const count = row.original.open_contradictions_count ?? 0;
      if (count === 0) {
        return <span className="text-muted-foreground">—</span>;
      }
      return (
        <span className="inline-flex items-center rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
          {count}
        </span>
      );
    },
    enableSorting: true,
  },
];
