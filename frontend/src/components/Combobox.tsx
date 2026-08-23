import React, { useEffect, useRef, useState } from 'react';
import { Input } from './antigravity';

interface ComboboxProps {
  value: string;
  onChange: (v: string) => void;
  /** Suggestion list. Filtered case-insensitively by the typed text. */
  options: string[];
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  testId?: string;
  fullWidth?: boolean;
}

/**
 * AIQ-1656 — a searchable combobox that SUGGESTS from `options` but still accepts a typed
 * value not in the list, so it never blocks the user. Used for catalogue-backed country and
 * destination-city fields; callers that want an "add this destination" request fire it
 * themselves on commit (e.g. on save), so a half-typed value never files a junk ticket.
 */
export function Combobox({ value, onChange, options, label, placeholder, disabled, testId, fullWidth = true }: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);
  const q = value.trim().toLowerCase();
  const filtered = (q ? options.filter((o) => o.toLowerCase().includes(q)) : options).slice(0, 50);
  return (
    <div ref={ref}>
      {/* `htmlFor`-less labels are not associated with their control: a screen reader
          announces nothing, and getByLabelText cannot find the input. The Input below
          forwards native attributes, so aria-label is the smallest correct association
          — no id plumbing through a shared component. */}
      {label && <label className="block text-sm font-medium text-navy-800 mb-1">{label}</label>}
      <div className="relative">
        <Input
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          fullWidth={fullWidth}
          data-testid={testId}
          aria-label={label}
          autoComplete="off"
          onFocus={() => { if (!disabled) setOpen(true); }}
        />
        {open && !disabled && filtered.length > 0 && (
          <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
            {filtered.map((o) => (
              <div
                key={o}
                role="option"
                aria-selected={value === o}
                tabIndex={0}
                onClick={() => { onChange(o); setOpen(false); }}
                onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(o); setOpen(false); } }}
                className="px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50"
              >
                {o}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
