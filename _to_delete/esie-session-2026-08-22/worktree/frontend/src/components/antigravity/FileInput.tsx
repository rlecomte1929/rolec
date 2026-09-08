import React from 'react';

/**
 * Thin antigravity wrapper over a native file input. Passes all native props
 * through (`accept`, `multiple`, `onChange`, `className`, `style`, …) and
 * forwards `ref` (file inputs are commonly hidden and triggered via a button
 * ref). Migration from a raw <input type="file"> is a straight tag swap.
 */
export type FileInputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'>;

export const FileInput = React.forwardRef<HTMLInputElement, FileInputProps>(
  (props, ref) => <input ref={ref} type="file" {...props} />,
);

FileInput.displayName = 'FileInput';
