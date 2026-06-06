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
  /**
   * Extra classes. In the default (styled) mode these are appended after the
   * design-system classes; with `unstyled` they are the ONLY classes applied.
   */
  className?: string;
  /**
   * Render a bare <input> with no wrapper/label/error and no design-system
   * styling — only the passed `className`, plus type/value/onChange/disabled
   * and the a11y attributes. For bespoke inputs embedded in a custom layout
   * (e.g. the intake wizard) whose appearance the default Input would fight.
   * Lets every text input route through this one primitive without imposing a
   * visual opinion. Prefer the styled mode (label/error/focus) whenever it fits.
   */
  unstyled?: boolean;
  /** Native min/max/step — for number/date inputs. */
  min?: number | string;
  max?: number | string;
  step?: number | string;
  onFocus?: () => void;
  onBlur?: () => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  /** Native tooltip. */
  title?: string;
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
  className = '',
  unstyled = false,
  min,
  max,
  step,
  onFocus,
  onBlur,
  onKeyDown,
  title,
}) => {
  // AUDIT-A6 / A11Y-1: generate a stable id when none provided so the label and
  // input are always associated. React.useId() guarantees uniqueness across
  // server/client renders.
  const autoId = React.useId();
  const inputId = id ?? `input-${autoId}`;
  const errorId = error ? `${inputId}-error` : undefined;

  // Shared native props so the styled and unstyled paths stay behaviourally
  // identical (same controlled value, same a11y wiring).
  const nativeProps = {
    id: inputId,
    name,
    type,
    value,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value),
    placeholder,
    autoComplete,
    disabled,
    required,
    min,
    max,
    step,
    onFocus,
    onBlur,
    onKeyDown,
    title,
    'aria-required': required || undefined,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': errorId,
  } as const;

  // [AUDIT-B2.2b] Bare input for bespoke layouts — caller owns the appearance.
  if (unstyled) {
    return <input {...nativeProps} className={className} />;
  }

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
        {...nativeProps}
        className={`px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${widthClass} ${errorClass} ${
          disabled ? 'bg-[#f3f4f6] cursor-not-allowed' : 'bg-white'
        } ${className}`}
      />
      {error && (
        <p id={errorId} className="text-sm text-[#7a2a2a] mt-1" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};
