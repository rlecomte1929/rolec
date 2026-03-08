import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { adminStagingAPI, adminCollaborationAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import { ThreadSummaryBadge } from '../../../components/admin/collaboration/ThreadSummaryBadge';

type EventCandidate = {
  id: string;
  title: string;
  country_code?: string;
  city_name?: string;
  event_type?: string;
  status?: string;
  start_datetime?: string;
  confidence_score?: number;
  source_name?: string;
  extraction_method?: string;
  created_at?: string;
};

export const AdminStagingEvents: React.FC = () => {
  const [items, setItems] = useState<EventCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [threadSummaries, setThreadSummaries] = useState<Record<string, { comment_count: number; last_comment_at?: string; status?: string; is_unread?: boolean }>>({});
  const [filters, setFilters] = useState({
    status: '',
    country_code: '',
    city_name: '',
    event_type: '',
    trust_tier: '',
    search: '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminStagingAPI.listEventCandidates({
        status: filters.status || undefined,
        country_code: filters.country_code || undefined,
        city_name: filters.city_name || undefined,
        event_type: filters.event_type || undefined,
        trust_tier: filters.trust_tier || undefined,
        search: filters.search || undefined,
        limit: 50,
      });
      const listItems = res.items || [];
      setItems(listItems);
      setTotal(res.total ?? 0);
      if (listItems.length > 0) {
        adminCollaborationAPI.getSummariesBatch(
          listItems.map((i) => ({ target_type: 'staged_event_candidate', target_id: i.id }))
        ).then((r) => setThreadSummaries(r.summaries || {})).catch(() => {});
      } else {
        setThreadSummaries({});
      }
    } catch {
      setItems([]);
      setTotal(0);
      setThreadSummaries({});
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const statusColor = (s: string) => {
    switch (s) {
      case 'new':
      case 'needs_review':
        return 'bg-amber-100 text-amber-800';
      case 'approved_new':
      case 'approved_merged':
        return 'bg-green-100 text-green-800';
      case 'rejected':
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'duplicate':
      case 'ignored':
        return 'bg-slate-100 text-slate-700';
      default:
        return 'bg-slate-100 text-slate-600';
    }
  };

  return (
    <AdminLayout
      title="Staged Event Candidates"
      subtitle="Review and approve extracted event candidates"
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Search title..."
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">All statuses</option>
            <option value="new">new</option>
            <option value="needs_review">needs_review</option>
            <option value="approved_new">approved_new</option>
            <option value="approved_merged">approved_merged</option>
            <option value="rejected">rejected</option>
            <option value="duplicate">duplicate</option>
            <option value="ignored">ignored</option>
            <option value="error">error</option>
          </select>
          <input
            type="text"
            placeholder="Country"
            value={filters.country_code}
            onChange={(e) => setFilters((f) => ({ ...f, country_code: e.target.value }))}
            className="w-24 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            placeholder="City"
            value={filters.city_name}
            onChange={(e) => setFilters((f) => ({ ...f, city_name: e.target.value }))}
            className="w-32 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <Link
            to={buildRoute('adminStagingDashboard')}
            className="text-sm text-[#0b2b43] hover:underline"
          >
            ← Dashboard
          </Link>
        </div>

        {loading ? (
          <div className="py-8 text-center text-slate-500">Loading...</div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-8 text-center text-slate-600">
            No staged event candidates found.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">Country</th>
                  <th className="px-4 py-2">City</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Start</th>
                  <th className="px-4 py-2">Confidence</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Source</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => (
                  <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{e.title}</span>
                        <ThreadSummaryBadge
                          targetType="staged_event_candidate"
                          targetId={e.id}
                          summary={threadSummaries[e.id] || null}
                          linkRoute="adminStagingEventDetail"
                        />
                      </div>
                    </td>
                    <td className="px-4 py-2">{e.country_code ?? '-'}</td>
                    <td className="px-4 py-2">{e.city_name ?? '-'}</td>
                    <td className="px-4 py-2">{e.event_type ?? '-'}</td>
                    <td className="px-4 py-2">
                      {e.start_datetime
                        ? new Date(e.start_datetime).toLocaleString()
                        : '-'}
                    </td>
                    <td className="px-4 py-2">
                      {e.confidence_score != null
                        ? (e.confidence_score * 100).toFixed(0) + '%'
                        : '-'}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs ${statusColor(
                          e.status ?? 'new'
                        )}`}
                      >
                        {e.status ?? 'new'}
                      </span>
                    </td>
                    <td className="px-4 py-2">{e.source_name ?? '-'}</td>
                    <td className="px-4 py-2">
                      <Link
                        to={buildRoute('adminStagingEventDetail', { id: e.id })}
                        className="text-[#0b2b43] hover:underline"
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="text-sm text-slate-500">
          Showing {items.length} of {total} candidates
        </div>
      </div>
    </AdminLayout>
  );
};
