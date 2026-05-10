import React from 'react';
import { Link } from 'react-router-dom';

type CTAVariant = 'primary' | 'secondary' | 'outline' | 'ghost';
type CTASize = 'sm' | 'md' | 'lg';

interface CTAButtonBaseProps {
  children: React.ReactNode;
  variant?: CTAVariant;
  size?: CTASize;
  fullWidth?: boolean;
  className?: string;
}

interface CTAButtonAsButton extends CTAButtonBaseProps {
  to?: never;
  href?: never;
  onClick?: () => void;
  type?: 'button' | 'submit';
}

interface CTAButtonAsLink extends CTAButtonBaseProps {
  to: string;
  onClick?: never;
  type?: never;
}

interface CTAButtonAsAnchor extends CTAButtonBaseProps {
  href: string;
  to?: never;
  onClick?: never;
  type?: never;
}

type CTAButtonProps = CTAButtonAsButton | CTAButtonAsLink | CTAButtonAsAnchor;

const variants: Record<CTAVariant, string> = {
  primary:
    'bg-marketing-primary text-white hover:bg-marketing-primary-muted focus:ring-marketing-primary',
  secondary:
    'bg-marketing-accent text-white hover:bg-marketing-accent-muted focus:ring-marketing-accent',
  outline:
    'border-2 border-marketing-primary text-marketing-primary hover:bg-marketing-surface-muted focus:ring-marketing-primary',
  ghost:
    'text-marketing-primary hover:bg-marketing-surface-muted focus:ring-marketing-primary',
};

const sizes: Record<CTASize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-6 py-3 text-base',
};

const baseStyles =
  'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';

export const CTAButton: React.FC<CTAButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  ...rest
}) => {
  const classes = [
    baseStyles,
    variants[variant],
    sizes[size],
    fullWidth ? 'w-full' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if ('to' in rest && rest.to) {
    return (
      <Link to={rest.to} className={classes}>
        {children}
      </Link>
    );
  }

  if ('href' in rest && rest.href) {
    return (
      <a
        href={rest.href}
        target="_blank"
        rel="noopener noreferrer"
        className={classes}
      >
        {children}
      </a>
    );
  }

  const { type = 'button', onClick } = rest as CTAButtonAsButton;
  return (
    <button type={type} onClick={onClick} className={classes}>
      {children}
    </button>
  );
};
