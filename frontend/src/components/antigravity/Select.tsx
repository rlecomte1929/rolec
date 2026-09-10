import React from 'react';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  label?: string;
  fullWidth?: boolean;
  /** `none` keeps caller order (status/workflow lists). `label` sorts A–Z. */
  sort?: 'none' | 'label';
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(({
  value,
  onChange,
  options,
  placeholder,
  label,
  fullWidth = false,
  sort = 'none',
}, ref) => {
  // fullWidth + min-w-0: a <select> sizes to its longest <option> (min-content).
  // In a CSS grid that overflows the track and paints over the next control —
  // BUG-260816-BEF6 on /admin/assignments (Company over Employee search).
  const widthClass = fullWidth ? 'w-full min-w-0 max-w-full' : '';
  const ordered =
    sort === 'label'
      ? [...options].sort((a, b) => a.label.localeCompare(b.label))
      : options;

  return (
    <div className={widthClass}>
      {label && (
        <label className="block text-sm font-medium text-[#374151] mb-1">
          {label}
        </label>
      )}
      <select
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`px-4 py-2 border border-[#d1d5db] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0b2b43] transition-all bg-white ${widthClass}`}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {ordered.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
});

Select.displayName = 'Select';
