import React from 'react';

export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <span
    aria-hidden="true"
    className={`inline-block animate-pulse rounded bg-slate-200 align-middle ${className ?? ''}`}
  />
);
