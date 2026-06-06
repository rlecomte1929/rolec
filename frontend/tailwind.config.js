/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        marketing: {
          primary: 'var(--marketing-primary)',
          'primary-muted': 'var(--marketing-primary-muted)',
          accent: 'var(--marketing-accent)',
          'accent-muted': 'var(--marketing-accent-muted)',
          surface: 'var(--marketing-surface)',
          'surface-subtle': 'var(--marketing-surface-subtle)',
          'surface-muted': 'var(--marketing-surface-muted)',
          text: 'var(--marketing-text)',
          'text-muted': 'var(--marketing-text-muted)',
          'text-subtle': 'var(--marketing-text-subtle)',
          border: 'var(--marketing-border)',
          'border-subtle': 'var(--marketing-border-subtle)',
        },
        // ReloPass brand scales — source of truth: design/system/tokens.css.
        // navy = primary (actions/structure); accent = teal (links/accents,
        // used sparingly per the Branding Blueprint). These replace the
        // off-brand violet/indigo/purple drift — there is no purple in the brand.
        navy: {
          50: '#f0f5fa', 100: '#d6e4f0', 200: '#adc9e1', 300: '#7fa5c8',
          400: '#4d7fac', 500: '#2d5f8e', 600: '#1f4870', 700: '#133456',
          800: '#0b2b43', 900: '#061a2a',
        },
        accent: {
          50: '#ebf7f6', 100: '#d2eceb', 200: '#a4d8d6', 300: '#6ec0bd',
          400: '#3aa6a3', 500: '#1f8e8b', 600: '#167572', 700: '#105d5b',
          800: '#0b4543', 900: '#062d2c',
        },
      },
      maxWidth: {
        'marketing': 'var(--marketing-container)',
        'marketing-narrow': 'var(--marketing-container-narrow)',
        'marketing-wide': 'var(--marketing-container-wide)',
      },
      spacing: {
        'section': 'var(--marketing-space-section)',
        'section-sm': 'var(--marketing-space-section-sm)',
        'block': 'var(--marketing-space-block)',
        'block-sm': 'var(--marketing-space-block-sm)',
      },
      fontSize: {
        'marketing-display': ['var(--marketing-font-display)', { lineHeight: '1.15' }],
        'marketing-hero': ['var(--marketing-font-hero)', { lineHeight: '1.12' }],
        'marketing-hero-lg': ['var(--marketing-font-hero-lg)', { lineHeight: '1.1' }],
        'marketing-h1': ['var(--marketing-font-h1)', { lineHeight: '1.3' }],
        'marketing-h2': ['var(--marketing-font-h2)', { lineHeight: '1.35' }],
        'marketing-h3': ['var(--marketing-font-h3)', { lineHeight: '1.4' }],
        'marketing-body-lg': ['var(--marketing-font-body-lg)', { lineHeight: '1.6' }],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out forwards',
      },
    },
  },
  plugins: [],
}
