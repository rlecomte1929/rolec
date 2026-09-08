import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
}) => {
  const variants = {
    success: 'bg-[#eaf5f4] text-[#1f8e8b]',
    warning: 'bg-[#f4efe5] text-[#7a5e2a]',
    error: 'bg-[#f4e9e9] text-[#7a2a2a]',
    info: 'bg-[#eaf1f7] text-[#0b2b43]',
    neutral: 'bg-[#f3f4f6] text-[#374151]',
  };
  
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  };
  
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${variants[variant]} ${sizes[size]}`}>
      {children}
    </span>
  );
};
