import React from 'react';
import { Button } from './Button';

interface LoadingButtonProps {
  children: React.ReactNode;
  onClick?: () => void | Promise<void>;
  loading?: boolean;
  loadingLabel?: string;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  fullWidth?: boolean;
  type?: 'button' | 'submit';
  className?: string;
}

export const LoadingButton: React.FC<LoadingButtonProps> = ({
  children,
  onClick,
  loading = false,
  loadingLabel,
  disabled = false,
  ...rest
}) => {
  const handleClick = async () => {
    if (!onClick || loading) return;
    await onClick();
  };

  return (
    <Button
      {...rest}
      onClick={handleClick}
      disabled={disabled || loading}
      className={`relative ${rest.className || ''}`}
    >
      {loading ? (
        <span className="inline-flex items-center justify-center gap-2" aria-busy="true">
          <svg
            className="animate-spin h-4 w-4 shrink-0"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>{loadingLabel ?? (typeof children === 'string' ? 'Processing…' : children)}</span>
        </span>
      ) : (
        children
      )}
    </Button>
  );
};
