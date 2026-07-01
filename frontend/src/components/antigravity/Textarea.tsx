import React from 'react';

interface TextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange' | 'value'> {
  /** Controlled value. Omit for uncontrolled textareas (use `defaultValue`). */
  value?: string;
  /** Receives the value (not the event). Optional for read-only/uncontrolled. */
  onChange?: (value: string) => void;
  label?: string;
  error?: string;
  fullWidth?: boolean;
  /**
   * Render a bare <textarea> with no wrapper/label/error and no design-system
   * styling — only the passed `className` (plus native attrs via `...rest`). For
   * bespoke layouts; prefer the styled mode (label/error/focus) when it fits.
   */
  unstyled?: boolean;
}

/**
 * Antigravity Textarea — the multi-line counterpart to Input. Closes a 100% gap
 * (the library had no textarea), so the 74 raw <textarea> sites can migrate with
 * a straight tag swap. Mirrors Input's API: value-based onChange, label/error with
 * auto-associated ids, and an `unstyled` escape hatch.
 */
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({
  value,
  onChange,
  label,
  error,
  disabled = false,
  fullWidth = false,
  rows = 4,
  id,
  className = '',
  unstyled = false,
  required = false,
  ...rest
}, ref) => {
  const autoId = React.useId();
  const textareaId = id ?? `textarea-${autoId}`;
  const errorId = error ? `${textareaId}-error` : undefined;

  const nativeProps = {
    ...rest,
    id: textareaId,
    rows,
    ...(value !== undefined ? { value } : {}),
    ...(onChange ? { onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value) } : {}),
    disabled,
    required,
    'aria-required': required || undefined,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': errorId,
  };

  if (unstyled) {
    return <textarea ref={ref} {...nativeProps} className={className} />;
  }

  const widthClass = fullWidth ? 'w-full' : '';
  const errorClass = error ? 'border-[#7a2a2a] focus:ring-[#7a2a2a]' : 'border-[#d1d5db] focus:ring-[#0b2b43]';

  return (
    <div className={widthClass}>
      {label && (
        <label htmlFor={textareaId} className="block text-sm font-medium text-[#374151] mb-1">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
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
});

Textarea.displayName = 'Textarea';
