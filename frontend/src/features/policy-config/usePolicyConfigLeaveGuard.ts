import { useEffect } from 'react';
import { useBlocker } from 'react-router-dom';

/**
 * Confirms before in-app navigation when the policy matrix has unsaved edits.
 * Tab close / refresh is handled separately via beforeunload in the workspace hook.
 */
export function usePolicyConfigLeaveGuard(shouldBlock: boolean) {
  const blocker = useBlocker(shouldBlock);

  useEffect(() => {
    if (blocker.state === 'blocked') {
      const ok = window.confirm(
        'You have unsaved changes to the compensation policy. Leave this page without saving?'
      );
      if (ok) {
        setTimeout(() => blocker.proceed(), 0);
      } else {
        blocker.reset();
      }
    }
  }, [blocker]);
}
