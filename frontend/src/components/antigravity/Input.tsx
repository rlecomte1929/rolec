import React from 'react';

interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value' | 'size'> {
  /** Controlled value. Omit for uncontrolled inputs (use `defaultValue` via native props). */
  value?: string | number;
  /**
   * Receives the value (not the event). Optional — read-only / uncontrolled
   * inputs may omit it.
   */
  onChange?: (value: string) => void;
  label?: string;
  error?: string;
  fullWidth?: boolean;
  /**
   * Render a bare <input> with no wrapper/label/error and no design-system
   * styling — only the passed `className` (plus any native attrs via `...rest`).
   * For bespoke inputs embedded in a custom layout whose appearance the default
   * Input would fight. Prefer the styled mode (label/error/focus) when it fits.
   */
  unstyled?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  type = 'text',
  value,
  onChange,
  label,
  error,
  disabled = false,
  fullWidth = false,
  id,
  className = '',
  unstyled = false,
  required = false,
  ...rest
}, ref) => {
  // AUDIT-A6 / A11Y-1: generate a stable id when none provided so the label and
  // input are always associated.
  const autoId = React.useId();
  const inputId = id ?? `input-${autoId}`;
  const errorId = error ? `${inputId}-error` : undefined;

  // `...rest` carries every native input attribute (style, readOnly, placeholder,
  // autoComplete, name, min/max/step, pattern, defaultValue, onFocus/onBlur/…)
  // so any raw <input> can migrate to <Input unstyled> without losing behaviour.
  const nativeProps = {
    ...rest,
    id: inputId,
    type,
    ...(value !== undefined ? { value } : {}),
    ...(onChange ? { onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value) } : {}),
    disabled,
    required,
    'aria-required': required || undefined,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': errorId,
  };

  // Bare input for bespoke layouts — caller owns the appearance.
  if (unstyled) {
    return <input ref={ref} {...nativeProps} className={className} />;
  }

  const widthClass = fullWidth ? 'w-full' : '';
  const errorClass = error ? 'border-rose-700 focus:ring-rose-700' : 'border-[#d1d5db] focus:ring-[#0b2b43]';

  return (
    <div className={widthClass}>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-[#374151] mb-1">
          {label}
        </label>
      )}
      <input
        ref={ref}
        {...nativeProps}
        className={`px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${widthClass} ${errorClass} ${
          disabled ? 'bg-[#f3f4f6] cursor-not-allowed' : 'bg-white'
        } ${className}`}
      />
      {error && (
        <p id={errorId} className="text-sm text-rose-800 mt-1" role="alert">
          {error}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
