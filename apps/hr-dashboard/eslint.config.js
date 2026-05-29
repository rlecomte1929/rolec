/**
 * ESLint flat config for apps/hr-dashboard. Mirrors frontend/eslint.config.js
 * (typescript-eslint + jsx-a11y) but without the legacy frontend-only custom
 * rules — those will be ported if/when they prove relevant here.
 */

import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [
  {
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
      'jsx-a11y': jsxA11y,
    },
    rules: {
      // No raw console.* in app code — wrap with the (eventual) logger.
      'no-console': 'error',

      // jsx-a11y essentials (same set frontend/ uses for HR/admin surfaces)
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-proptypes': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/no-redundant-roles': 'warn',
      'jsx-a11y/interactive-supports-focus': 'warn',
    },
  },
];
