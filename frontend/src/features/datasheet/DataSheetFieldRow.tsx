/**
 * DataSheetFieldRow — one field of the composed Document Data Sheet.
 *
 * Consumes the DataSheetField DTO (already lang-resolved + provenance-mapped by the backend),
 * so it is a thin renderer. Matches the visual language of platform-v2 form-editor/FieldRow
 * (amber for consult-professional, rose for needs-input) without sharing its FieldValueItem shape.
 *
 * States:
 *   - consult_professional → guidance only, never a value or an input (the firewall).
 *   - needs_input          → an editable input + Save.
 *   - sourced value        → the value verbatim + a provenance badge, with an Edit affordance.
 */
import React, { useState } from 'react';
import { Badge } from '../../components/antigravity/Badge';
import { Button } from '../../components/antigravity/Button';
import { Input } from '../../components/antigravity/Input';
import type { DataSheetField, DataSheetSource } from '../../api/datasheet';

const SOURCE_BADGE: Partial<
  Record<DataSheetSource, { label: string; variant: 'success' | 'info' | 'warning' }>
> = {
  intake: { label: 'Provided', variant: 'info' },
  passport_ocr: { label: 'From your passport', variant: 'success' },
  prior_form: { label: 'From a previous form', variant: 'success' },
  ai: { label: 'AI suggestion — please check', variant: 'warning' },
};

interface Props {
  field: DataSheetField;
  /** HR view surfaces the employer-action note. */
  audience: 'employee' | 'hr';
  onSave: (fieldId: string, value: string) => Promise<void>;
  saving: boolean;
}

export const DataSheetFieldRow: React.FC<Props> = ({ field, audience, onSave, saving }) => {
  const isConsult = field.source === 'consult_professional';
  const isNeedsInput = field.source === 'needs_input';
  const badge = !isConsult && !isNeedsInput ? SOURCE_BADGE[field.source] : undefined;
  const [editing, setEditing] = useState(isNeedsInput);
  const [draft, setDraft] = useState(field.value ?? '');

  const containerCls = isConsult
    ? 'border-amber-200 bg-amber-50/40'
    : isNeedsInput
      ? 'border-rose-300 bg-rose-50/40'
      : 'border-slate-200 bg-white hover:border-slate-300';

  const save = async () => {
    await onSave(field.fieldId, draft);
    setEditing(false);
  };

  return (
    <div className={`rounded-lg border px-4 py-3 transition-colors ${containerCls}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-sm font-medium text-slate-800 flex-1 leading-snug" htmlFor={`ds-${field.fieldId}`}>
          {field.label}
        </label>
        <div className="flex items-center gap-1.5 shrink-0">
          {isConsult && <Badge variant="warning" size="sm">Consult a professional</Badge>}
          {isNeedsInput && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-700 border border-rose-200">
              Needs input
            </span>
          )}
          {badge && (
            <Badge variant={badge.variant} size="sm">
              {badge.label}
            </Badge>
          )}
        </div>
      </div>

      {isConsult ? (
        <p className="text-xs text-amber-700 italic">
          A regulated advisor will determine this — ReloPass won&apos;t pre-fill it.
        </p>
      ) : editing ? (
        <div className="flex items-center gap-2">
          <Input
            id={`ds-${field.fieldId}`}
            value={draft}
            onChange={(v) => setDraft(v)}
            placeholder={field.hint ? undefined : 'Enter a value'}
            fullWidth
          />
          <Button size="sm" onClick={save} disabled={saving || draft.trim() === ''}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
          {!isNeedsInput && (
            <Button size="sm" variant="ghost" onClick={() => { setDraft(field.value ?? ''); setEditing(false); }} disabled={saving}>
              Cancel
            </Button>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-900 font-medium">{field.value}</span>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>
        </div>
      )}

      {field.requiresOriginal && !isConsult && (
        <p className="mt-1 text-xs text-slate-500 italic">Bring the original document to your appointment.</p>
      )}
      {/* needs_input prompt / consult referral note */}
      {(field.hint || field.guidance) && (
        <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{field.hint ?? field.guidance}</p>
      )}
      {audience === 'hr' && field.employerActionNote && (
        <p className="mt-1.5 text-xs leading-relaxed text-slate-700">
          <span className="font-medium">Employer action:</span> {field.employerActionNote}
        </p>
      )}
    </div>
  );
};
