/**
 * Tailwind config for apps/hr-dashboard.
 *
 * Theme extension block is the literal `_tailwind_extension_hint` from
 * design/system/shadcn-theme.json. When that JSON changes, update this file in
 * lockstep — they are intended to mirror each other and the design system seed
 * is the source of truth (see design/system/README.md).
 *
 * Color tokens come through CSS variables (var(--rp-*)) defined in
 * design/system/tokens.css, which is imported by src/index.css.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // shadcn/ui contract — every name maps to a --rp-* token (see
        // design/system/shadcn-theme.json cssVars.light).
        background: 'var(--rp-surface)',
        foreground: 'var(--rp-text-primary)',
        card: 'var(--rp-surface)',
        'card-foreground': 'var(--rp-text-primary)',
        popover: 'var(--rp-surface)',
        'popover-foreground': 'var(--rp-text-primary)',
        primary: {
          DEFAULT: 'var(--rp-color-primary-600)',
          foreground: 'var(--rp-text-inverse)',
        },
        secondary: {
          DEFAULT: 'var(--rp-color-secondary-500)',
          foreground: 'var(--rp-text-inverse)',
        },
        muted: {
          DEFAULT: 'var(--rp-surface-subtle)',
          foreground: 'var(--rp-text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--rp-color-secondary-50)',
          foreground: 'var(--rp-color-secondary-700)',
        },
        destructive: {
          DEFAULT: 'var(--rp-color-danger-500)',
          foreground: 'var(--rp-text-inverse)',
        },
        success: {
          DEFAULT: 'var(--rp-color-success-500)',
          foreground: 'var(--rp-text-inverse)',
        },
        warning: {
          DEFAULT: 'var(--rp-color-warning-500)',
          foreground: 'var(--rp-color-warning-700)',
        },
        border: 'var(--rp-border-default)',
        input: 'var(--rp-border-default)',
        ring: 'var(--rp-color-primary-500)',
      },
      spacing: {
        1: 'var(--rp-space-1)',
        2: 'var(--rp-space-2)',
        3: 'var(--rp-space-3)',
        4: 'var(--rp-space-4)',
        6: 'var(--rp-space-6)',
        8: 'var(--rp-space-8)',
        12: 'var(--rp-space-12)',
        16: 'var(--rp-space-16)',
      },
      fontSize: {
        xs: 'var(--rp-text-xs)',
        sm: 'var(--rp-text-sm)',
        base: 'var(--rp-text-base)',
        md: 'var(--rp-text-md)',
        lg: 'var(--rp-text-lg)',
        xl: 'var(--rp-text-xl)',
        '2xl': 'var(--rp-text-2xl)',
        '3xl': 'var(--rp-text-3xl)',
      },
      borderRadius: {
        sm: 'var(--rp-radius-sm)',
        md: 'var(--rp-radius-md)',
        lg: 'var(--rp-radius-lg)',
        xl: 'var(--rp-radius-xl)',
        full: 'var(--rp-radius-full)',
      },
      boxShadow: {
        sm: 'var(--rp-shadow-sm)',
        md: 'var(--rp-shadow-md)',
        lg: 'var(--rp-shadow-lg)',
        xl: 'var(--rp-shadow-xl)',
        focus: 'var(--rp-shadow-focus)',
      },
      transitionDuration: {
        fast: 'var(--rp-duration-fast)',
        base: 'var(--rp-duration-base)',
        slow: 'var(--rp-duration-slow)',
      },
      transitionTimingFunction: {
        out: 'var(--rp-easing-out)',
        'in-out': 'var(--rp-easing-in-out)',
        spring: 'var(--rp-easing-spring)',
      },
      zIndex: {
        tooltip: 'var(--rp-z-tooltip)',
        dropdown: 'var(--rp-z-dropdown)',
        overlay: 'var(--rp-z-overlay)',
        dialog: 'var(--rp-z-dialog)',
        toast: 'var(--rp-z-toast)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
