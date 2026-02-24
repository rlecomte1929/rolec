/**
 * Standalone Assignment Debug page - dev only
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { AssignmentDebugPanel } from './AssignmentDebugPanel';

const DEV_TOOLS = import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true';

export const AssignmentDebugPage: React.FC = () => {
  if (!DEV_TOOLS) {
    return null;
  }
  return (
    <AppShell title="Assignment Debug" subtitle="Verify case_assignments visibility under RLS.">
      <Link
        to="/debug/auth"
        className="text-sm text-[#6b7280] hover:text-[#0b2b43] mb-4 inline-block"
      >
        ← Debug Auth
      </Link>
      <AssignmentDebugPanel />
    </AppShell>
  );
};
