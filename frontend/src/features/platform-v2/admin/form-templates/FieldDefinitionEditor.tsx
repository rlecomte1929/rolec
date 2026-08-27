/**
 * [P1-2B] FieldDefinitionEditor — drag-and-drop list of FieldDefinitions.
 *
 * Backs the "Fields" tab of the admin form template editor. The parent
 * owns the canonical state (the array of FieldDefinitions); this component
 * just mutates that array in response to add/edit/remove/reorder.
 *
 * Drag-and-drop uses @dnd-kit/sortable (same package as DataTable).
 */
import React, { useCallback, useMemo } from 'react';
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
import { Input } from '../../../../components/antigravity/Input';
import { Checkbox } from '../../../../components/antigravity/Checkbox';
import { Button } from '../../../../components/antigravity';

// ─────────────────────────────────────────────────────────────────────
// Canonical FieldDefinition shape (locked in by this task)
// ─────────────────────────────────────────────────────────────────────

export type FieldType = 'text' | 'date' | 'number' | 'boolean' | 'select';

export interface FieldDefinition {
  id: string;
  label: string;
  type: FieldType;
  required: boolean;
  prefill_source?: string;
  requires_original?: boolean;
  position?: number;          // computed on save, not user-editable
  options?: string[];         // type='select' only
  // PDF overlay coordinates — consumed by the P3-1 overlay engine
  // (backend/app/routers/cases_read.py::_generate_filled_pdf). Raw PDF
  // points: pdf_x from the page's left edge, pdf_y from the page's
  // bottom edge (PDF/PostScript Y-up space). pdf_page is 1-based.
  pdf_x?: number;
  pdf_y?: number;
  pdf_page?: number;
  pdf_font_size?: number;
  /**
   * [S3] Keys this editor does not model, carried through verbatim.
   *
   * The editor is not the only writer of `form_templates.fields`. Seeded data sheets
   * carry `section`, `label_nb`/`label_de`/`label_fr`, `note`, `portal_url` and
   * `consult_professional` — none of which the admin UI shows. Reconstructing each
   * field from the modelled keys alone silently DELETED them on save, which for the
   * FR→NO data sheet meant losing both its Norwegian labels and its section grouping.
   *
   * The cost is that a typo in a FieldDefinition literal no longer fails type-check.
   * That is worth it: a mistyped key is a visible bug in an admin form, whereas the
   * data loss was silent and irreversible.
   */
  [unmodelledKey: string]: unknown;
}

const FIELD_TYPE_OPTIONS: FieldType[] = ['text', 'date', 'number', 'boolean', 'select'];

// Stable unique key for dnd-kit rows. Field ids should be unique within a
// template, but during editing duplicates are possible; we synthesise a
// per-row dnd id that is stable across renders by remembering the array index
// at first mount via a ref-keyed sentinel.
function dndIdFor(field: FieldDefinition, index: number): string {
  return field.id ? `${field.id}__${index}` : `__row_${index}`;
}

// ─────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────

export interface FieldDefinitionEditorProps {
  value: FieldDefinition[];
  onChange: (next: FieldDefinition[]) => void;
  disabled?: boolean;
}

// ─────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────

export const FieldDefinitionEditor: React.FC<FieldDefinitionEditorProps> = ({
  value,
  onChange,
  disabled,
}) => {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // dnd-kit needs a stable list of ids; we recompute on each render.
  const ids = useMemo(
    () => value.map((f, i) => dndIdFor(f, i)),
    [value],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const oldIndex = ids.indexOf(active.id as string);
      const newIndex = ids.indexOf(over.id as string);
      if (oldIndex < 0 || newIndex < 0) return;
      onChange(arrayMove(value, oldIndex, newIndex));
    },
    [ids, value, onChange],
  );

  const updateAt = (index: number, patch: Partial<FieldDefinition>) => {
    const next = value.map((f, i) => (i === index ? { ...f, ...patch } : f));
    onChange(next);
  };

  const removeAt = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const addRow = () => {
    onChange([
      ...value,
      { id: '', label: '', type: 'text', required: false, requires_original: false },
    ]);
  };

  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-12 gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-2">
        <span className="col-span-1"></span>
        <span className="col-span-2">Field ID</span>
        <span className="col-span-3">Label</span>
        <span className="col-span-2">Type</span>
        <span className="col-span-1 text-center">Req&apos;d</span>
        <span className="col-span-2">Prefill source</span>
        <span className="col-span-1 text-center">Orig.</span>
      </div>

      {value.length === 0 ? (
        <div className="rounded border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          No fields yet. Click <span className="font-medium">Add field</span> to define the first one.
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={[restrictToVerticalAxis]}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={ids} strategy={verticalListSortingStrategy}>
            <div className="grid gap-2">
              {value.map((field, index) => (
                <FieldRow
                  key={ids[index]}
                  dndId={ids[index] ?? dndIdFor(field, index)}
                  field={field}
                  disabled={disabled}
                  onChange={(patch) => updateAt(index, patch)}
                  onRemove={() => removeAt(index)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      <div>
        <Button onClick={addRow} disabled={disabled} variant="secondary">
          + Add field
        </Button>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────
// Sortable row
// ─────────────────────────────────────────────────────────────────────

interface FieldRowProps {
  dndId: string;
  field: FieldDefinition;
  disabled?: boolean;
  onChange: (patch: Partial<FieldDefinition>) => void;
  onRemove: () => void;
}

const FieldRow: React.FC<FieldRowProps> = ({ dndId, field, disabled, onChange, onRemove }) => {
  const sortable = useSortable({ id: dndId, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.6 : 1,
  };

  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className="grid grid-cols-12 gap-2 items-center bg-white border border-slate-200 rounded px-2 py-2"
    >
      {/* Drag handle */}
      <Button unstyled
        type="button"
        ref={sortable.setActivatorNodeRef}
        {...sortable.attributes}
        {...sortable.listeners}
        disabled={disabled}
        aria-label="Drag to reorder"
        className="col-span-1 flex items-center justify-center text-slate-500 hover:text-slate-600 cursor-grab active:cursor-grabbing disabled:cursor-not-allowed"
        // Don't trigger the parent click — dnd attaches its own listeners.
        onClick={(e) => e.preventDefault()}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="9"  cy="6"  r="1.5" />
          <circle cx="9"  cy="12" r="1.5" />
          <circle cx="9"  cy="18" r="1.5" />
          <circle cx="15" cy="6"  r="1.5" />
          <circle cx="15" cy="12" r="1.5" />
          <circle cx="15" cy="18" r="1.5" />
        </svg>
      </Button>

      <Input unstyled
        value={field.id}
        onChange={(v) => onChange({ id: v })}
        placeholder="snake_case_id"
        disabled={disabled}
        className="col-span-2 rounded border border-slate-200 px-2 py-1 text-xs font-mono"
      />
      <Input unstyled
        value={field.label}
        onChange={(v) => onChange({ label: v })}
        placeholder="Human label"
        disabled={disabled}
        className="col-span-3 rounded border border-slate-200 px-2 py-1 text-sm"
      />
      <select
        value={field.type}
        onChange={(e) => onChange({ type: e.target.value as FieldType })}
        disabled={disabled}
        className="col-span-2 rounded border border-slate-200 px-2 py-1 text-sm"
      >
        {FIELD_TYPE_OPTIONS.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <label className="col-span-1 flex items-center justify-center">
        <Checkbox
          checked={field.required}
          onChange={(e) => onChange({ required: e.target.checked })}
          disabled={disabled}
          aria-label="Required"
        />
      </label>
      <Input unstyled
        value={field.prefill_source ?? ''}
        onChange={(v) => onChange({ prefill_source: v || undefined })}
        placeholder="profile.legal_full_name"
        disabled={disabled}
        className="col-span-2 rounded border border-slate-200 px-2 py-1 text-xs font-mono"
      />
      <label className="col-span-1 flex items-center justify-center">
        <Checkbox
          checked={field.requires_original ?? false}
          onChange={(e) => onChange({ requires_original: e.target.checked })}
          disabled={disabled}
          aria-label="Requires original"
        />
      </label>

      {/* Remove (full-width row below on mobile would be nicer but for now use a small overlay) */}
      <Button unstyled
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label="Remove field"
        className="col-span-12 text-right text-xs text-rose-600 hover:text-rose-700 mt-1 pr-1 disabled:opacity-50"
      >
        Remove
      </Button>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────
// Helpers exposed for callers (e.g. AdminFormTemplateEditor save flow)
// ─────────────────────────────────────────────────────────────────────

/** Compute final `position` values from current array order. */
export function withComputedPositions(fields: FieldDefinition[]): FieldDefinition[] {
  return fields.map((f, i) => ({ ...f, position: i + 1 }));
}

/**
 * Coerce raw `form_templates.fields` jsonb into the canonical FieldDefinition shape.
 *
 * Templates seeded by P1-4, or edited via earlier passes, may carry entries that do not
 * conform. Coerce gracefully so the editor does not error on legacy shapes.
 *
 * [S3] Two things matter here, and both were wrong:
 *
 * 1. **Unmodelled keys are preserved.** The spread comes first, so `section`,
 *    `label_nb`/`label_de`/`label_fr`, `note`, `portal_url` and `consult_professional`
 *    survive a load/save round trip. The editor never displayed them, so it never
 *    showed them disappearing — opening the FR→NO data sheet and pressing Save
 *    destroyed its Norwegian labels and its section grouping in one click.
 *
 * 2. **There is one copy.** This was duplicated verbatim in AdminFormTemplateEditor and
 *    AdminFormTemplateMap, which is exactly why the defect existed in both — the PDF
 *    coordinate mapper saves the whole fields array too.
 */
export function normalizeFields(raw: Array<Record<string, unknown>>): FieldDefinition[] {
  const asFiniteNumber = (v: unknown): number | undefined =>
    typeof v === 'number' && Number.isFinite(v) ? v : undefined;
  return (raw || []).map((r, i) => ({
    ...r,
    id: typeof r.id === 'string' ? r.id : '',
    label: typeof r.label === 'string' ? r.label : '',
    type: ((r.type as FieldDefinition['type']) ?? 'text'),
    required: r.required === true,
    prefill_source: typeof r.prefill_source === 'string' ? r.prefill_source : undefined,
    requires_original: r.requires_original === true,
    position: typeof r.position === 'number' ? r.position : i + 1,
    options: Array.isArray(r.options) ? (r.options as string[]) : undefined,
    pdf_x: asFiniteNumber(r.pdf_x),
    pdf_y: asFiniteNumber(r.pdf_y),
    pdf_page: asFiniteNumber(r.pdf_page),
    pdf_font_size: asFiniteNumber(r.pdf_font_size),
  }));
}

/** Quick validation: every id must be non-empty and unique. */
export function validateFieldDefinitions(fields: FieldDefinition[]): string | null {
  if (fields.some((f) => !f.id.trim())) return 'Every field needs a non-empty ID.';
  if (fields.some((f) => !f.label.trim())) return 'Every field needs a non-empty label.';
  const seen = new Set<string>();
  for (const f of fields) {
    const key = f.id.trim();
    if (seen.has(key)) return `Duplicate field ID "${key}". IDs must be unique within a template.`;
    seen.add(key);
  }
  return null;
}
