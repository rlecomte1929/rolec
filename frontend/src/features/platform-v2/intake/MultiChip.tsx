// ─── MultiChip ────────────────────────────────────────────────────────────────
// Small presentational pill-group used across the intake wizard. Multi-select by
// design; single-select fields wire it as `value={x ? [x] : []}` and read the
// newly-toggled option from onChange. Kept in its own module so it can be unit
// tested without importing the full page (which pulls in the Supabase client).

export function MultiChip({ value, onChange, options }: {
  value: string[]; onChange: (v: string[]) => void;
  options: Array<string | { value: string; label: string }>;
}) {
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {options.map((o) => {
        const val = typeof o === 'string' ? o : o.value;
        const lbl = typeof o === 'string' ? o : o.label;
        return (
          <button key={val} type="button" onClick={() => toggle(val)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              value.includes(val) ? 'bg-accent-600 text-white border-accent-600' : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
            }`}>{lbl}</button>
        );
      })}
    </div>
  );
}
