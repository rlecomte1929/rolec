import { useCallback } from 'react';
import { reportError } from '../lib/errorTracking';

/**
 * Returns a `report(error, componentName?)` function for use in catch blocks.
 *
 * Usage:
 *   const report = useErrorReporter();
 *   try { ... } catch (err) { report(err, 'MyComponent'); }
 */
export function useErrorReporter() {
  return useCallback((error: unknown, componentName?: string) => {
    const err = error instanceof Error ? error : new Error(String(error));
    void reportError({
      message:       err.message,
      stack:         err.stack ?? null,
      componentName: componentName ?? null,
    });
  }, []);
}
