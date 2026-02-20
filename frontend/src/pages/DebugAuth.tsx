import React, { useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { getAuthItem } from '../utils/demo';

export const DebugAuth: React.FC = () => {
  const [lastError] = useState(() => localStorage.getItem('debug_last_auth_error') || 'none');
  const token = getAuthItem('relopass_token');
  const userId = getAuthItem('relopass_user_id');
  const email = getAuthItem('relopass_email');
  const username = getAuthItem('relopass_username');
  const role = getAuthItem('relopass_role');

  return (
    <AppShell title="Auth Debug" subtitle="Dev-only diagnostics">
      <Card padding="lg">
        <div className="space-y-4 text-sm font-mono">
          <div>
            <span className="text-[#6b7280]">Session: </span>
            <span className={token ? 'text-green-600' : 'text-red-600'}>
              {token ? 'present' : 'none'}
            </span>
          </div>
          <div>
            <span className="text-[#6b7280]">Token (first 12 chars): </span>
            <span>{token ? `${token.slice(0, 12)}...` : '—'}</span>
          </div>
          <div>
            <span className="text-[#6b7280]">User ID: </span>
            <span>{userId || '—'}</span>
          </div>
          <div>
            <span className="text-[#6b7280]">Email: </span>
            <span>{email || '—'}</span>
          </div>
          <div>
            <span className="text-[#6b7280]">Username: </span>
            <span>{username || '—'}</span>
          </div>
          <div>
            <span className="text-[#6b7280]">Role: </span>
            <span>{role || '—'}</span>
          </div>
          <div>
            <span className="text-[#6b7280]">Storage: </span>
            <span>localStorage (relopass_* keys)</span>
          </div>
          <div>
            <span className="text-[#6b7280]">Last auth error: </span>
            <span className="text-amber-600">{lastError}</span>
          </div>
        </div>
      </Card>
    </AppShell>
  );
};
