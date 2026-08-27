/**
 * AIQ-1607: address input with server-proxied autocomplete (Geoapify).
 *
 * Mirrors the intake CountryCombo dropdown, but the value is free text and the
 * suggestions come from the backend proxy (debounced, superseded requests
 * aborted). Free-typed text stays valid (onChange fires on every keystroke —
 * a selection is never forced). When the backend is unkeyed/disabled or errors,
 * no dropdown appears and it behaves as a plain input (graceful degrade).
 */
import React, { useEffect, useRef, useState } from 'react';
import { Input } from './antigravity/Input';
import { getAddressAutocomplete } from '../api/geo';

export function AddressAutocompleteInput({
  value,
  onChange,
  placeholder,
  disabled,
  className,
  testId,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  const reqId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  // Skip the fetch that a selection would otherwise trigger (value just changed
  // to the full selected address — we don't want the dropdown to re-open).
  const justSelected = useRef(false);

  // Close on outside click (same pattern as CountryCombo).
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Debounced suggestions on value change; aborts superseded requests.
  useEffect(() => {
    if (disabled) return;
    if (justSelected.current) {
      justSelected.current = false;
      return;
    }
    const q = (value || '').trim();
    if (q.length < 3) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    const myId = ++reqId.current;
    const timer = window.setTimeout(() => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      void getAddressAutocomplete(q, ctrl.signal)
        .then((res) => {
          if (myId !== reqId.current) return; // superseded
          if (res.disabled) {
            setSuggestions([]); // graceful degrade → plain input
            return;
          }
          const items = (res.suggestions || []).map((s) => s.formatted).filter(Boolean);
          setSuggestions(items);
          setOpen(items.length > 0);
        })
        .catch(() => {
          if (myId === reqId.current) setSuggestions([]); // fail-soft
        });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [value, disabled]);

  const select = (s: string) => {
    justSelected.current = true;
    onChange(s);
    setOpen(false);
    setSuggestions([]);
  };

  return (
    <div ref={ref} className="relative">
      <Input
        unstyled
        type="text"
        data-testid={testId}
        className={className}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        onChange={(v) => onChange(v)}
        onFocus={() => {
          if (!disabled && suggestions.length > 0) setOpen(true);
        }}
      />
      {open && !disabled && suggestions.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
          {suggestions.map((s, i) => (
            <div
              key={`${i}-${s}`}
              onClick={() => select(s)}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  select(s);
                }
              }}
              role="option"
              aria-selected={false}
              tabIndex={0}
              className="flex items-center gap-2 px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50"
            >
              <span className="text-gray-500">📍</span>
              <span className="flex-1">{s}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
