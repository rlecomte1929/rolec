import React from 'react';

interface SkeletonProps {
  /** Tailwind width class or arbitrary value (default w-full). */
  width?: string;
  /** Tailwind height class (default h-4). */
  height?: string;
  /** Rounded variant — 'text' (rounded), 'circle' (rounded-full), 'rect' (rounded-lg). */
  variant?: 'text' | 'circle' | 'rect';
  className?: string;
}

const RADIUS: Record<NonNullable<SkeletonProps['variant']>, string> = {
  text: 'rounded',
  circle: 'rounded-full',
  rect: 'rounded-lg',
};

/**
 * Antigravity Skeleton — one shared loading placeholder (the app had ~34 ad-hoc
 * `animate-pulse` spots). Decorative, so `aria-hidden`; pair with an
 * `aria-busy`/`role="status"` region on the parent for screen readers.
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  width = 'w-full',
  height = 'h-4',
  variant = 'text',
  className = '',
}) => (
  <div
    aria-hidden="true"
    className={`animate-pulse bg-[#e2e8f0] ${RADIUS[variant]} ${width} ${height} ${className}`}
  />
);
