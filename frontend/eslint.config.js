/**
 * ESLint flat config for the ReloPass frontend.
 *
 * To run:
 *   cd frontend && npx eslint src --ext .ts,.tsx
 *
 * AUDIT-A6 (AIQ-359): initial config wires up the custom no-clickable-div rule.
 * AUDIT-A6-followup (AIQ-395): adds @typescript-eslint/parser so ESLint can parse TS.
 * LINT-1 (AIQ-1193): the config was "theater" — ~8 hand rules, extended no recommended
 *   ruleset, and the parser was set but `projectService` was not, so type-aware rules
 *   silently no-op'd. This enriches it with:
 *     - @eslint/js                              `recommended`
 *     - typescript-eslint                       `recommendedTypeChecked` (type-aware)
 *     - eslint-plugin-jsx-a11y                  `flatConfigs.recommended`
 *   and turns on `projectService` so no-floating-promises / no-misused-promises /
 *   no-unsafe-* actually run. The project-specific rules (local/no-clickable-div,
 *   no-console) are preserved.
 *
 *   NOTE: enabling these rulesets surfaces a large pre-existing backlog by design.
 *   Draining it is LINT-3; making the lint step CI-blocking is QG-1. Do NOT gate on
 *   zero violations here — `npx eslint src` is expected to report findings.
 */

import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import noClickableDiv from './eslint-rules/no-clickable-div.js';

export default tseslint.config(
  {
    // Application source — full recommended + type-aware + a11y rulesets.
    files: ['src/**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      // LINT-2 (AIQ-1194): react + react-hooks were never installed, so the 20
      // exhaustive-deps/no-danger disable comments scattered through the app
      // targeted rules that did not exist (phantom "rule not found" errors) and
      // Rules of Hooks were entirely unenforced. jsx-runtime drops the stale
      // "React must be in scope" rules (the project uses the automatic JSX runtime).
      react.configs.flat.recommended,
      react.configs.flat['jsx-runtime'],
      jsxA11y.flatConfigs.recommended,
    ],
    settings: {
      react: { version: 'detect' },
    },
    languageOptions: {
      parserOptions: {
        // Enables type-aware linting (no-floating-promises, no-unsafe-*, etc.).
        // Without projectService the type-checked rules are parsed but never run.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      // "local" namespace for project-specific custom rules.
      local: {
        rules: {
          'no-clickable-div': noClickableDiv,
        },
      },
      // react-hooks plugin (v7). NOTE: v7's `recommended` also enables the new
      // React Compiler rule set (react-hooks/set-state-in-effect, purity,
      // static-components, immutability, refs …) — a large, separate adoption
      // decision the codebase hasn't made. We deliberately enable only the classic
      // Rules of Hooks + exhaustive-deps here (the audit's intent + what the 20
      // phantom disables target); the compiler rules can be turned on later as a
      // deliberate, scoped follow-up.
      'react-hooks': reactHooks,
    },
    rules: {
      // Classic Rules of Hooks — real bugs (conditional hooks, wrong call order).
      'react-hooks/rules-of-hooks': 'error',
      // Stale-closure guard — warn (the existing disables target exactly this rule).
      'react-hooks/exhaustive-deps': 'warn',

      /**
       * Prohibit <div onClick={...}> without role + tabIndex + onKeyDown.
       * WCAG 2.1 SC 2.1.1 (Keyboard). Hard accessibility blocker.
       */
      'local/no-clickable-div': 'error',

      /**
       * AUDIT-A8: ban direct console.* in app code — use src/lib/logger.ts
       * (no-ops in production). logger.ts itself is exempt below.
       */
      'no-console': 'error',
    },
  },

  {
    // logger.ts is the one place allowed to call console directly.
    files: ['src/lib/logger.ts'],
    rules: {
      'no-console': 'off',
    },
  },

  {
    // eval_*.ts and *_pipeline.ts are Node CLI scripts that write to stdout as
    // their primary output; their tests likewise. console.* is fine here.
    files: [
      'src/features/policy-builder/eval_*.ts',
      'src/features/policy-builder/*_pipeline.ts',
      'src/features/policy-builder/__tests__/**',
    ],
    rules: {
      'no-console': 'off',
    },
  },

  {
    // Synthetic test case for the custom rule — JS/JSX, not part of the TS program,
    // so disable type-aware rules and just assert the custom rule fires.
    files: ['eslint-rules/__tests__/**'],
    extends: [tseslint.configs.disableTypeChecked],
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
);
