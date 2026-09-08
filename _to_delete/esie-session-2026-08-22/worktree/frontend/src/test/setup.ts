// TEST-2 — global Vitest setup. Loaded via vite.config.ts `test.setupFiles`.
// Registers jest-dom matchers (toBeInTheDocument, toHaveTextContent, …) once for
// the whole suite. With `globals: true`, Vitest auto-cleans the DOM between tests,
// so individual files no longer need to import jest-dom or call cleanup().
import '@testing-library/jest-dom/vitest';
