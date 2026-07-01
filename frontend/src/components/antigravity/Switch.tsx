import React from 'react';

interface SwitchProps {
  /** On/off state (controlled). */
  checked: boolean;
  /** Receives the next boolean state. */
  onChange: (checked: boolean) => void;
  /** Accessible label. Use `label` for a visible label, or `aria-label` via rest. */
  label?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
  'aria-label'?: string;
}

/**
 * Antigravity Switch — an accessible on/off toggle (the library had none). Built
 * as a `role="switch"` button so it is keyboard-operable (Space/Enter) and
 * screen-reader-correct via `aria-checked`. Navy when on, slate track when off.
 */
export const Switch: React.FC<SwitchProps> = ({
  checked,
  onChange,
  label,
  disabled = false,
  id,
  className = '',
  'aria-label': ariaLabel,
}) => {
  const autoId = React.useId();
  const switchId = id ?? `switch-${autoId}`;
  const labelId = label ? `${switchId}-label` : undefined;

  const control = (
    <button
      type="button"
      role="switch"
      id={switchId}
      aria-checked={checked}
      aria-label={!label ? ariaLabel : undefined}
      aria-labelledby={labelId}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-2 ${
        checked ? 'bg-[#0b2b43]' : 'bg-[#cbd5e1]'
      } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  );

  if (!label) return control;

  return (
    <span className="inline-flex items-center gap-2">
      {control}
      <span id={labelId} className="text-sm text-[#374151]">
        {label}
      </span>
    </span>
  );
};
