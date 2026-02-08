import React from 'react';

interface AlertProps {
  children: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = 'info',
  title,
}) => {
  const variants = {
    info: 'bg-[#eef4f8] border-[#c7d8e6] text-[#0b2b43]',
    success: 'bg-[#eef7f6] border-[#c6e2df] text-[#1f8e8b]',
    warning: 'bg-[#f6f2e9] border-[#e2d6bf] text-[#7a5e2a]',
    error: 'bg-[#f7eeee] border-[#e6c9c9] text-[#7a2a2a]',
  };
  
  return (
    <div className={`border-l-4 p-4 rounded ${variants[variant]}`}>
      {title && <h3 className="font-semibold mb-1">{title}</h3>}
      <div className="text-sm">{children}</div>
    </div>
  );
};
