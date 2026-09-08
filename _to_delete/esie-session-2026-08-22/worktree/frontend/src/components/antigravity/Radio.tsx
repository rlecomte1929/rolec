import React from 'react';

/**
 * Thin antigravity wrapper over a native radio input. Passes all native props
 * through (`name`, `value`, `checked`, `onChange`, `className`, …) so migration
 * from a raw <input type="radio"> is a straight tag swap.
 */
export type RadioProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'>;

export const Radio = React.forwardRef<HTMLInputElement, RadioProps>(
  (props, ref) => <input ref={ref} type="radio" {...props} />,
);

Radio.displayName = 'Radio';
