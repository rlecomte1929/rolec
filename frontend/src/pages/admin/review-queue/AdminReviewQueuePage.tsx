import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { AdminReviewQueueLayout } from './AdminReviewQueueLayout';
import { ReviewQueuePriorityBadge } from '../../../components/admin/review-queue/ReviewQueuePriorityBadge';
import { ReviewQueueStatusBadge } from '../../../components/admin/review-queue/ReviewQueueStatusBadge';
import { adminReviewQueueAPI, adminCollaborationAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import { ThreadSummaryBadge } from '../../../components/admin/collaboration/ThreadSummaryBadge';

type QueueItem = {
  id: string;
  queue_item_type: string;
  status: string;
  priority_score: number;
  priority_band: string;
  title: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  source_name?: string;
  trust_tier?: string;
  assigned_to_user_id?: string;
  due_at?: string;
  created_at?: string;
  priority_reasons?: string[];
  related_staged_resource_candidate_id?: string;
  related_staged_event_candidate_id?: string;
  related_change_event_id?: string;
  related_live_resource_id?: string;
  related_live_event_id?: string;
};

const QUEUE_TYPES: Record<string, string> = {
  staged_resource_candidate: 'Staged Resource',
  staged_event_candidate: 'Staged Event',
  source_change_review: 'Source Change',
  stale_live_resource_review: 'Stale Resource',
  stale_live_event_review: 'Stale Event',
  duplicate_resolution: 'Duplicate',
  crawl_failure_review: 'Crawl Failure',
  coverage_gap_review: 'Coverage Gap',
};

export const AdminReviewQueuePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') || undefined;
  const priorityBand = searchParams.get('priority') || undefined;
  const assigneeId = searchParams.get('assignee') || undefined;
  const countryCode = searchParams.get('country') || undefined;
  const itemType = searchParams.get('type') || undefined;
  const overdueOnly = searchParams.get('overdue') === '1';
  const unassignedOnly = searchParams.get('unassigned') === '1';
  const searchText = searchParams.get('search') || '';
  const sort = (searchParams.get('sort') as 'priority' | 'created' | 'due' | 'age') || 'priority';

  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [threadSummaries, setThreadSummaries] = useState<Record<string, { comment_count: number; last_comment_at?: string; status?: string; is_unread?: boolean }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [st, list] = await Promise.all([
        adminReviewQueueAPI.getStats(),
        adminReviewQueueAPI.list({
          status,
          priority_band: priorityBand,
          assignee_id: assigneeId,
          country_code: countryCode,
          queue_item_type: itemType,
          overdue_only: overdueOnly,
          unassigned_only: unassignedOnly,
          search: searchText || undefined,
          limit: 50,
          offset: 0,
          sort,
        }),
      ]);
      setStats(st);
      const listItems = list.items ?? [];
      setItems(listItems);
      setTotal(list.total ?? 0);
      if (listItems.length > 0) {
        adminCollaborationAPI.getSummariesBatch(
          listItems.map((i: { id: string }) => ({ target_type: 'review_queue_item', target_id: i.id }))
        ).then((r) => setThreadSummaries(r.summaries || {})).catch(() => {});
      } else {
        setThreadSummaries({});
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [status, priorityBand, assigneeId, countryCode, itemType, overdueOnly, unassignedOnly, searchText, sort]);

  useEffect(() => {
    load();
  }, [load]);

  const updateFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const handleClaim = async (id: string) => {
    setActionLoading(id);
    try {
      await adminReviewQueueAPI.claim(id);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Claim failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleBackfill = async () => {
    setBackfillLoading(true);
    try {
      await adminReviewQueueAPI.backfill();
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Backfill failed');
    } finally {
      setBackfillLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(items.map((i) => i.id)));
  };

  const formatAge = (createdAt?: string) => {
    if (!createdAt) return '-';
    const d = new Date(createdAt);
    const hours = (Date.now() - d.getTime()) / 3600000;
    if (hours < 1) return '<1h';
    if (hours < 24) return `${Math.floor(hours)}h`;
    return `${Math.floor(hours / 24)}d`;
  };

  const formatDue = (dueAt?: string) => {
    if (!dueAt) return '-';
    const d = new Date(dueAt);
    const now = new Date();
    if (d < now) return 'Overdue';
    const hours = (d.getTime() - now.getTime()) / 3600000;
    if (hours < 24) return `${Math.floor(hours)}h`;
    return d.toLocaleDateString();
  };

  return (
    <AdminReviewQueueLayout
      title="Review Queue"
      subtitle="Staged items, changes, stale content"
    >
      <div className="space-y-4">
        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div className="text-xl font-semibold text-[#0b2b43]">{Number(stats?.open_items_count) ?? 0}</div>
            <div className="text-xs text-slate-600">Open</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div className="text-xl font-semibold text-amber-700">{Number(stats?.unassigned_count) ?? 0}</div>
            <div className="text-xs text-slate-600">Unassigned</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div className="text-xl font-semibold text-blue-700">{Number(stats?.in_progress_count) ?? 0}</div>
            <div className="text-xs text-slate-600">In progress</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div className="text-xl font-semibold text-red-700">{Number(stats?.overdue_count) ?? 0}</div>
            <div className="text-xs text-slate-600">Overdue</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="text-lg font-semibold text-slate-700">
              {Number((stats?.by_priority_band as Record<string, number>)?.['critical']) || 0}
            </div>
            <div className="text-xs text-slate-600">Critical</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="text-lg font-semibold text-slate-700">
              {Number((stats?.by_priority_band as Record<string, number>)?.['high']) || 0}
            </div>
            <div className="text-xs text-slate-600">High</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="text-lg font-semibold text-slate-700">
              {Number((stats?.by_queue_item_type as Record<string, number>)?.['stale_live_resource_review']) || 0}
            </div>
            <div className="text-xs text-slate-600">Stale resources</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="text-lg font-semibold text-slate-700">
              {Number((stats?.by_queue_item_type as Record<string, number>)?.['source_change_review']) || 0}
            </div>
            <div className="text-xs text-slate-600">Source changes</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
            value={status ?? ''}
            onChange={(e) => updateFilter('status', e.target.value || undefined)}
          >
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="triaged">Triaged</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In progress</option>
            <option value="blocked">Blocked</option>
            <option value="waiting">Waiting</option>
          </select>
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
            value={priorityBand ?? ''}
            onChange={(e) => updateFilter('priority', e.target.value || undefined)}
          >
            <option value="">All priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
            value={itemType ?? ''}
            onChange={(e) => updateFilter('type', e.target.value || undefined)}
          >
            <option value="">All types</option>
            {Object.entries(QUEUE_TYPES).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => updateFilter('overdue', e.target.checked ? '1' : undefined)}
            />
            Overdue only
          </label>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={unassignedOnly}
              onChange={(e) => updateFilter('unassigned', e.target.checked ? '1' : undefined)}
            />
            Unassigned only
          </label>
          <input
            type="text"
            placeholder="Search..."
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={searchText}
            onChange={(e) => updateFilter('search', e.target.value || undefined)}
          />
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
            value={sort}
            onChange={(e) => updateFilter('sort', e.target.value)}
          >
            <option value="priority">Priority</option>
            <option value="created">Created</option>
            <option value="due">Due date</option>
            <option value="age">Age</option>
          </select>
          <button
            type="button"
            onClick={handleBackfill}
            disabled={backfillLoading}
            className="ml-auto rounded bg-[#0b2b43] px-3 py-1 text-sm text-white hover:bg-[#0d3552] disabled:opacity-50"
          >
            {backfillLoading ? 'Backfilling…' : 'Backfill from signals'}
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>
        )}

        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">
                    <input
                      type="checkbox"
                      checked={items.length > 0 && selectedIds.size === items.length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Title</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Type</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Priority</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Country/City</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Assignee</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Due</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Age</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                      No queue items match filters. Try backfilling from signals.
                    </td>
                  </tr>
                ) : (
                  items.map((it) => (
                    <tr key={it.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(it.id)}
                          onChange={() => toggleSelect(it.id)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Link
                            to={buildRoute('adminReviewQueueDetail', { id: it.id })}
                            className="font-medium text-[#0b2b43] hover:underline"
                          >
                            {(it.title || 'Untitled').slice(0, 60)}
                            {(it.title || '').length > 60 ? '…' : ''}
                          </Link>
                          <ThreadSummaryBadge
                            targetType="review_queue_item"
                            targetId={it.id}
                            summary={threadSummaries[it.id] || null}
                            linkRoute="adminReviewQueueDetail"
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2 text-sm text-slate-600">
                        {QUEUE_TYPES[it.queue_item_type] ?? it.queue_item_type}
                      </td>
                      <td className="px-3 py-2">
                        <ReviewQueuePriorityBadge band={it.priority_band} score={it.priority_score} />
                      </td>
                      <td className="px-3 py-2">
                        <ReviewQueueStatusBadge status={it.status} />
                      </td>
                      <td className="px-3 py-2 text-sm">
                        {[it.country_code, it.city_name].filter(Boolean).join(' / ') || '-'}
                      </td>
                      <td className="px-3 py-2 text-sm">{it.assigned_to_user_id ? 'Assigned' : '-'}</td>
                      <td className="px-3 py-2 text-sm">{formatDue(it.due_at)}</td>
                      <td className="px-3 py-2 text-sm">{formatAge(it.created_at)}</td>
                      <td className="px-3 py-2">
                        {['new', 'triaged', 'assigned'].includes(it.status) && (
                          <button
                            type="button"
                            onClick={() => handleClaim(it.id)}
                            disabled={actionLoading === it.id}
                            className="rounded bg-slate-200 px-2 py-0.5 text-xs hover:bg-slate-300 disabled:opacity-50"
                          >
                            Claim
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {total > 50 && (
          <div className="text-sm text-slate-600">Showing 50 of {total} items</div>
        )}
      </div>
    </AdminReviewQueueLayout>
  );
};
