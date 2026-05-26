import React from 'react';

interface InputProps {
  type?: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  fullWidth?: boolean;
  /**
   * Optional explicit id for the input. When omitted, a stable id is generated
   * via `React.useId()` and wired to both the `<label>` (htmlFor) and the error
   * `<p>` (aria-describedby). This closes A11Y-1 + A11Y-7 from
   * `audit/02-expert-a11y.md` for every consumer of <Input>.
   */
  id?: string;
  /** Optional `name` attribute, useful for autofill heuristics + uncontrolled forms. */
  name?: string;
  /** When true, the input is required (announced by screen readers via aria-required). */
  required?: boolean;
}

export const Input: React.FC<InputProps> = ({
  type = 'text',
  value,
  onChange,
  placeholder,
  autoComplete,
  label,
  error,
  disabled = false,
  fullWidth = false,
  id,
  name,
  required = false,
}) => {
  // AUDIT-A6 / A11Y-1: generate a stable id when none provided so the label and
  // input are always associated. React.useId() guarantees uniqueness across
  // server/client renders.
  const autoId = React.useId();
  const inputId = id ?? `input-${autoId}`;
  const errorId = error ? `${inputId}-error` : undefined;

  const widthClass = fullWidth ? 'w-full' : '';
  const errorClass = error ? 'border-[#7a2a2a] focus:ring-[#7a2a2a]' : 'border-[#d1d5db] focus:ring-[#0b2b43]';

  return (
    <div className={widthClass}>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-[#374151] mb-1">
          {label}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className={`px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${widthClass} ${errorClass} ${
          disabled ? 'bg-[#f3f4f6] cursor-not-allowed' : 'bg-white'
        }`}
      />
      {error && (
        <p id={errorId} className="text-sm text-[#7a2a2a] mt-1" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};
