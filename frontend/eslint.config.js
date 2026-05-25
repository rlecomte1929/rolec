/**
 * ESLint flat config for the ReloPass frontend.
 *
 * To run:
 *   cd frontend && npx eslint src --ext .ts,.tsx
 *
 * AUDIT-A6 (AIQ-359): initial config wires up the custom no-clickable-div rule.
 * Add eslint-plugin-react, @typescript-eslint, and eslint-plugin-jsx-a11y as
 * needed when ESLint is added to package.json and CI.
 */

import noClickableDiv from './eslint-rules/no-clickable-div.js';

export default [
  {
    // Apply to all TypeScript/TSX source files
    files: ['src/**/*.{ts,tsx}'],

    plugins: {
      /**
       * "local" namespace for project-specific custom rules.
       * Usage: 'local/no-clickable-div': 'error'
       */
      local: {
        rules: {
          'no-clickable-div': noClickableDiv,
        },
      },
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
