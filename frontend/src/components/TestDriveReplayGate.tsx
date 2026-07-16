/**
 * TestDriveReplayGate — TD-M2 (AIQ-1560).
 *
 * Starts PostHog session replay the moment a test-drive session exists, checked on
 * every route change (a tester provisions on /test-drive, then navigates to log in —
 * the session appears mid-visit, after boot). Renders nothing. A complete no-op for
 * real users: ensureTestDriveReplay only records when getTestDriveSession() is set,
 * so no HR/employee/admin page is ever recorded.
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ensureTestDriveReplay } from '../analytics';

export function TestDriveReplayGate() {
  const location = useLocation();
  useEffect(() => {
    ensureTestDriveReplay();
  }, [location.pathname]);
  return null;
}

export default TestDriveReplayGate;
