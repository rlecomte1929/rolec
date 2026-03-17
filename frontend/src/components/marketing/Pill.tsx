import React from 'react';

interface PillProps {
  children: React.ReactNode;
  /** Style variant */
  variant?: 'default' | 'accent' | 'muted' | 'outline';
  size?: 'sm' | 'md';
  className?: string;
}

export const Pill: React.FC<PillProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
}) => {
  const variants = {
    default: 'bg-marketing-surface-muted text-marketing-text-muted',
    accent: 'bg-marketing-accent/10 text-marketing-accent',
    muted: 'bg-marketing-surface-subtle text-marketing-text-subtle',
    outline: 'border border-marketing-border text-marketing-text-muted',
  };

  const sizes = {
    sm: 'px-2.5 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </span>
  );
};
