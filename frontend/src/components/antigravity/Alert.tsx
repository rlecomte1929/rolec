import React from 'react';

interface AlertProps {
  children: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  className?: string;
}

// AIQ-397 (AUDIT-A11Y-P2-followup):
//   - error → role="alert" + aria-live="assertive" so screen readers interrupt
//     immediately when something has gone wrong.
//   - info / success / warning → role="status" + aria-live="polite" so the
//     announcement waits its turn (non-interrupting) — matches WCAG SC 4.1.3
//     guidance for transient status messages.
const ARIA_BY_VARIANT: Record<NonNullable<AlertProps['variant']>, { role: 'alert' | 'status'; live: 'assertive' | 'polite' }> = {
  info:    { role: 'status', live: 'polite' },
  success: { role: 'status', live: 'polite' },
  warning: { role: 'status', live: 'polite' },
  error:   { role: 'alert',  live: 'assertive' },
};

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = 'info',
  title,
  className = '',
}) => {
  const variants = {
    info: 'bg-[#eef4f8] border-[#c7d8e6] text-[#0b2b43]',
    // accent-500 on this tint is 3.64:1 — below AA. accent-700 is 7.04:1. The #2069
    // sweep missed it because it matched accent text only against a fixed list of
    // tint backgrounds and #eef7f6 was not on it; Alert is a shared primitive, so
    // this one line covers every success alert in the app.
    success: 'bg-[#eef7f6] border-[#c6e2df] text-[#105d5b]',
    warning: 'bg-[#f6f2e9] border-[#e2d6bf] text-[#7a5e2a]',
    error: 'bg-[#f7eeee] border-[#e6c9c9] text-[#7a2a2a]',
  };
  const aria = ARIA_BY_VARIANT[variant];

  return (
    <div
      role={aria.role}
      aria-live={aria.live}
      className={`border-l-4 p-4 rounded ${variants[variant]} ${className}`}
    >
      {title && <h3 className="font-semibold mb-1">{title}</h3>}
      <div className="text-sm">{children}</div>
    </div>
  );
};
