import React from 'react';

/**
 * Thin antigravity wrapper over a native checkbox so every checkbox routes
 * through the design system (one place for future styling/a11y). Passes all
 * native props through — `checked`, `onChange` (event-based), `className`,
 * `disabled`, `id`, … — so migration from a raw <input type="checkbox"> is a
 * straight tag swap.
 */
export type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'>;

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  (props, ref) => <input ref={ref} type="checkbox" {...props} />,
);

Checkbox.displayName = 'Checkbox';
