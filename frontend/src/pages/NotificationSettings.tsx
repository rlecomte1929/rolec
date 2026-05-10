/**
 * Option 6C: Notification preferences settings.
 * Shows toggles for in-app and email per notification type.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { NOTIFICATION_TYPES } from '../constants/notificationTypes';
import {
  getNotificationPreferences,
  upsertNotificationPreference,
  type NotificationPreference,
} from '../api/notifications';

const TYPE_LABELS: Record<string, string> = {
  [NOTIFICATION_TYPES.HR_FEEDBACK_POSTED]: 'New feedback from HR',
  [NOTIFICATION_TYPES.EMPLOYEE_SAVED]: 'Employee updated the case',
  [NOTIFICATION_TYPES.CASE_STATUS_CHANGED]: 'Case status changed',
};

const SUPPORTED_TYPES = [
  NOTIFICATION_TYPES.CASE_STATUS_CHANGED,
  NOTIFICATION_TYPES.EMPLOYEE_SAVED,
  NOTIFICATION_TYPES.HR_FEEDBACK_POSTED,
];

export const NotificationSettings: React.FC = () => {
  const [prefs, setPrefs] = useState<Record<string, NotificationPreference>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const list = await getNotificationPreferences();
      const map: Record<string, NotificationPreference> = {};
      list.forEach((p) => {
        map[p.type] = p;
      });
      SUPPORTED_TYPES.forEach((t) => {
        if (!map[t]) {
          map[t] = { type: t, in_app: true, email: false, muted_until: null };
        }
      });
      setPrefs(map);
    } catch (e: any) {
      setError(e?.message || 'Failed to load preferences.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updatePref = async (
    type: string,
    field: 'in_app' | 'email',
    value: boolean
  ) => {
    const current = prefs[type] || { type, in_app: true, email: false, muted_until: null };
    setSaving(type);
    setError('');
    try {
      await upsertNotificationPreference({
        type,
        in_app: field === 'in_app' ? value : current.in_app,
        email: field === 'email' ? value : current.email,
        muted_until: current.muted_until,
      });
      setPrefs((prev) => ({
        ...prev,
        [type]: {
          ...current,
          [field]: value,
        },
      }));
    } catch (e: any) {
      setError(e?.message || 'Failed to save.');
    } finally {
      setSaving(null);
    }
  };

  return (
    <AppShell title="Notification settings" subtitle="Email and in-app preferences.">
      <div className="max-w-2xl">
        {loading && (
          <div className="text-sm text-[#6b7280] py-8">Loading preferences...</div>
        )}
        {error && (
          <div className="mb-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
            {error}
          </div>
        )}
        {!loading && (
          <Card padding="lg">
            <div className="text-sm text-[#6b7280] mb-6">
              Configure which notifications you receive in-app and via email.
            </div>
            <div className="space-y-6">
              {SUPPORTED_TYPES.map((type) => {
                const p = prefs[type] || { in_app: true, email: false };
                const label = TYPE_LABELS[type] || type;
                const isSaving = saving === type;
                return (
                  <div
                    key={type}
                    className="flex flex-wrap items-center justify-between gap-4 py-3 border-b border-[#e2e8f0] last:border-b-0"
                  >
                    <div className="font-medium text-[#0b2b43]">{label}</div>
                    <div className="flex items-center gap-6">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={p.in_app}
                          disabled={isSaving}
                          onChange={(e) => updatePref(type, 'in_app', e.target.checked)}
                          className="rounded border-[#e2e8f0] text-[#0b2b43]"
                        />
                        In-app
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={p.email}
                          disabled={isSaving}
                          onChange={(e) => updatePref(type, 'email', e.target.checked)}
                          className="rounded border-[#e2e8f0] text-[#0b2b43]"
                        />
                        Email
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
};
