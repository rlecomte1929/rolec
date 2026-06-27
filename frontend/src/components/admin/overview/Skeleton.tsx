import React from 'react';

interface SkeletonProps {
  className?: string;
}

// A muted pulse instead of a bare '…', which read as a broken/WIP value (UI9).
export const Skeleton: React.FC<SkeletonProps> = ({ className }) => (
  <span
    aria-hidden="true"
    className={`inline-block animate-pulse rounded bg-slate-200 align-middle ${className ?? ''}`}
  />
);
