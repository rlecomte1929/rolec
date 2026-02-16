import React, { useState } from 'react';
import { Card } from './antigravity';
import { TEST_ACCOUNTS, type TestAccount } from '../config/testAccounts';
import { authAPI } from '../api/client';
import { clearAuthItems, setAuthItem } from '../utils/demo';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const SwitchUserModal: React.FC<Props> = ({ open, onClose }) => {
  const [switching, setSwitching] = useState<string | null>(null);
  const [error, setError] = useState('');

  if (!open) return null;

  const handleSwitch = async (account: TestAccount) => {
    setSwitching(account.email);
    setError('');
    try {
      const response = await authAPI.login({
        identifier: account.email,
        password: account.password,
      });
      clearAuthItems();
      setAuthItem('relopass_token', response.token);
      setAuthItem('relopass_role', response.user.role);
      if (response.user.name) setAuthItem('relopass_name', response.user.name);
      if (response.user.email) setAuthItem('relopass_email', response.user.email);
      if (response.user.username) setAuthItem('relopass_username', response.user.username);

      const target = response.user.role === 'EMPLOYEE' ? '/employee/journey' : '/hr/dashboard';
      window.location.href = target;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Login failed. Make sure the account exists.');
      setSwitching(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <Card padding="lg" className="w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-semibold text-[#0b2b43]">Switch test account</div>
          <button
            onClick={onClose}
            className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
          >
            Close
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
            {error}
          </div>
        )}

        <div className="space-y-2">
          {TEST_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              disabled={switching !== null}
              onClick={() => handleSwitch(account)}
              className={`w-full text-left border rounded-lg px-4 py-3 text-sm transition-colors ${
                switching === account.email
                  ? 'bg-[#eef4ff] border-[#1d4ed8]'
                  : 'border-[#e2e8f0] hover:bg-[#f8fafc]'
              } disabled:opacity-50`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[#0b2b43]">{account.label}</div>
                  <div className="text-xs text-[#6b7280]">{account.email}</div>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  account.role === 'ADMIN'
                    ? 'bg-[#f0fdf4] text-[#166534]'
                    : account.role === 'HR'
                    ? 'bg-[#eef4ff] text-[#1d4ed8]'
                    : 'bg-[#f8fafc] text-[#4b5563]'
                }`}>
                  {account.role}
                </span>
              </div>
              {switching === account.email && (
                <div className="text-xs text-[#1d4ed8] mt-1">Switching...</div>
              )}
            </button>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-[#e2e8f0]">
          <div className="text-xs text-[#6b7280]">
            Test accounts must be pre-registered in the backend. If login fails, register the account first via the Auth page.
          </div>
        </div>
      </Card>
    </div>
  );
};
