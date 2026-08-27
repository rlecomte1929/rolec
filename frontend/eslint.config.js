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
import importPlugin from 'eslint-plugin-import';
import noClickableDiv from './eslint-rules/no-clickable-div.js';
import noLowContrastText from './eslint-rules/no-low-contrast-text.js';

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
    // LINT-4 (AIQ-1196): fail on eslint-disable comments that no longer suppress
    // anything, so the dead-disable backlog can't silently grow back.
    linterOptions: {
      reportUnusedDisableDirectives: 'error',
    },
    settings: {
      react: { version: 'detect' },
      // LINT-5 (AIQ-1197): resolve TS path imports via eslint-import-resolver-typescript.
      'import/resolver': {
        typescript: { alwaysTryTypes: true },
        node: true,
      },
    },
    languageOptions: {
      parserOptions: {
        // Enables type-aware linting (no-floating-promises, no-unsafe-*, etc.).
        // LINT-3 close: point at tsconfig.eslint.json (extends tsconfig.json, but
        // INCLUDES the test files the deploy build excludes) so the type-aware rules
        // cover tests too — otherwise tests report "not found by project service"
        // parse errors, which would fail a blocking lint gate.
        project: ['./tsconfig.eslint.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      // "local" namespace for project-specific custom rules.
      local: {
        rules: {
          'no-clickable-div': noClickableDiv,
          'no-low-contrast-text': noLowContrastText,
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
      // LINT-5: import-hygiene plugin (unresolved imports, cycles, ordering).
      import: importPlugin,
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
      // A11Y-2 / AIQ-1211. The convention has been in DESIGN.md since June and
      // usage still grew 76% because nothing enforced it. Auto-fixable.
      'local/no-low-contrast-text': 'error',

      /**
       * AUDIT-A8: ban direct console.* in app code — use src/lib/logger.ts
       * (no-ops in production). logger.ts itself is exempt below.
       */
      'no-console': 'error',

      // LINT-5 (AIQ-1197): import hygiene.
      // Unresolved imports are real bugs (the dead-router / wrong-path class) — error.
      'import/no-unresolved': 'error',
      // Cycles surface architectural debt; warn so they're visible without blocking.
      'import/no-cycle': 'warn',
      // Consistent ordering — warn + autofixable; drained incrementally (not mass-fixed here).
      'import/order': [
        'warn',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          'newlines-between': 'never',
        },
      ],
      // TS already validates named exports/imports; the import/* equivalents only
      // duplicate that (and are slow), so leave them off.
      'import/named': 'off',
      'import/namespace': 'off',
      'import/default': 'off',
      'import/no-named-as-default-member': 'off',
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
    // their primary output; their tests likewise. The src/perf/* + *Perf + staleness
    // modules are diagnostic/instrumentation utilities whose console output IS their
    // purpose. console.* is fine in all of these.
    files: [
      'src/features/policy-builder/eval_*.ts',
      'src/features/policy-builder/*_pipeline.ts',
      'src/features/policy-builder/__tests__/**',
      'src/perf/**',
      'src/utils/employeeJourneyPerf.ts',
      'src/utils/staleness.ts',
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
          'no-low-contrast-text': noLowContrastText,
        },
      },
    },
    rules: {
      'local/no-clickable-div': 'error',
      // A11Y-2 / AIQ-1211. The convention has been in DESIGN.md since June and
      // usage still grew 76% because nothing enforced it. Auto-fixable.
      'local/no-low-contrast-text': 'error',
    },
  },

  {
    // LINT-3 (AIQ-1195) — PRAGMATIC CLOSE. The full no-unsafe-* / a11y / promise
    // backlog is genuinely multi-week structural work; rather than block QG-1 on it,
    // demote those large manual rule-families to non-blocking `warn` so CI can gate
    // *real* errors on a 0-error baseline today. The warn-backlogs are tracked as
    // dedicated epics (TS type-safety, accessibility, async-safety) that re-promote
    // each rule to `error` as it drains to 0. Rules kept at `error` (the live gate):
    // react-hooks/rules-of-hooks, no-console, no-unused-vars, import/no-unresolved,
    // reportUnusedDisableDirectives.
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      // Underscore-prefixed args/vars and unused catch bindings are intentional.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],

      // — TS type-safety epic (the no-unsafe-* family stems from untyped API responses) —
      '@typescript-eslint/no-unsafe-member-access': 'error',
      '@typescript-eslint/no-unsafe-assignment': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/no-unsafe-argument': 'error',
      '@typescript-eslint/no-unsafe-call': 'error',
      '@typescript-eslint/no-unsafe-enum-comparison': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-base-to-string': 'error',
      '@typescript-eslint/restrict-template-expressions': 'error',

      // — Async-safety epic —
      // no-misused-promises: DRAINED + re-promoted to 'error' (Epic A2). The
      // `checksVoidReturn.attributes: false` opt-out stops flagging async JSX event
      // handlers (onClick={asyncFn} etc.) — idiomatic + safe in React (React ignores
      // the returned promise; rejection-safety is no-floating-promises' job, already
      // enforced). The dangerous misuses (async passed to a void-expecting *function
      // argument* — subscriptions, timers) ARE still caught and were fixed in A2.
      '@typescript-eslint/no-misused-promises': ['error', { checksVoidReturn: { attributes: false } }],
      // no-floating-promises: DRAINED to 0 + re-promoted to 'error' (reverts to the
      // recommendedTypeChecked default) — Epic A1. New floating promises now fail CI.

      // — Accessibility epic (clickable-div + jsx-a11y) —
      // Epic C / R-CLICK: DRAINED to 0 + re-promoted to 'error' (with its ride-along rules below).
      'local/no-clickable-div': 'error',
      // A11Y-2 / AIQ-1211. The convention has been in DESIGN.md since June and
      // usage still grew 76% because nothing enforced it. Auto-fixable.
      'local/no-low-contrast-text': 'error',
      // label-has-associated-control: DRAINED to 0 + re-promoted to 'error' (Epic C / R1).
      // controlComponents recognises the antigravity wrappers that render native form controls.
      // Select (antigravity) is NOT listed — it doesn't expose id, so pairs use native <select> with id instead.
      'jsx-a11y/label-has-associated-control': ['error', {
        controlComponents: ['Checkbox', 'Input', 'FileInput', 'Radio'],
        depth: 3,
      }],
      'jsx-a11y/click-events-have-key-events': 'error',
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/no-noninteractive-element-interactions': 'error',
      // Epic C / R3: DRAINED to 0 + re-promoted to 'error'. These now fail CI on any new violation.
      'jsx-a11y/no-redundant-roles': 'error',
      // Epic C / R-AUTOFOCUS: DRAINED to 0 + re-promoted to 'error'.
      'jsx-a11y/no-autofocus': 'error',
      'jsx-a11y/interactive-supports-focus': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/no-noninteractive-element-to-interactive-role': 'error',

      // — Cosmetic / low-count, demoted for now (tracked for follow-up; several are
      //   trivially fixable and should be drained + re-promoted in the epics) —
      'react/no-unescaped-entities': 'error',
      'react/prop-types': 'warn',
      // Drained to 0 and promoted (frontend-hygiene pass, 2026-06-30) so they can't regress.
      'no-constant-binary-expression': 'error',
      '@typescript-eslint/no-redundant-type-constituents': 'warn',
      '@typescript-eslint/no-unnecessary-type-assertion': 'warn',
      '@typescript-eslint/require-await': 'warn',
      '@typescript-eslint/await-thenable': 'warn',
      '@typescript-eslint/prefer-promise-reject-errors': 'warn',
      '@typescript-eslint/only-throw-error': 'warn',
      '@typescript-eslint/no-unused-expressions': 'warn',
      'no-useless-escape': 'error',
      'no-empty': 'error',
      'prefer-const': 'error',
    },
  },

  {
    // Test files (now in the lint TS project so they parse) follow different
    // conventions: console for debugging, setup imports that look unused, and
    // unbound-method noise from vitest mocks passing methods around. Relax those.
    // MUST come after the LINT-3-close block above so these win for test files.
    files: ['src/**/*.test.{ts,tsx}', 'src/**/__tests__/**'],
    rules: {
      'no-console': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/unbound-method': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-return': 'off',
      '@typescript-eslint/no-unsafe-argument': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-base-to-string': 'off',
      '@typescript-eslint/restrict-template-expressions': 'off',
    },
  },
);
