// platform-table-utils.jsx — reusable column-reorder + resize for any table.
//
// Usage:
//   const cols = useMovableColumns({
//     storageKey: 'mytable',
//     defaultOrder: ['name','plan','status'],
//     defaultWidths: { name: 240, plan: 100, status: 100 },
//     minWidths: { name: 140, plan: 70, status: 70 },
//   });
//
//   <table className="tbl movable-tbl">
//     <thead><tr>
//       {cols.order.map(id => (
//         <MovableTh key={id} colId={id} ctx={cols}
//                    label={LABELS[id]}
//                    sortable sortKey={SORT_KEYS[id]}
//                    currentSortKey={sortKey} sortDir={sortDir}
//                    onSort={toggleSort} />
//       ))}
//     </tr></thead>
//     <tbody>
//       {rows.map(r => (
//         <tr>{cols.order.map(id => (
//           <td key={id} style={cols.cellStyle(id)}>{renderCell(r, id)}</td>
//         ))}</tr>
//       ))}
//     </tbody>
//   </table>
//
//   {cols.dirty && <span className="mt-reset" onClick={cols.reset}>Reset columns</span>}

(function() {
const { useState, useEffect, useCallback, useMemo } = React;
const I = window.PlatformIcon;

function useMovableColumns({ storageKey, defaultOrder, defaultWidths, minWidths = {}, maxWidth = 520 }) {
  const orderKey  = storageKey ? `mt_order_${storageKey}` : null;
  const widthsKey = storageKey ? `mt_widths_${storageKey}` : null;

  const [order, setOrder] = useState(() => {
    if (!orderKey) return defaultOrder;
    try {
      const saved = JSON.parse(localStorage.getItem(orderKey) || 'null');
      if (Array.isArray(saved) &&
          saved.length === defaultOrder.length &&
          saved.every(k => defaultOrder.includes(k))) return saved;
    } catch (e) {}
    return defaultOrder;
  });

  const [widths, setWidths] = useState(() => {
    if (!widthsKey) return defaultWidths;
    try {
      const saved = JSON.parse(localStorage.getItem(widthsKey) || 'null');
      if (saved && typeof saved === 'object') return { ...defaultWidths, ...saved };
    } catch (e) {}
    return defaultWidths;
  });

  useEffect(() => {
    if (orderKey) { try { localStorage.setItem(orderKey, JSON.stringify(order)); } catch (e) {} }
  }, [orderKey, order]);
  useEffect(() => {
    if (widthsKey) { try { localStorage.setItem(widthsKey, JSON.stringify(widths)); } catch (e) {} }
  }, [widthsKey, widths]);

  const [dragCol, setDragCol] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);
  const [dragSide, setDragSide] = useState(null);
  const [resizingCol, setResizingCol] = useState(null);

  const startResize = useCallback((e, colId) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startW = widths[colId] ?? defaultWidths[colId];
    const minW = minWidths[colId] || 60;
    setResizingCol(colId);
    const onMove = (ev) => {
      const dx = ev.clientX - startX;
      const nw = Math.max(minW, Math.min(maxWidth, startW + dx));
      setWidths(w => ({ ...w, [colId]: nw }));
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      setResizingCol(null);
    };
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [widths, defaultWidths, minWidths, maxWidth]);

  const headerDragProps = useCallback((colId) => ({
    draggable: true,
    onDragStart: (e) => {
      setDragCol(colId);
      try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', colId); } catch (err) {}
    },
    onDragOver: (e) => {
      if (!dragCol || dragCol === colId) return;
      e.preventDefault();
      const rect = e.currentTarget.getBoundingClientRect();
      const side = (e.clientX - rect.left) < rect.width / 2 ? 'before' : 'after';
      setDragOverCol(colId);
      setDragSide(side);
    },
    onDrop: (e) => {
      e.preventDefault();
      if (!dragCol || dragCol === colId) {
        setDragCol(null); setDragOverCol(null); setDragSide(null);
        return;
      }
      const next = order.filter(c => c !== dragCol);
      const target = next.indexOf(colId);
      const idx = target + (dragSide === 'after' ? 1 : 0);
      next.splice(idx, 0, dragCol);
      setOrder(next);
      setDragCol(null); setDragOverCol(null); setDragSide(null);
    },
    onDragEnd: () => { setDragCol(null); setDragOverCol(null); setDragSide(null); },
  }), [dragCol, order, dragSide]);

  const reset = useCallback(() => {
    setOrder(defaultOrder);
    setWidths(defaultWidths);
  }, [defaultOrder, defaultWidths]);

  const cellStyle = useCallback((colId) => ({
    width: widths[colId],
    minWidth: minWidths[colId] || 60,
  }), [widths, minWidths]);

  const dirty = useMemo(() => {
    if (order.length !== defaultOrder.length) return true;
    for (let i = 0; i < order.length; i++) if (order[i] !== defaultOrder[i]) return true;
    for (const k of Object.keys(defaultWidths)) if (widths[k] !== defaultWidths[k]) return true;
    return false;
  }, [order, widths, defaultOrder, defaultWidths]);

  return {
    order, widths,
    dragCol, dragOverCol, dragSide, resizingCol,
    startResize, headerDragProps,
    cellStyle, reset, dirty,
    minWidths,
  };
}

function MovableTh({ colId, ctx, label, sortable, sortKey, currentSortKey, sortDir, onSort, className, numeric }) {
  const isDragging = ctx.dragCol === colId;
  const isOver = ctx.dragOverCol === colId && ctx.dragCol !== colId;
  const sorted = sortable && currentSortKey === sortKey;

  const handleClick = (e) => {
    if (e.target.closest('.mt-resize')) return;
    if (sortable && onSort) onSort(sortKey);
  };

  const classes = [
    'movable-th',
    sortable ? 'sortable' : '',
    sorted ? 'sorted' : '',
    numeric ? 'numeric' : '',
    isDragging ? 'dragging' : '',
    isOver ? `drag-over drag-${ctx.dragSide}` : '',
    className || '',
  ].filter(Boolean).join(' ');

  return (
    <th
      style={ctx.cellStyle(colId)}
      className={classes}
      {...ctx.headerDragProps(colId)}
      onClick={sortable ? handleClick : undefined}
      title={sortable ? `Sort by ${typeof label === 'string' ? label : colId}. Drag to reorder.` : 'Drag to reorder.'}
    >
      <span className="mt-grip">⋮⋮</span>
      {label}
      {sorted && <span className="sort-i" style={{ display:'inline-block', marginLeft:4, fontSize:10, verticalAlign:'middle' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>}
      <span
        className={`mt-resize${ctx.resizingCol === colId ? ' active' : ''}`}
        onMouseDown={(e) => ctx.startResize(e, colId)}
        onClick={(e) => e.stopPropagation()}
        onDragStart={(e) => { e.preventDefault(); e.stopPropagation(); }}
        draggable={false}
        title="Drag to resize"
      />
    </th>
  );
}

window.useMovableColumns = useMovableColumns;
window.MovableTh = MovableTh;
})();
