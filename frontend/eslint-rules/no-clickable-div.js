/**
 * eslint-rules/no-clickable-div.js
 *
 * Custom ESLint rule: prohibit `<div onClick={...}>` (and other non-interactive
 * HTML elements) without the three WCAG-required keyboard-accessibility attributes:
 *   - role="button"   (or another interactive role)
 *   - tabIndex={0}    (or tabIndex={-1} for programmatically-focused elements)
 *   - onKeyDown       (keyboard handler for Enter / Space)
 *
 * Rationale: clickable divs are keyboard-inaccessible by default because
 * they don't receive focus and don't fire 'click' on Enter/Space.
 *
 * Usage in eslint.config.js:
 *   import noClickableDiv from './eslint-rules/no-clickable-div.js';
 *   plugins: { local: { rules: { 'no-clickable-div': noClickableDiv } } }
 *   rules:   { 'local/no-clickable-div': 'error' }
 *
 * AUDIT-A6 (AIQ-359) — A11y baseline
 */

/** Non-interactive HTML elements that become interactive when given onClick */
const INTERACTIVE_ELEMENTS = new Set([
  'div', 'span', 'p', 'section', 'article', 'header', 'footer', 'main',
  'li', 'td', 'tr', 'th', 'label', 'form',
]);

/** These roles are natively interactive — role="button" is one, but link, tab, etc. also qualify */
const INTERACTIVE_ROLES = new Set([
  'button', 'link', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
  'option', 'tab', 'treeitem', 'checkbox', 'radio', 'combobox', 'listbox',
  'slider', 'spinbutton', 'switch', 'gridcell',
]);

// AUDIT-A6 followup: frontend/package.json has `"type": "module"`, so ESLint
// loads this file as ESM. `module.exports` is CommonJS — it's not exposed as
// a named or default export under ESM, which causes:
//   SyntaxError: The requested module './eslint-rules/no-clickable-div.js'
//                does not provide an export named 'default'
// Use `export default` so eslint.config.js can `import noClickableDiv from …`.
export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Disallow onClick on non-interactive HTML elements without role, tabIndex, and onKeyDown (WCAG 2.1 SC 2.1.1)',
      recommended: true,
    },
    schema: [],
    messages: {
      missingRole:
        "Clickable <{{element}}> is missing role=\"button\" (or an interactive role). " +
        "Screen readers won't announce it as interactive.",
      missingTabIndex:
        "Clickable <{{element}}> is missing tabIndex={0}. " +
        "Keyboard users can't focus it.",
      missingOnKeyDown:
        "Clickable <{{element}}> is missing onKeyDown. " +
        "Enter and Space won't trigger the action for keyboard users.",
    },
  },

  create(context) {
    return {
      JSXOpeningElement(node) {
        // Only lint non-interactive HTML elements (lowercase = HTML, uppercase = React component)
        const elementName =
          node.name.type === 'JSXIdentifier' ? node.name.name : null;
        if (!elementName || !INTERACTIVE_ELEMENTS.has(elementName)) return;

        const attrs = node.attributes;

        // Check if onClick is present
        const hasOnClick = attrs.some(
          (attr) =>
            attr.type === 'JSXAttribute' &&
            attr.name &&
            (attr.name.name === 'onClick' || attr.name.name === 'onPress'),
        );
        if (!hasOnClick) return;

        // Collect the values of relevant attributes
        const roleAttr = attrs.find(
          (attr) => attr.type === 'JSXAttribute' && attr.name?.name === 'role',
        );
        const tabIndexAttr = attrs.find(
          (attr) => attr.type === 'JSXAttribute' && attr.name?.name === 'tabIndex',
        );
        const onKeyDownAttr = attrs.find(
          (attr) => attr.type === 'JSXAttribute' && attr.name?.name === 'onKeyDown',
        );

        // Check role is an interactive role
        const roleValue =
          roleAttr?.value?.type === 'Literal'
            ? roleAttr.value.value
            : roleAttr?.value?.type === 'JSXExpressionContainer' &&
              roleAttr.value.expression?.type === 'Literal'
            ? roleAttr.value.expression.value
            : null;

        const hasInteractiveRole = roleValue && INTERACTIVE_ROLES.has(String(roleValue));

        if (!hasInteractiveRole) {
          context.report({
            node,
            messageId: 'missingRole',
            data: { element: elementName },
          });
        }

        if (!tabIndexAttr) {
          context.report({
            node,
            messageId: 'missingTabIndex',
            data: { element: elementName },
          });
        }

        if (!onKeyDownAttr) {
          context.report({
            node,
            messageId: 'missingOnKeyDown',
            data: { element: elementName },
          });
        }
      },
    };
  },
};
