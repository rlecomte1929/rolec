/**
 * Synthetic test fixture for the no-clickable-div ESLint rule.
 *
 * Running `npx eslint eslint-rules/__tests__/no-clickable-div.test-fixture.jsx`
 * should produce 3 errors on the bare <div onClick> below and 0 errors on the
 * accessible <div onClick role="button" tabIndex={0} onKeyDown={...}> below.
 *
 * AUDIT-A6 validation criterion:
 *   "New ESLint rule fires on a synthetic test case <div onClick={x}>"
 */

// ❌ Should trigger 3 errors: missing role, tabIndex, onKeyDown
export function BadExample() {
  return (
    <div onClick={() => console.log('clicked')}>
      Click me (inaccessible)
    </div>
  );
}

// ✅ Should pass: all three required attributes present
export function GoodExample() {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      console.log('activated');
    }
  };
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => console.log('clicked')}
      onKeyDown={handleKeyDown}
    >
      Click me (accessible)
    </div>
  );
}
