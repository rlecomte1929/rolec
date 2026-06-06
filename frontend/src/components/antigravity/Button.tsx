import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  fullWidth?: boolean;
  type?: 'button' | 'submit';
  className?: string;
  /** Native tooltip (e.g. disabled buttons) */
  title?: string;
  /** Accessible name for icon-only buttons (passed through to the native element) */
  'aria-label'?: string;
  /**
   * Render the semantic <button> with NO design-system styling — only the
   * passed `className`, plus type/onClick/disabled/title/aria-label. For
   * bespoke or container-style buttons (selectable cards, accordion rows,
   * brand-coloured inline actions) whose layout the styled variants would
   * fight. Lets every clickable element route through this one primitive — a
   * single a11y/behaviour chokepoint, no raw <button> — without imposing a
   * visual opinion. Prefer a real `variant` whenever one fits.
   */
  unstyled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled = false,
  fullWidth = false,
  type = 'button',
  className = '',
  title,
  'aria-label': ariaLabel,
  unstyled = false,
}) => {
  const baseStyles = 'font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2';
  
  const variants = {
    primary: 'bg-[#0b2b43] text-white hover:bg-[#123651] focus:ring-[#0b2b43]',
    secondary: 'bg-[#1f8e8b] text-white hover:bg-[#197c79] focus:ring-[#1f8e8b]',
    outline: 'border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43]',
    ghost: 'text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43]',
  };
  
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };
  
  const widthClass = fullWidth ? 'w-full' : '';
  const disabledClass = disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer';

  // `unstyled` callers own their full appearance (incl. disabled/hover states)
  // via className — the design system only lends the semantic element + a11y.
  const composedClassName = unstyled
    ? className
    : `${baseStyles} ${variants[variant]} ${sizes[size]} ${widthClass} ${disabledClass} ${className}`;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={ariaLabel}
      className={composedClassName}
    >
      {children}
    </button>
  );
};
