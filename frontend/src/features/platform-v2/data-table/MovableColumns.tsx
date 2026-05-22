/**
 * MovableColumns.tsx — Column drag-to-reorder system
 * ─────────────────────────────────────────────────────────────────────────────
 * useMovableColumns — React hook that owns column order + localStorage persist
 * MovableTh          — <th> with drag handle, ghost styling, drop-target
 *
 * Usage:
 *   const { orderedColumns, thProps } = useMovableColumns({ tableId: 'cases', columns })
 *   <thead><tr>{orderedColumns.map(col => <MovableTh key={col.id} {...thProps(col)} />)}</tr></thead>
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ColumnDef {
  id: string;
  label: string;
  /** Minimum width in px. Defaults to 80. */
  minWidth?: number;
  /** If true, column cannot be moved */
  fixed?: boolean;
}

export interface UseMovableColumnsOptions {
  /** Unique key used for localStorage — rp-cols-{tableId} */
  tableId: string;
  columns: ColumnDef[];
}

export interface MovableThProps {
  column: ColumnDef;
  index: number;
  isDragging: boolean;
  isOver: boolean;
  onDragStart: (e: React.DragEvent, id: string) => void;
  onDragOver:  (e: React.DragEvent, id: string) => void;
  onDrop:      (e: React.DragEvent, id: string) => void;
  onDragEnd:   () => void;
  children?: React.ReactNode;
  /** Extra styles merged into the <th> element */
  style?: React.CSSProperties;
}

export interface UseMovableColumnsResult {
  /** Columns in current display order */
  orderedColumns: ColumnDef[];
  /** Returns props to spread onto each <MovableTh> */
  thProps: (column: ColumnDef) => MovableThProps;
  /** Programmatically reset to default order */
  resetOrder: () => void;
}

// ─── Storage helpers ──────────────────────────────────────────────────────────

function storageKey(tableId: string) {
  return `rp-cols-${tableId}`;
}

function loadOrder(tableId: string, columns: ColumnDef[]): string[] {
  try {
    const raw = localStorage.getItem(storageKey(tableId));
    if (!raw) return columns.map(c => c.id);
    const saved: string[] = JSON.parse(raw);
    // Filter out any columns that no longer exist, then append new ones
    const valid = saved.filter(id => columns.some(c => c.id === id));
    const newIds = columns.filter(c => !valid.includes(c.id)).map(c => c.id);
    return [...valid, ...newIds];
  } catch {
    return columns.map(c => c.id);
  }
}

function saveOrder(tableId: string, order: string[]) {
  try {
    localStorage.setItem(storageKey(tableId), JSON.stringify(order));
  } catch {
    // ignore
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useMovableColumns({ tableId, columns }: UseMovableColumnsOptions): UseMovableColumnsResult {
  const [order, setOrder] = useState<string[]>(() => loadOrder(tableId, columns));
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  // Persist on change
  useEffect(() => {
    saveOrder(tableId, order);
  }, [tableId, order]);

  // Re-sync when columns prop changes (e.g. new column added)
  useEffect(() => {
    setOrder(prev => {
      const valid = prev.filter(id => columns.some(c => c.id === id));
      const newIds = columns.filter(c => !valid.includes(c.id)).map(c => c.id);
      return [...valid, ...newIds];
    });
  }, [columns]);

  const orderedColumns: ColumnDef[] = order
    .map(id => columns.find(c => c.id === id)!)
    .filter(Boolean);

  const onDragStart = useCallback((e: React.DragEvent, id: string) => {
    const col = columns.find(c => c.id === id);
    if (col?.fixed) { e.preventDefault(); return; }
    setDraggingId(id);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', id);
  }, [columns]);

  const onDragOver = useCallback((e: React.DragEvent, id: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setOverId(id);
  }, []);

  const onDrop = useCallback((e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData('text/plain') || draggingId;
    if (!sourceId || sourceId === targetId) return;
    const col = columns.find(c => c.id === sourceId);
    if (col?.fixed) return;
    setOrder(prev => {
      const result = [...prev];
      const from = result.indexOf(sourceId);
      const to   = result.indexOf(targetId);
      if (from === -1 || to === -1) return prev;
      result.splice(from, 1);
      result.splice(to, 0, sourceId);
      return result;
    });
    setDraggingId(null);
    setOverId(null);
  }, [draggingId, columns]);

  const onDragEnd = useCallback(() => {
    setDraggingId(null);
    setOverId(null);
  }, []);

  const resetOrder = useCallback(() => {
    const defaultOrder = columns.map(c => c.id);
    setOrder(defaultOrder);
    saveOrder(tableId, defaultOrder);
  }, [tableId, columns]);

  const thProps = useCallback((column: ColumnDef): MovableThProps => ({
    column,
    index: order.indexOf(column.id),
    isDragging: draggingId === column.id,
    isOver: overId === column.id && draggingId !== column.id,
    onDragStart,
    onDragOver,
    onDrop,
    onDragEnd,
  }), [order, draggingId, overId, onDragStart, onDragOver, onDrop, onDragEnd]);

  return { orderedColumns, thProps, resetOrder };
}

// ─── MovableTh ────────────────────────────────────────────────────────────────

export function MovableTh({
  column,
  isDragging,
  isOver,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  children,
  style: extraStyle,
}: MovableThProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <th
      draggable={!column.fixed}
      onDragStart={e => onDragStart(e, column.id)}
      onDragOver={e => onDragOver(e, column.id)}
      onDrop={e => onDrop(e, column.id)}
      onDragEnd={onDragEnd}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        padding: '0 12px',
        height: '40px',
        textAlign: 'left',
        fontSize: '12px',
        fontWeight: 600,
        color: 'var(--text-secondary)',
        background: isDragging
          ? 'var(--accent-soft)'
          : isOver
            ? 'var(--surface-hover)'
            : 'transparent',
        borderBottom: isOver
          ? '2px solid var(--accent)'
          : '1px solid var(--border-subtle)',
        opacity: isDragging ? 0.5 : 1,
        cursor: column.fixed ? 'default' : 'grab',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        minWidth: column.minWidth ?? 80,
        transition: 'background var(--transition-fast), border-color var(--transition-fast)',
        ...extraStyle,
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {/* Drag handle — visible on hover */}
        {!column.fixed && (
          <span
            aria-hidden="true"
            style={{
              opacity: hovered ? 0.5 : 0,
              transition: 'opacity var(--transition-fast)',
              cursor: 'grab',
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
            }}
          >
            {/* GripVertical icon */}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="9"  cy="5"  r="1" fill="currentColor" /><circle cx="15" cy="5"  r="1" fill="currentColor" />
              <circle cx="9"  cy="12" r="1" fill="currentColor" /><circle cx="15" cy="12" r="1" fill="currentColor" />
              <circle cx="9"  cy="19" r="1" fill="currentColor" /><circle cx="15" cy="19" r="1" fill="currentColor" />
            </svg>
          </span>
        )}
        {children ?? column.label}
      </span>
    </th>
  );
}

export default MovableTh;
