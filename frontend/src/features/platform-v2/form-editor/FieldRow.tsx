/**
 * [P2-3] FieldRow — renders a single form field with its value input.
 *
 * - AI-filled fields show a blue "AI" badge with a tooltip (confidence %).
 * - Missing required fields show a red outline on the input.
 * - `requires_original=true` fields show a document upload placeholder
 *   (full upload lands in P3-2).
 * - Supports field types: text, date, select, boolean, number, and a fallback
 *   textarea for everything else.
 */
import React, { useState } from 'react';
import type { FieldValueItem } from '../../../api/formEditor';

interface FieldRowProps {
  field: FieldValueItem;
  /** Current live value (may differ from field.value if user has typed) */
  liveValue: string;
  onValueChange: (fieldId: string, value: string) => void;
  /** Highlight as missing required */
  showMissing?: boolean;
}

// ---------------------------------------------------------------------------
// AI badge
// ---------------------------------------------------------------------------

function AiBadge({
  confidence,
  prefillSource,
}: {
  confidence: number | null;
  prefillSource: string | null;
}) {
  const [open, setOpen] = useState(false);
  const pct = confidence !== null ? Math.round(confidence * 100) : null;

  // Human-readable data source from the prefill_source key
  // e.g. "profile.legal_full_name" → "Employee profile"
  //      "family.spouse.legal_full_name" → "Family data (spouse)"
  //      "contract.employer_name" → "Contract data"
  function humaniseSource(src: string | null): string | null {
    if (!src) return null;
    if (src.startsWith('profile.')) return 'Employee profile';
    if (src.startsWith('family.spouse.')) return 'Family data (spouse)';
    if (src.startsWith('family.child.')) return 'Family data (child)';
    if (src.startsWith('family.')) return 'Family data';
    if (src.startsWith('contract.')) return 'Contract data';
    if (src.startsWith('intake.')) return 'Intake answers';
    if (src.startsWith('person.')) return 'Person record';
    return src;
  }

  const sourceLabel = humaniseSource(prefillSource);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200 cursor-default"
        aria-label={`AI pre-filled${pct !== null ? ` · ${pct}% confidence` : ''}${sourceLabel ? ` · from ${sourceLabel}` : ''}`}
      >
        AI
      </button>
      {open && (
        <div className="absolute z-10 bottom-full mb-1.5 left-1/2 -translate-x-1/2 rounded bg-slate-800 text-white text-xs px-2.5 py-1.5 shadow-lg pointer-events-none min-w-max max-w-[220px]">
          <div className="font-medium">Pre-filled by AI</div>
          {sourceLabel && (
            <div className="text-slate-300 mt-0.5">Source: {sourceLabel}</div>
          )}
          {pct !== null && (
            <div className="text-slate-400 mt-0.5">Confidence: {pct}%</div>
          )}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
        </div>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Input controls by field_type
// ---------------------------------------------------------------------------

interface InputProps {
  field: FieldValueItem;
  value: string;
  onChange: (v: string) => void;
  hasError: boolean;
}

function FieldInput({ field, value, onChange, hasError }: InputProps) {
  const base =
    'w-full rounded border px-2.5 py-1.5 text-sm text-slate-900 bg-white ' +
    'focus:outline-none focus:ring-1 focus:ring-[#0b2b43] focus:border-[#0b2b43] transition-colors ';
  const errorClass = 'border-rose-400 bg-rose-50 ';
  const normalClass = 'border-slate-300 ';
  const cls = base + (hasError ? errorClass : normalClass);

  if (field.requires_original) {
    return (
      <div className={`rounded border px-3 py-2 text-sm ${hasError ? 'border-rose-300 bg-rose-50' : 'border-slate-200 bg-slate-50'}`}>
        <span className="text-slate-500 italic">
          Document upload — attach the original physical document (P3-2).
        </span>
      </div>
    );
  }

  if (field.field_type === 'boolean') {
    return (
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={value === 'true'}
          onChange={(e) => onChange(e.target.checked ? 'true' : 'false')}
          className="w-4 h-4 rounded border-slate-300 text-[#0b2b43] focus:ring-[#0b2b43]"
        />
        <span className="text-sm text-slate-700">{value === 'true' ? 'Yes' : 'No'}</span>
      </label>
    );
  }

  if (field.field_type === 'select' && field.options && field.options.length > 0) {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cls}
      >
        <option value="">— select —</option>
        {field.options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  if (field.field_type === 'date') {
    return (
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cls}
      />
    );
  }

  if (field.field_type === 'number') {
    return (
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cls}
      />
    );
  }

  // Default: text
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.required ? 'Required' : 'Optional'}
      className={cls}
    />
  );
}

// ---------------------------------------------------------------------------
// FieldRow component
// ---------------------------------------------------------------------------

export const FieldRow: React.FC<FieldRowProps> = ({
  field,
  liveValue,
  onValueChange,
  showMissing = false,
}) => {
  const isAiFilled = field.filled_by === 'ai';
  const isMissing = showMissing && field.required && (!liveValue || liveValue.trim() === '');

  return (
    <div className={`rounded-lg border px-4 py-3 transition-colors ${isMissing ? 'border-rose-300 bg-rose-50/40' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
      {/* Label row */}
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-sm font-medium text-slate-800 flex-1 leading-snug">
          {field.label}
          {field.required && (
            <span className="ml-0.5 text-rose-500" aria-label="required">*</span>
          )}
        </label>
        <div className="flex items-center gap-1.5 shrink-0">
          {isAiFilled && (
            <AiBadge
              confidence={field.ai_confidence}
              prefillSource={field.prefill_source}
            />
          )}
          {field.overridden && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200">
              Edited
            </span>
          )}
          {field.reviewed && !field.overridden && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700 border border-emerald-200">
              Reviewed
            </span>
          )}
        </div>
      </div>

      {/* Input */}
      <FieldInput
        field={field}
        value={liveValue}
        onChange={(v) => onValueChange(field.field_id, v)}
        hasError={isMissing}
      />

      {isMissing && (
        <p className="mt-1 text-xs text-rose-600">This field is required.</p>
      )}
    </div>
  );
};
