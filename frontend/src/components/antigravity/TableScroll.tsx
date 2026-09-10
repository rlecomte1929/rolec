import React from 'react';

interface TableScrollProps {
  children: React.ReactNode;
  /** Tailwind min-width for the inner scroller (default matches catalog tables). */
  minWidthClass?: string;
  className?: string;
}

/** Horizontal scroll wrapper — never clip data tables with overflow-hidden. */
export const TableScroll: React.FC<TableScrollProps> = ({
  children,
  minWidthClass = 'min-w-[56rem]',
  className = '',
}) => (
  <div className={`overflow-x-auto ${className}`}>
    <div className={minWidthClass}>{children}</div>
  </div>
);
