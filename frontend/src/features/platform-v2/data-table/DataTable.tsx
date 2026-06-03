import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type Header,
  type Row,
  type SortingState,
} from '@tanstack/react-table';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { restrictToHorizontalAxis } from '@dnd-kit/modifiers';
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { loadLayout, resetLayout, saveLayout, type ColumnLayout } from './persistence';

/**
 * <DataTable> — reusable resizable + drag-reorderable column table.
 *
 * Wraps @tanstack/react-table for column model + sort + resize, and
 * @dnd-kit/sortable for column drag-reorder. Layout (order + widths)
 * persists to localStorage per `tableId`.
 *
 * Migration model — DO NOT replace tables proactively. Migrate one
 * table at a time as you're actively working on it. Tables that work
 * fine as plain HTML stay as plain HTML.
 *
 * Pattern of use:
 *
 *   const cols: DataTableColumn<Row>[] = useMemo(() => [
 *     { id: 'name', header: 'Name', cell: (r) => r.name, defaultWidth: 240 },
 *     { id: 'plan', header: 'Plan', cell: (r) => r.plan, defaultWidth: 100 },
 *   ], []);
 *
 *   <DataTable tableId="admin.companies" columns={cols} rows={data} />
 */

// ── Public column shape ─────────────────────────────────────────────────────

export interface DataTableColumn<T> {
  /** Stable id used for layout persistence + drag. Don't rename casually. */
  id: string;
  /** Header label (string) or render function. */
  header: string | (() => React.ReactNode);
  /** Cell renderer — receives the full row object. */
  cell: (row: T) => React.ReactNode;
  /**
   * Value used to sort this column. Provide it to make the column sortable;
   * omit it (or set `unsortable`) for display-only columns. Required because
   * `cell` returns opaque ReactNode — TanStack needs a primitive accessor to
   * sort by, otherwise the column is a non-sortable display column.
   */
  sortValue?: (row: T) => string | number | null | undefined;
  /** Default pixel width before the user resizes. */
  defaultWidth?: number;
  /** Minimum pixel width when resizing. */
  minWidth?: number;
  /** Maximum pixel width when resizing. */
  maxWidth?: number;
  /** Disable sorting on this column (default: sortable). */
  unsortable?: boolean;
  /** Disable drag-reorder for this column (e.g. checkbox / actions column). */
  unmovable?: boolean;
  /** className applied to <td> for alignment etc. */
  cellClassName?: string;
}

// ── Component ──────────────────────────────────────────────────────────────

export interface DataTableProps<T> {
  /** Stable id used for layout persistence. e.g. "admin.companies". */
  tableId: string;
  /** Column config. Pass a memoised array. */
  columns: DataTableColumn<T>[];
  /** Row data. Pass a memoised array. */
  rows: T[];
  /** Row click handler. If provided, rows get hover + cursor:pointer. */
  onRowClick?: (row: T) => void;
  /** When true, a row gets the `is-active` styling. */
  isRowActive?: (row: T) => boolean;
  /** Optional stable key extractor (defaults to JSON.stringify of the row). */
  rowKey?: (row: T) => string;
  /** Aria-label for the table. */
  ariaLabel?: string;
  /** Render below the table — useful for "reset columns" link. */
  footerSlot?: React.ReactNode;
  /** Empty-state node when rows.length === 0. */
  emptyState?: React.ReactNode;
}

export function DataTable<T>({
  tableId,
  columns,
  rows,
  onRowClick,
  isRowActive,
  rowKey,
  ariaLabel,
  footerSlot,
  emptyState,
}: DataTableProps<T>) {
  // ── Hydrate layout from localStorage on mount ────────────────────────────
  const initialOrder = useMemo(() => {
    const stored = loadLayout(tableId)?.order;
    // Only keep ids that still exist in the current column config (renames
    // or removals make stored ids stale).
    if (stored) {
      const known = new Set(columns.map((c) => c.id));
      const filtered = stored.filter((id) => known.has(id));
      // Append any new columns at the end so renames/adds don't lose them.
      for (const c of columns) if (!filtered.includes(c.id)) filtered.push(c.id);
      return filtered;
    }
    return columns.map((c) => c.id);
  }, [tableId, columns]);

  const [columnOrder, setColumnOrder] = useState<string[]>(initialOrder);
  const [columnSizing, setColumnSizing] = useState<Record<string, number>>(() => {
    return loadLayout(tableId)?.widths ?? {};
  });
  const [sorting, setSorting] = useState<SortingState>([]);

  // Persist on change. Wrapped in a ref-guarded effect to skip the initial render.
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const layout: ColumnLayout = { order: columnOrder, widths: columnSizing };
    saveLayout(tableId, layout);
  }, [tableId, columnOrder, columnSizing]);

  // ── Build TanStack column defs from our public shape ─────────────────────
  const tanColumns = useMemo<ColumnDef<T>[]>(() => {
    return columns.map<ColumnDef<T>>((c) => {
      // A column is sortable only when it exposes a primitive sort value.
      // Without an accessor TanStack treats it as a display column and
      // getCanSort() is false, so the header renders no sort affordance.
      const sortable = !c.unsortable && !!c.sortValue;
      return {
        id: c.id,
        header: typeof c.header === 'string' ? c.header : c.header,
        cell: (info) => c.cell(info.row.original),
        ...(c.sortValue ? { accessorFn: c.sortValue } : {}),
        enableSorting: sortable,
        enableResizing: true,
        size: c.defaultWidth ?? 160,
        minSize: c.minWidth ?? 60,
        maxSize: c.maxWidth ?? 800,
      };
    });
  }, [columns]);

  const table = useReactTable<T>({
    data: rows,
    columns: tanColumns,
    state: { columnOrder, columnSizing, sorting },
    onColumnOrderChange: setColumnOrder,
    onColumnSizingChange: setColumnSizing,
    onSortingChange: setSorting,
    columnResizeMode: 'onChange',
    enableColumnResizing: true,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // ── dnd-kit for header drag-reorder ──────────────────────────────────────
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const oldIndex = columnOrder.indexOf(active.id as string);
      const newIndex = columnOrder.indexOf(over.id as string);
      if (oldIndex < 0 || newIndex < 0) return;
      // Don't allow moving past or onto an `unmovable` column.
      const targetCol = columns.find((c) => c.id === over.id);
      if (targetCol?.unmovable) return;
      setColumnOrder(arrayMove(columnOrder, oldIndex, newIndex));
    },
    [columnOrder, columns],
  );

  // ── Compute total width from header sizing ───────────────────────────────
  const totalWidth = table.getCenterTotalSize();

  // ── Empty state ──────────────────────────────────────────────────────────
  if (rows.length === 0 && emptyState) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="p-8 text-center text-sm text-slate-400">{emptyState}</div>
        {footerSlot}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto rounded-xl">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={[restrictToHorizontalAxis]}
          onDragEnd={handleDragEnd}
        >
          <table
            role="table"
            aria-label={ariaLabel}
            className="text-[13px]"
            style={{ width: totalWidth, minWidth: '100%' }}
          >
            <thead className="bg-slate-50/80 text-left text-[10.5px] font-semibold uppercase tracking-widest text-slate-500">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  <SortableContext
                    items={columnOrder}
                    strategy={horizontalListSortingStrategy}
                  >
                    {headerGroup.headers.map((header) => {
                      const col = columns.find((c) => c.id === header.column.id);
                      return (
                        <DraggableHeaderCell
                          key={header.id}
                          header={header}
                          unmovable={col?.unmovable}
                        />
                      );
                    })}
                  </SortableContext>
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-slate-100">
              {table.getRowModel().rows.map((row) => (
                <DataRow
                  key={rowKey ? rowKey(row.original) : row.id}
                  row={row}
                  columns={columns}
                  onClick={onRowClick}
                  isActive={isRowActive?.(row.original) ?? false}
                />
              ))}
            </tbody>
          </table>
        </DndContext>
      </div>
      {footerSlot}
    </div>
  );
}

// ── Header cell ────────────────────────────────────────────────────────────

interface DraggableHeaderCellProps<T> {
  header: Header<T, unknown>;
  unmovable?: boolean;
}

function DraggableHeaderCell<T>({ header, unmovable }: DraggableHeaderCellProps<T>) {
  const sortable = useSortable({
    id: header.column.id,
    disabled: unmovable,
  });
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = sortable;

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition,
    width: header.getSize(),
    opacity: isDragging ? 0.7 : 1,
    position: 'relative',
    // Cursor: 'grabbing' during an active drag, 'grab' otherwise, 'default'
    // for unmovable columns. Communicates the affordance + the live state.
    cursor: unmovable ? 'default' : isDragging ? 'grabbing' : 'grab',
    background: isDragging ? '#eef2ff' : undefined,
  };

  const canSort = header.column.getCanSort();
  const sortDir = header.column.getIsSorted();
  const isResizing = header.column.getIsResizing();

  return (
    <th
      ref={setNodeRef}
      style={style}
      // `group` so the grip + resize handle can react to header hover.
      className="group select-none whitespace-nowrap py-2.5 px-3 font-semibold"
      {...(unmovable ? {} : attributes)}
      {...(unmovable ? {} : listeners)}
    >
      <span className="inline-flex items-center gap-1.5">
        {/* Drag grip — visible on hover, fully opaque while dragging. */}
        {!unmovable && (
          <GripDots
            className={`shrink-0 transition-opacity ${
              isDragging
                ? 'text-indigo-500 opacity-100'
                : 'text-slate-300 opacity-0 group-hover:opacity-100'
            }`}
          />
        )}
        <span
          className={canSort ? 'cursor-pointer' : ''}
          onClick={(e) => {
            // Allow click-to-sort without triggering drag (dnd-kit's
            // activationConstraint distance=5 already handles this, but
            // stopPropagation is belt-and-braces).
            e.stopPropagation();
            if (canSort) header.column.toggleSorting();
          }}
        >
          {flexRender(header.column.columnDef.header, header.getContext())}
        </span>
        {canSort && (
          <span aria-hidden className="text-[10px] text-slate-400">
            {sortDir === 'asc' ? '↑' : sortDir === 'desc' ? '↓' : '⇅'}
          </span>
        )}
      </span>

      {/* Resize handle.
          - Wide invisible hit-zone (w-2) for easy grabbing.
          - Inside it, a thin always-visible line (w-px) at the right edge
            that thickens + recolors on hover/resize so the affordance is
            discoverable but not noisy.
          - stopPropagation on pointerdown prevents drag from hijacking. */}
      <span
        onMouseDown={header.getResizeHandler()}
        onTouchStart={header.getResizeHandler()}
        onPointerDown={(e) => e.stopPropagation()}
        className="absolute right-0 top-0 h-full w-2 cursor-col-resize select-none touch-none group/resize"
        aria-hidden
      >
        <span
          className={`pointer-events-none absolute right-0 top-1/4 h-1/2 transition-all ${
            isResizing
              ? 'w-[3px] bg-indigo-500'
              : 'w-px bg-slate-300 group-hover/resize:w-[3px] group-hover/resize:bg-indigo-400'
          }`}
        />
      </span>
    </th>
  );
}

/** 6-dot grip icon (matches the standard drag-handle convention). */
function GripDots({ className = '' }: { className?: string }) {
  return (
    <svg
      width="6"
      height="10"
      viewBox="0 0 6 10"
      className={className}
      aria-hidden
    >
      <circle cx="1.5" cy="1.5" r="1" fill="currentColor" />
      <circle cx="4.5" cy="1.5" r="1" fill="currentColor" />
      <circle cx="1.5" cy="5" r="1" fill="currentColor" />
      <circle cx="4.5" cy="5" r="1" fill="currentColor" />
      <circle cx="1.5" cy="8.5" r="1" fill="currentColor" />
      <circle cx="4.5" cy="8.5" r="1" fill="currentColor" />
    </svg>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────

interface DataRowProps<T> {
  row: Row<T>;
  columns: DataTableColumn<T>[];
  onClick?: (row: T) => void;
  isActive: boolean;
}

function DataRow<T>({ row, columns, onClick, isActive }: DataRowProps<T>) {
  const clickable = !!onClick;
  return (
    <tr
      onClick={clickable ? () => onClick?.(row.original) : undefined}
      className={`${clickable ? 'cursor-pointer hover:bg-slate-50' : ''} ${isActive ? 'bg-indigo-50' : ''}`}
    >
      {row.getVisibleCells().map((cell) => {
        const col = columns.find((c) => c.id === cell.column.id);
        return (
          <td
            key={cell.id}
            style={{ width: cell.column.getSize() }}
            className={`py-2.5 px-3 ${col?.cellClassName ?? ''}`}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        );
      })}
    </tr>
  );
}

// ── Utility — "Reset columns" affordance ────────────────────────────────────

export function ResetColumnsLink({ tableId, onReset }: { tableId: string; onReset?: () => void }) {
  return (
    <button
      type="button"
      onClick={() => {
        resetLayout(tableId);
        onReset?.();
        // Reload so the table picks up the cleared layout from defaults.
        // (Cheapest correct behaviour; could be replaced with an imperative
        // `table.reset*()` call later if reload is too heavy.)
        window.location.reload();
      }}
      className="text-[11px] text-slate-500 underline-offset-2 hover:underline"
    >
      Reset column layout
    </button>
  );
}

export default DataTable;
