/**
 * Section C: small country multi-select for jurisdiction-override rows.
 *
 * Why roll our own instead of pulling a dep:
 *   - The repo doesn't have an existing MultiSelect we can reuse.
 *   - Country list is ~180 items; a virtualized library is overkill.
 *   - Full styling control matches the existing antigravity tone.
 *
 * Behavior:
 *   - Click the input to open. Type to filter by code or name.
 *   - Click a row to add; click an existing chip to remove.
 *   - Closes on click outside or Escape.
 *   - Disabled state mirrors the rest of the editor (read-only review).
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { COUNTRY_OPTIONS, countryName } from './countryList';

type Props = {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
};

export const CountryMultiSelect: React.FC<Props> = ({
  value,
  onChange,
  disabled,
  placeholder,
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Close when clicking outside the picker. Avoid using global Escape only;
  // mouse users expect click-out as well.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  const selectedSet = useMemo(() => new Set(value.map((c) => c.toUpperCase())), [value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COUNTRY_OPTIONS;
    return COUNTRY_OPTIONS.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q)
    );
  }, [query]);

  const toggle = (code: string) => {
    const up = code.toUpperCase();
    const next = selectedSet.has(up)
      ? value.filter((c) => c.toUpperCase() !== up)
      : [...value, up];
    onChange(next);
  };

  const remove = (code: string) => {
    onChange(value.filter((c) => c.toUpperCase() !== code.toUpperCase()));
  };

  return (
    <div ref={wrapRef} className="relative">
      <div
        className={`flex flex-wrap items-center gap-1 min-h-[40px] px-2 py-1.5 border rounded-lg bg-white ${
          disabled
            ? 'border-[#e5e7eb] opacity-60 cursor-not-allowed'
            : 'border-[#d1d5db] focus-within:ring-2 focus-within:ring-[#0b2b43] cursor-text'
        }`}
        onClick={() => !disabled && setOpen(true)}
      >
        {value.length === 0 && !open && (
          <span className="text-sm text-[#9ca3af]">
            {placeholder || 'Select countries (search by name or ISO code)…'}
          </span>
        )}
        {value.map((code) => (
          <span
            key={code}
            className="inline-flex items-center gap-1 rounded-full bg-[#eff6ff] border border-[#bfdbfe] px-2 py-0.5 text-xs text-[#1d4ed8]"
          >
            <span className="font-medium">{code.toUpperCase()}</span>
            <span className="text-[#64748b]">{countryName(code.toUpperCase())}</span>
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${countryName(code.toUpperCase())}`}
                onClick={(e) => {
                  e.stopPropagation();
                  remove(code);
                }}
                className="ml-0.5 text-[#64748b] hover:text-[#dc2626]"
              >
                ×
              </button>
            )}
          </span>
        ))}
        {!disabled && (
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (!open) setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={value.length === 0 ? '' : 'Add another…'}
            className="flex-1 min-w-[8ch] outline-none text-sm bg-transparent"
          />
        )}
      </div>
      {open && !disabled && (
        <div className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-[#e2e8f0] bg-white shadow-lg">
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-sm text-[#6b7280]">
              No matches. Try the ISO code (e.g. SG, DE, US).
            </div>
          ) : (
            filtered.map((c) => {
              const checked = selectedSet.has(c.code);
              return (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => toggle(c.code)}
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-[#f1f5f9] flex items-center justify-between ${
                    checked ? 'bg-[#eff6ff] text-[#1d4ed8]' : 'text-[#0f172a]'
                  }`}
                >
                  <span>
                    <span className="font-mono mr-2 text-[#64748b]">{c.code}</span>
                    {c.name}
                  </span>
                  {checked && <span aria-hidden>✓</span>}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
