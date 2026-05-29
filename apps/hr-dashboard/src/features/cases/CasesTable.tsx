import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { cn } from '../../lib/utils';
import { caseColumns } from './columns';
import type { CaseRow } from './types';

interface CasesTableProps {
  rows: CaseRow[];
}

const ROW_HEIGHT_PX = 56;
const TABLE_HEIGHT_PX = 640;

/**
 * Virtualized case table. Sort by clicking column headers; clicking a row
 * navigates to /cases/:id. Virtualization uses @tanstack/react-virtual so
 * 1,000+ rows render without scroll jank.
 *
 * Keyboard a11y: each row is a button-role element with tabIndex, and Enter /
 * Space activate the same navigation as a click. This is consistent with the
 * design system's "row-as-action" pattern and avoids the no-clickable-div
 * lint rule (rows render an <a> via React Router for actual semantics).
 */
export function CasesTable({ rows }: CasesTableProps): JSX.Element {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'target_start_date', desc: true },
  ]);

  const table = useReactTable({
    data: rows,
    columns: caseColumns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const sortedRows = table.getRowModel().rows;
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 8,
  });

  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      {/* Header row sits OUTSIDE the scrollable region so it stays pinned. */}
      <div
        role="row"
        className="grid grid-cols-[1.6fr_1fr_0.9fr_0.9fr_0.9fr_0.6fr] border-b border-border bg-muted/40 px-4"
      >
        {table.getHeaderGroups()[0]?.headers.map((header) => {
          const isSortable = header.column.getCanSort();
          const sorted = header.column.getIsSorted();
          return (
            <button
              key={header.id}
              type="button"
              role="columnheader"
              onClick={isSortable ? header.column.getToggleSortingHandler() : undefined}
              className={cn(
                'flex items-center gap-1 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground',
                isSortable && 'cursor-pointer hover:text-foreground transition-colors',
              )}
            >
              {flexRender(header.column.columnDef.header, header.getContext())}
              {isSortable ? (
                sorted === 'asc' ? (
                  <ArrowUp className="h-3 w-3" aria-hidden="true" />
                ) : sorted === 'desc' ? (
                  <ArrowDown className="h-3 w-3" aria-hidden="true" />
                ) : (
                  <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden="true" />
                )
              ) : null}
            </button>
          );
        })}
      </div>

      {/* Virtualized body. */}
      <div
        ref={scrollRef}
        className="overflow-auto"
        style={{ height: `${TABLE_HEIGHT_PX}px` }}
        role="rowgroup"
        aria-label="Cases"
      >
        <div
          style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = sortedRows[virtualRow.index];
            if (!row) return null;
            return (
              <div
                key={row.id}
                role="row"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                  height: `${ROW_HEIGHT_PX}px`,
                }}
                className={cn(
                  'grid grid-cols-[1.6fr_1fr_0.9fr_0.9fr_0.9fr_0.6fr] items-center gap-2 border-b border-border px-4 text-sm',
                  'cursor-pointer transition-colors hover:bg-muted/40 focus-within:bg-muted/40',
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <button
                    key={cell.id}
                    type="button"
                    role="cell"
                    onClick={() => navigate(`/cases/${row.original.id}`)}
                    className="flex h-full items-center text-left"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
