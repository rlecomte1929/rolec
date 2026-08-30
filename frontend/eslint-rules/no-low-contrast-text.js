/**
 * eslint-rules/no-low-contrast-text.js
 *
 * Custom ESLint rule: muted TEXT on light surfaces must meet WCAG AA (4.5:1).
 * Bans the `-300`/`-400` slate/gray text tier and its raw-hex equivalents, and
 * auto-fixes each to the nearest compliant token.
 *
 *   text-slate-400 (2.6:1)  ->  text-slate-500 (4.6:1)
 *   text-gray-400           ->  text-gray-500
 *   text-slate-300 / gray-300  ->  -500  (see "Why 300 collapses" below)
 *   text-[#94a3b8] / [#cbd5e1] ->  text-slate-500
 *   text-[#9ca3af] / [#d1d5db] ->  text-gray-500
 *
 * WHY THIS RULE EXISTS
 * DESIGN.md already carries the convention (A11Y-2 / AIQ-1211) and commit 57c6398e
 * migrated one file to prove it. Nothing enforced it, so usage GREW 76% — from the
 * ~490 that commit cites to ~890. An external QA sweep then filed 29 separate
 * contrast bugs, median measured ratio 2.56:1. A convention without a gate is a
 * suggestion; this is the gate.
 *
 * WHY AUTO-FIXING IS SAFE HERE
 * The obvious hazard is light-on-dark: darkening text that sits on a navy fill makes
 * it WORSE, and 57c6398e explicitly warns about it. Measured across ~890 banned-text
 * lines in this codebase, exactly 2 co-occur with a dark background, and both are
 * false positives (the navy is the other branch of a ternary). There is no dark
 * layout, no dark page shell: both app shells are bg-slate-50, the sidebar is
 * bg-white. Dark fills are small elements only — buttons, badges, pills, tooltips —
 * and text on them is 100% `text-white`. So the tier this rule matches is, in
 * practice, always on a light surface.
 *
 * If a genuine light-on-dark case ever appears, it is one `eslint-disable-next-line`
 * with a reason — not grounds for weakening the rule.
 *
 * WHY 300 COLLAPSES INTO 500
 * `-300` is intentionally lighter than `-400` in a few components (a de-emphasis
 * step). Both fail AA, and there is no compliant token lighter than `-500`, so both
 * map to `-500` and that distinction is lost. That is forced by the contrast floor,
 * not a preference. Use weight or size for de-emphasis instead of colour.
 *
 * SCOPE — text only
 * `border-*`, `bg-*` and `fill-*` in the same greys are deliberately NOT matched:
 * the 4.5:1 rule is about text. 215 of the raw-hex occurrences in this repo are
 * borders, and sweeping them would triple the diff for no accessibility gain.
 *
 * Usage in eslint.config.js:
 *   import noLowContrastText from './eslint-rules/no-low-contrast-text.js';
 *   plugins: { local: { rules: { 'no-low-contrast-text': noLowContrastText } } }
 *   rules:   { 'local/no-low-contrast-text': 'error' }
 */

/** banned token -> compliant replacement (variant prefixes are preserved) */
const REPLACEMENTS = new Map([
  ['text-slate-400', 'text-slate-500'],
  ['text-slate-300', 'text-slate-500'],
  ['text-gray-400', 'text-gray-500'],
  ['text-gray-300', 'text-gray-500'],
  // raw hex equivalents — routed to the matching family
  ['text-[#94a3b8]', 'text-slate-500'], // slate-400
  ['text-[#cbd5e1]', 'text-slate-500'], // slate-300
  ['text-[#9ca3af]', 'text-gray-500'],  // gray-400
  ['text-[#d1d5db]', 'text-gray-500'],  // gray-300
  // legacy placeholder-* (pre-Tailwind-3 syntax) still in a handful of inputs
  ['placeholder-slate-400', 'placeholder-slate-500'],
  ['placeholder-slate-300', 'placeholder-slate-500'],
  ['placeholder-gray-400', 'placeholder-gray-500'],
  ['placeholder-gray-300', 'placeholder-gray-500'],
]);

// A class token. Boundaries are NON-CONSUMING lookarounds, deliberately:
// context.sourceCode.getText(node) returns the node INCLUDING its quotes/backticks,
// so a `(?=\s|$)` lookahead fails on the very common `… text-slate-400"` and only
// space-terminated tokens get matched — that silently fixed 303 of 874 sites.
// `(?![\w-])` accepts a quote, backtick, brace or end-of-text as a boundary while
// still rejecting `text-slate-4000` and `mytext-slate-400`.
// Variant prefixes (hover:, placeholder:, group-hover:, marker:) are matched around
// rather than consumed, so they survive untouched with no extra bookkeeping.
const TOKEN_RE =
  /(?<![\w-])(?:text|placeholder)-(?:slate-[34]00|gray-[34]00|\[#(?:94a3b8|9ca3af|cbd5e1|d1d5db)\])(?![\w-])/g;

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'muted text on light surfaces must meet WCAG AA 4.5:1 — use text-slate-500 or darker',
    },
    fixable: 'code',
    schema: [],
    messages: {
      lowContrast:
        "'{{found}}' is ~2.6:1 on a light surface and fails WCAG AA (4.5:1). Use '{{suggested}}'. " +
        'If this really sits on a dark fill, disable this line with a reason.',
    },
  },

  create(context) {
    const sourceCode = context.sourceCode ?? context.getSourceCode();

    /**
     * Replace ONLY the matched token's character range, located by searching the
     * node's own source text.
     *
     * Do NOT rewrite the whole node. `TemplateElement.range` does not mean the same
     * thing in every parser — espree excludes the backtick/`${` delimiters while
     * @typescript-eslint/parser includes them — so a whole-node replace silently ate
     * the delimiters under the TS parser and produced
     *   className={flex-shrink-0 … isExpanded ? 'x' : ''}`}
     * out of a valid template literal, in 13 files. Offsetting from the source text
     * is parser-agnostic and cannot corrupt the delimiters, because it never touches
     * anything outside the token itself.
     */
    function checkNode(node) {
      const text = sourceCode.getText(node);
      TOKEN_RE.lastIndex = 0;
      let match;
      while ((match = TOKEN_RE.exec(text)) !== null) {
        const token = match[0];
        const replacement = REPLACEMENTS.get(token);
        if (!replacement) continue;
        const tokenStart = node.range[0] + match.index;
        const tokenEnd = tokenStart + token.length;
        context.report({
          node,
          messageId: 'lowContrast',
          data: { found: token, suggested: replacement },
          fix: (fixer) => fixer.replaceTextRange([tokenStart, tokenEnd], replacement),
        });
      }
    }

    return {
      Literal(node) {
        if (typeof node.value !== 'string') return;
        checkNode(node);
      },
      TemplateElement(node) {
        checkNode(node);
      },
    };
  },
};
