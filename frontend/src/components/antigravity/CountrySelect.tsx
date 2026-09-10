/**
 * Single-country picker: full name + flag, value persisted as ISO alpha-2.
 * Native <option> cannot render CSS flag glyphs, so this is a combobox.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { COUNTRY_OPTIONS, countryName } from '../../features/policy-config/countryList';
import { compareCountryDisplayNames } from '../../utils/countries';
import { Button } from './Button';
import { CountryFlag } from './CountryFlag';
import { Input } from './Input';

export type CountrySelectOption = { code: string; name: string };

type Props = {
  value: string;
  onChange: (code: string) => void;
  options?: ReadonlyArray<CountrySelectOption>;
  /** Restrict to these ISO codes (e.g. countries returned by an API). */
  codes?: readonly string[];
  allowEmpty?: boolean;
  emptyLabel?: string;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
  className?: string;
};

export const CountrySelect: React.FC<Props> = ({
  value,
  onChange,
  options = COUNTRY_OPTIONS,
  codes,
  allowEmpty = false,
  emptyLabel = 'All',
  disabled,
  placeholder = 'Select a country',
  id,
  className = '',
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const list = useMemo(() => {
    const source = codes && codes.length > 0
      ? codes.filter((c) => c.trim()).map((raw) => {
          const code = raw.trim().toUpperCase();
          const match = options.find(
            (o) => o.code === code || (code === 'UK' && o.code === 'GB'),
          );
          return { code, name: match?.name ?? countryName(code) };
        })
      : [...options];
    return [...source].sort((a, b) => compareCountryDisplayNames(a.name, b.name));
  }, [options, codes]);

  const selected = list.find(
    (c) => c.code.toUpperCase() === value.toUpperCase() || c.name.toLowerCase() === value.trim().toLowerCase(),
  );

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q),
    );
  }, [list, query]);

  const choose = (code: string) => {
    onChange(code);
    setOpen(false);
    setQuery('');
  };

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      <Button
        unstyled
        type="button"
        id={id}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={selected ? selected.name : (allowEmpty ? emptyLabel : placeholder)}
        onClick={() => {
          if (disabled) return;
          setOpen((o) => !o);
          setQuery('');
        }}
        className={`w-full min-h-[40px] px-3 py-2 border rounded-lg bg-white text-left text-sm flex items-center gap-2 ${
          disabled
            ? 'border-slate-200 opacity-60 cursor-not-allowed'
            : 'border-slate-300 focus:outline-none focus:ring-2 focus:ring-navy-800 cursor-pointer'
        }`}
      >
        {selected ? (
          <CountryFlag country={selected.code} label={selected.name} className="text-sm" />
        ) : (
          <span className="text-slate-500">{allowEmpty && !value ? emptyLabel : placeholder}</span>
        )}
        <span className="ml-auto text-slate-500 text-xs" aria-hidden>▾</span>
      </Button>
      {open && !disabled && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="sticky top-0 bg-white p-2 border-b border-slate-100">
            <Input
              unstyled
              type="text"
              value={query}
              onChange={setQuery}
              placeholder="Search by name or code…"
              className="w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
            />
          </div>
          {allowEmpty && (
            <Button
              unstyled
              type="button"
              role="option"
              onClick={() => choose('')}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${
                !value ? 'bg-accent-50 text-accent-700' : 'text-slate-700'
              }`}
            >
              {emptyLabel}
            </Button>
          )}
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-sm text-slate-500">No matches.</div>
          ) : (
            filtered.map((c) => (
              <Button
                unstyled
                key={c.code}
                type="button"
                role="option"
                aria-selected={selected?.code === c.code}
                onClick={() => choose(c.code)}
                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 flex items-center ${
                  selected?.code === c.code ? 'bg-accent-50 text-accent-700' : 'text-navy-900'
                }`}
              >
                <CountryFlag country={c.code} label={c.name} className="text-sm" />
              </Button>
            ))
          )}
        </div>
      )}
    </div>
  );
};
