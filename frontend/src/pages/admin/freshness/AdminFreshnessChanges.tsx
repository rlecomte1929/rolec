import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';

type ChangeItem = {
  id?: string;
  source_name?: string;
  source_url?: string;
  country_code?: string;
  city_name?: string;
  change_type?: string;
  change_score?: number;
  detected_at?: string;
  job_run_id?: string;
};

export const AdminFreshnessChanges: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const changeType = searchParams.get('change_type') || undefined;
  const sourceName = searchParams.get('source') || undefined;
  const [sourceFilter, setSourceFilter] = useState('');
  const [items, setItems] = useState<ChangeItem[]>([]);

  useEffect(() => {
    setSourceFilter(sourceName ?? '');
  }, [sourceName]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminFreshnessAPI
      .listDocumentChanges({
        change_type: changeType,
        source_name: sourceName,
        limit: 50,
      })
      .then((r) => {
        setItems(r.items ?? []);
        setTotal(r.total ?? 0);
      })
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [changeType, sourceName]);

  const changeTypeColor = (t: string) => {
    switch (t) {
      case 'significant_change':
        return 'bg-amber-100 text-amber-800';
      case 'new':
        return 'bg-green-100 text-green-800';
      case 'updated':
      case 'minor_change':
        return 'bg-slate-100 text-slate-700';
      case 'removed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-slate-100 text-slate-600';
    }
  };

  if (loading) {
    return (
      <AdminFreshnessLayout title="Document changes" subtitle="Recent source content changes">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Document changes" subtitle="Recent source content changes">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Document changes" subtitle="Recent source content changes">
      <div className="mb-4 flex gap-2">
        <select
          value={changeType ?? ''}
          onChange={(e) => {
            const v = e.target.value;
            const next = new URLSearchParams(searchParams);
            if (v) next.set('change_type', v);
            else next.delete('change_type');
            setSearchParams(next);
          }}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">All change types</option>
          <option value="new">new</option>
          <option value="updated">updated</option>
          <option value="minor_change">minor_change</option>
          <option value="significant_change">significant_change</option>
          <option value="removed">removed</option>
          <option value="unchanged">unchanged</option>
        </select>
        <input
          type="text"
          placeholder="Filter by source"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const next = new URLSearchParams(searchParams);
              if (sourceFilter.trim()) next.set('source', sourceFilter.trim());
              else next.delete('source');
              setSearchParams(next);
            }
          }}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          onClick={() => {
            const next = new URLSearchParams(searchParams);
            if (sourceFilter.trim()) next.set('source', sourceFilter.trim());
            else next.delete('source');
            setSearchParams(next);
          }}
          className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300"
        >
          Filter
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Country / City</th>
              <th className="px-4 py-2">Change type</th>
              <th className="px-4 py-2">Score</th>
              <th className="px-4 py-2">Detected</th>
              <th className="px-4 py-2">URL</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={String(c.id)} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">{c.source_name ?? '-'}</td>
                <td className="px-4 py-2">{c.country_code ?? '-'} / {c.city_name ?? '-'}</td>
                <td className="px-4 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs ${changeTypeColor(c.change_type ?? '')}`}>
                    {c.change_type ?? '-'}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {c.change_score != null ? (c.change_score * 100).toFixed(0) + '%' : '-'}
                </td>
                <td className="px-4 py-2">
                  {c.detected_at ? new Date(c.detected_at).toLocaleString() : '-'}
                </td>
                <td className="max-w-[200px] truncate px-4 py-2">
                  {c.source_url ? (
                    <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="text-[#0b2b43] hover:underline">
                      {c.source_url}
                    </a>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-sm text-slate-500">Showing {items.length} of {total}</div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No document changes found</div>
      )}
    </AdminFreshnessLayout>
  );
};
