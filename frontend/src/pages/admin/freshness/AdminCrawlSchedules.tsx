import React, { useCallback, useEffect, useState } from 'react';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';

type Schedule = {
  id: string;
  name?: string;
  is_active?: boolean;
  schedule_type?: string;
  schedule_expression?: string;
  source_scope_type?: string;
  source_scope_ref?: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  priority?: number;
  last_run_at?: string;
  next_run_at?: string;
};

export const AdminCrawlSchedules: React.FC = () => {
  const [items, setItems] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioning, setActioning] = useState<string | null>(null);
  const [activeOnly, setActiveOnly] = useState<boolean | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await adminFreshnessAPI.listSchedules({
        is_active: activeOnly ?? undefined,
        limit: 100,
      });
      setItems(r.items ?? []);
    } catch (e) {
      setError((e as Error)?.message || 'Failed');
    } finally {
      setLoading(false);
    }
  }, [activeOnly]);

  useEffect(() => {
    load();
  }, [load]);

  const handleTrigger = async (id: string) => {
    setActioning(id);
    try {
      await adminFreshnessAPI.triggerSchedule(id);
      await load();
    } catch (e) {
      alert((e as Error)?.message || 'Trigger failed');
    } finally {
      setActioning(null);
    }
  };

  const handlePause = async (id: string) => {
    if (!confirm('Pause this schedule?')) return;
    setActioning(id);
    try {
      await adminFreshnessAPI.pauseSchedule(id);
      await load();
    } catch (e) {
      alert((e as Error)?.message || 'Pause failed');
    } finally {
      setActioning(null);
    }
  };

  const handleResume = async (id: string) => {
    setActioning(id);
    try {
      await adminFreshnessAPI.resumeSchedule(id);
      await load();
    } catch (e) {
      alert((e as Error)?.message || 'Resume failed');
    } finally {
      setActioning(null);
    }
  };

  const handleProcessDue = async () => {
    setActioning('process-due');
    try {
      await adminFreshnessAPI.processDueSchedules();
      await load();
    } catch (e) {
      alert((e as Error)?.message || 'Process due failed');
    } finally {
      setActioning(null);
    }
  };

  if (loading) {
    return (
      <AdminFreshnessLayout title="Crawl schedules" subtitle="Schedule management">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Crawl schedules" subtitle="Schedule management">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Crawl schedules" subtitle="Schedule management">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          onClick={handleProcessDue}
          disabled={!!actioning}
          className="rounded bg-[#0b2b43] px-3 py-1.5 text-sm text-white hover:bg-[#0d3a5c] disabled:opacity-50"
        >
          {actioning === 'process-due' ? 'Processing...' : 'Process due schedules'}
        </button>
        <select
          value={activeOnly === null ? '' : activeOnly ? 'active' : 'inactive'}
          onChange={(e) => {
            const v = e.target.value;
            setActiveOnly(v === '' ? null : v === 'active');
          }}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">All</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Scope</th>
              <th className="px-4 py-2">Cadence</th>
              <th className="px-4 py-2">Active</th>
              <th className="px-4 py-2">Last run</th>
              <th className="px-4 py-2">Next run</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">{s.name ?? '-'}</td>
                <td className="px-4 py-2">
                  {s.source_scope_type}: {s.source_scope_ref ?? s.country_code ?? s.city_name ?? s.content_domain ?? '-'}
                </td>
                <td className="px-4 py-2">
                  {s.schedule_type ?? '-'} {s.schedule_expression ?? ''}
                </td>
                <td className="px-4 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs ${s.is_active ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600'}`}>
                    {s.is_active ? 'Yes' : 'No'}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-2">
                  {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-2 flex gap-1">
                  <button
                    onClick={() => handleTrigger(s.id)}
                    disabled={!!actioning}
                    className="rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-800 hover:bg-blue-200 disabled:opacity-50"
                  >
                    Trigger
                  </button>
                  {s.is_active ? (
                    <button
                      onClick={() => handlePause(s.id)}
                      disabled={!!actioning}
                      className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                    >
                      Pause
                    </button>
                  ) : (
                    <button
                      onClick={() => handleResume(s.id)}
                      disabled={!!actioning}
                      className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-800 hover:bg-green-200 disabled:opacity-50"
                    >
                      Resume
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No schedules</div>
      )}
    </AdminFreshnessLayout>
  );
};
