import React, { useEffect, useState } from 'react';
import { adminFreshnessAPI } from '../../api/client';
import { AdminFreshnessLayout } from './freshness/AdminFreshnessLayout';

type SourcePage = {
  id?: string;
  url?: string;
  tier?: string;
  content_hash?: string | null;
  page_title?: string | null;
  http_status?: number | null;
  is_accessible?: boolean;
  last_fetched_at?: string | null;
  last_changed_at?: string | null;
};

const fmt = (ts?: string | null) => (ts ? new Date(ts).toLocaleString() : '—');
const shortHash = (h?: string | null) => (h ? `${h.slice(0, 12)}…` : '—');

export const AdminSourceMonitor: React.FC = () => {
  const [items, setItems] = useState<SourcePage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminFreshnessAPI
      .getSourcePages()
      .then((r) => setItems(r.items ?? []))
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, []);

  const subtitle = 'Every monitored source URL — last fetched, last changed, current hash, tier';

  if (loading) {
    return (
      <AdminFreshnessLayout title="Source monitor" subtitle={subtitle}>
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Source monitor" subtitle={subtitle}>
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Source monitor" subtitle={subtitle}>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">URL</th>
              <th className="px-4 py-2">Tier</th>
              <th className="px-4 py-2">Last fetched</th>
              <th className="px-4 py-2">Last changed</th>
              <th className="px-4 py-2">Current hash</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={String(s.id ?? s.url)} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#0b2b43] hover:underline"
                  >
                    {s.url ?? '—'}
                  </a>
                </td>
                <td className="px-4 py-2">{s.tier ?? '—'}</td>
                <td className="px-4 py-2">{fmt(s.last_fetched_at)}</td>
                <td className="px-4 py-2">{fmt(s.last_changed_at)}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-500">{shortHash(s.content_hash)}</td>
                <td className="px-4 py-2">
                  {s.is_accessible === false ? (
                    <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                      Unreachable{s.http_status ? ` (${s.http_status})` : ''}
                    </span>
                  ) : (
                    <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      OK{s.http_status ? ` (${s.http_status})` : ''}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No monitored source pages yet</div>
      )}
    </AdminFreshnessLayout>
  );
};
