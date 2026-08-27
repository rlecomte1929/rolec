/**
 * RuleTester coverage for local/no-low-contrast-text.
 *
 * The rule auto-fixes ~890 occurrences across ~200 files in one sweep, so the fixer
 * has to be exactly right — a bad rewrite corrupts JSX at scale. These cases pin the
 * parts that can silently go wrong: variant prefixes, template-literal quasis (where
 * the fix is a range replacement), quote style, and the tokens that must NOT match.
 */
import { RuleTester } from 'eslint';
import tseslint from 'typescript-eslint';
import { describe, it } from 'vitest';
// @ts-expect-error — plain .js ESLint rule, no types
import rule from '../no-low-contrast-text.js';

// MUST be the parser the project actually lints with. The first version of this
// test used espree and passed, while the real sweep (which runs @typescript-eslint/
// parser) corrupted 13 files — the two parsers disagree on whether
// TemplateElement.range includes the backtick/`${` delimiters. Testing with a
// different parser than production is testing a different rule.
const ruleTester = new RuleTester({
  languageOptions: {
    parser: tseslint.parser as never,
    ecmaVersion: 2022,
    sourceType: 'module',
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
});

describe('local/no-low-contrast-text', () => {
  it('passes RuleTester', () => {
    ruleTester.run('no-low-contrast-text', rule, {
      valid: [
        // already compliant
        `const a = "text-slate-500";`,
        `const a = "text-gray-600 font-medium";`,
        // NOT text — borders/backgrounds in the same greys are out of scope, and
        // sweeping them would triple the diff for no contrast gain.
        `const a = "border-slate-400";`,
        `const a = "border-[#cbd5e1] bg-slate-300";`,
        `const a = "fill-gray-400";`,
        // substring traps: these must not be mangled
        `const a = "text-slate-4000";`,
        `const a = "mytext-slate-400";`,
        `const a = "text-slate-40";`,
      ],
      invalid: [
        {
          code: `const a = "text-slate-400";`,
          output: `const a = "text-slate-500";`,
          errors: 1,
        },
        {
          // the lighter 300 tier has no compliant token below 500, so it collapses
          code: `const a = "text-slate-300";`,
          output: `const a = "text-slate-500";`,
          errors: 1,
        },
        {
          code: `const a = "text-gray-400 text-xs";`,
          output: `const a = "text-gray-500 text-xs";`,
          errors: 1,
        },
        {
          // raw hex routes to the matching family: #94a3b8 IS slate-400
          code: `const a = "text-[#94a3b8]";`,
          output: `const a = "text-slate-500";`,
          errors: 1,
        },
        {
          // #9ca3af IS gray-400
          code: `const a = "text-[#9ca3af]";`,
          output: `const a = "text-gray-500";`,
          errors: 1,
        },
        {
          // variant prefixes must survive the rewrite
          code: `const a = "placeholder:text-slate-400";`,
          output: `const a = "placeholder:text-slate-500";`,
          errors: 1,
        },
        {
          code: `const a = "group-hover:text-gray-400 marker:text-slate-400";`,
          output: `const a = "group-hover:text-gray-500 marker:text-slate-500";`,
          errors: 2,
        },
        {
          // legacy pre-Tailwind-3 placeholder syntax
          code: `const a = "placeholder-gray-400";`,
          output: `const a = "placeholder-gray-500";`,
          errors: 1,
        },
        {
          // single quotes preserved
          code: `const a = 'text-slate-400';`,
          output: `const a = 'text-slate-500';`,
          errors: 1,
        },
        {
          // template literal: only the static quasi is rewritten, the interpolation
          // is left completely alone. This is the fixer path most likely to corrupt.
          code: 'const a = `text-slate-400 ${x} p-2`;',
          output: 'const a = `text-slate-500 ${x} p-2`;',
          errors: 1,
        },
        {
          // a banned token in the SECOND quasi, after an interpolation
          code: 'const a = `p-2 ${x} text-gray-300`;',
          output: 'const a = `p-2 ${x} text-gray-500`;',
          errors: 1,
        },
        {
          // real JSX shape
          code: `const el = <p className="mt-1 text-xs text-slate-400">hi</p>;`,
          output: `const el = <p className="mt-1 text-xs text-slate-500">hi</p>;`,
          errors: 1,
        },
        {
          // REGRESSION (HrTeamList.tsx:545 and 12 other files): a hex token in the
          // first quasi of a JSX className template with an interpolation after it.
          // The whole-node fixer ate the opening backtick AND the `${`, producing
          //   className={flex-shrink-0 … isExpanded ? 'rotate-180' : ''}`}
          // which is a syntax error. The delimiters must survive untouched.
          code:
            "const el = <svg className={`flex-shrink-0 text-[#9ca3af] transition-transform " +
            "${isExpanded ? 'rotate-180' : ''}`} />;",
          output:
            "const el = <svg className={`flex-shrink-0 text-gray-500 transition-transform " +
            "${isExpanded ? 'rotate-180' : ''}`} />;",
          errors: 1,
        },
        {
          // ternary inside a JSX expression container — both branches are Literals
          code: `const el = <span className={v ? 'text-[#374151]' : 'text-[#9ca3af]'} />;`,
          output: `const el = <span className={v ? 'text-[#374151]' : 'text-gray-500'} />;`,
          errors: 1,
        },
      ],
    });
  });
});
