/**
 * ESLint flat config for the ReloPass frontend.
 *
 * To run:
 *   cd frontend && npx eslint src --ext .ts,.tsx
 *
 * AUDIT-A6 (AIQ-359): initial config wires up the custom no-clickable-div rule.
 * AUDIT-A6-followup (AIQ-395): adds @typescript-eslint/parser so ESLint can
 * actually parse .ts/.tsx files (without this every file errored with
 * "Parsing error" because the default espree parser doesn't understand TS syntax).
 */

import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import noClickableDiv from './eslint-rules/no-clickable-div.js';
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [
  {
    // Apply to all TypeScript/TSX source files
    files: ['src/**/*.{ts,tsx}'],

    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
    },

    plugins: {
      '@typescript-eslint': tsPlugin,
      /**
       * "local" namespace for project-specific custom rules.
       * Usage: 'local/no-clickable-div': 'error'
       */
      local: {
        rules: {
          'no-clickable-div': noClickableDiv,
        },
      },

      /**
       * jsx-a11y: WCAG-aligned accessibility rules for JSX elements.
       * MVP-9 / AUDIT-A6: enforces aria-label on interactive elements,
       * proper label associations for inputs, alt text on images, etc.
       */
      'jsx-a11y': jsxA11y,
    },

    rules: {
      /**
       * Prohibit <div onClick={...}> (and other non-interactive elements) without
       * role + tabIndex + onKeyDown. WCAG 2.1 SC 2.1.1 (Keyboard).
       *
       * Error — this is a hard accessibility blocker. Clicking divs without
       * keyboard support excludes all keyboard-only and switch-access users.
       */
      'local/no-clickable-div': 'error',

      /**
       * AUDIT-A8: Ban direct console.* calls in application code.
       * Use the logger wrapper (src/lib/logger.ts) instead — it no-ops in production.
       * The logger module itself is exempt via the override block below.
       */
      'no-console': 'error',

      // jsx-a11y: key WCAG 2.1 rules for interactive elements and form inputs
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-proptypes': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/no-redundant-roles': 'warn',
      // Warn (not error) on missing aria-label — many icon buttons are already fixed
      // but some may remain in lower-priority screens. Escalate to error after a
      // full sweep (see AUDIT-A6 known gaps).
      'jsx-a11y/interactive-supports-focus': 'warn',
    },
  },

  {
    // logger.ts is the one place allowed to call console directly
    files: ['src/lib/logger.ts'],
    rules: {
      'no-console': 'off',
    },
  },

  {
    // eval_*.ts and *_pipeline.ts are Node.js CLI scripts that intentionally
    // write to stdout/stderr as their primary output. console.* is fine here.
    files: [
      'src/features/policy-builder/eval_*.ts',
      'src/features/policy-builder/eval_*.ts',
      'src/features/policy-builder/*_pipeline.ts',
      'src/features/policy-builder/__tests__/**',
    ],
    rules: {
      'no-console': 'off',
    },
  },

  {
    // Synthetic test case for the rule — proves the rule fires on a bare <div onClick>
    // Run: npx eslint eslint-rules/__tests__/no-clickable-div.test-fixture.jsx
    files: ['eslint-rules/__tests__/**'],
    plugins: {
      local: {
        rules: {
          'no-clickable-div': noClickableDiv,
        },
      },
    },
    rules: {
      'local/no-clickable-div': 'error',
    },
  },
];
