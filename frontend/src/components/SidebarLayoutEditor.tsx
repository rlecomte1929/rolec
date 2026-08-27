/**
 * SidebarLayoutEditor — in-sidebar editor for ONE nav section's layout.
 *
 * Rendered per visible section when the user enters "Edit layout" mode (all sections,
 * not just Admin). Drag a tab to reorder it or move it into another sub-group within
 * the same section (it adopts the group it's dropped into); click a group name to
 * rename it. Changes are lifted to the parent via onChange, which persists to
 * localStorage. The Done/Reset controls live once at the sidebar level. See
 * adminSidebarLayout.ts for the model.
 */

import React, { useLayoutEffect, useRef, useState } from 'react';
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToVerticalAxis } from '@dnd-kit/modifiers';
import { GripVertical } from 'lucide-react';
import type { AdminLayoutEntry } from './adminSidebarLayout';

const SortableRow: React.FC<{ id: string; label: string }> = ({ id, label }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label={`Drag ${label}`}
        className="cursor-grab touch-none text-slate-500 hover:text-slate-600 active:cursor-grabbing"
      >
        <GripVertical size={13} />
      </button>
      <span className="truncate">{label}</span>
    </div>
  );
};

export const SidebarLayoutEditor: React.FC<{
  /** Section heading shown above the draggable rows (omitted for borrowed sections). */
  sectionTitle?: string;
  layout: AdminLayoutEntry[];
  labels: Record<string, string>;
  onChange: (next: AdminLayoutEntry[]) => void;
}> = ({ sectionTitle, layout, labels, onChange }) => {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const [editingGroup, setEditingGroup] = useState<string | null>(null);
  const [draftName, setDraftName] = useState('');
  const renameInputRef = useRef<HTMLInputElement | null>(null);
  // Focus the rename field when it opens (jsx-a11y forbids the autoFocus prop).
  useLayoutEffect(() => {
    if (editingGroup !== null) renameInputRef.current?.focus();
  }, [editingGroup]);

  const ids = layout.map((e) => e.id);

  const handleDragEnd = (evt: DragEndEvent) => {
    const { active, over } = evt;
    if (!over || active.id === over.id) return;
    const from = ids.indexOf(String(active.id));
    const to = ids.indexOf(String(over.id));
    if (from < 0 || to < 0) return;
    const moved = arrayMove(layout, from, to);
    // Adopt the group of the new neighbour above (or below when dropped at the very top)
    // so sub-groups stay contiguous and moving across a boundary re-sections the tab.
    const neighbourGroup = moved[to - 1]?.group ?? moved[to + 1]?.group ?? moved[to]!.group;
    moved[to] = { ...moved[to]!, group: neighbourGroup };
    onChange(moved);
  };

  const commitRename = (oldName: string) => {
    const name = draftName.trim();
    setEditingGroup(null);
    if (!name || name === oldName) return;
    onChange(layout.map((e) => (e.group === oldName ? { ...e, group: name } : e)));
  };

  return (
    <div className="px-2 pb-2">
      {sectionTitle && (
        <div className="px-1 pt-3 pb-1">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{sectionTitle}</span>
        </div>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        modifiers={[restrictToVerticalAxis]}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          <div className="flex flex-col gap-1">
            {layout.map((entry, idx) => {
              const isBoundary = entry.group !== layout[idx - 1]?.group;
              return (
                <React.Fragment key={entry.id}>
                  {isBoundary && (
                    <div className="px-1 pt-2 first:pt-0">
                      {editingGroup === entry.group ? (
                        <input
                          ref={renameInputRef}
                          value={draftName}
                          onChange={(e) => setDraftName(e.target.value)}
                          onBlur={() => commitRename(entry.group)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') commitRename(entry.group);
                            if (e.key === 'Escape') setEditingGroup(null);
                          }}
                          className="w-full rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600 focus:outline-none focus:ring-1 focus:ring-[#0b2b43]/40"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingGroup(entry.group);
                            setDraftName(entry.group);
                          }}
                          title="Rename section"
                          className="text-[9px] font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-600"
                        >
                          {entry.group || 'Ungrouped'}
                        </button>
                      )}
                    </div>
                  )}
                  <SortableRow id={entry.id} label={labels[entry.id] ?? entry.id} />
                </React.Fragment>
              );
            })}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
};

export default SidebarLayoutEditor;
