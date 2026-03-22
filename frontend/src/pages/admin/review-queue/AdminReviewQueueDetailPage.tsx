import React, { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { AdminReviewQueueLayout } from './AdminReviewQueueLayout';
import { ReviewQueuePriorityBadge } from '../../../components/admin/review-queue/ReviewQueuePriorityBadge';
import { ReviewQueueStatusBadge } from '../../../components/admin/review-queue/ReviewQueueStatusBadge';
import { adminReviewQueueAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import { InternalThreadPanel } from '../../../components/admin/collaboration/InternalThreadPanel';

type QueueItem = {
  id: string;
  queue_item_type: string;
  status: string;
  priority_score: number;
  priority_band: string;
  title: string;
  summary?: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  source_name?: string;
  source_url?: string;
  trust_tier?: string;
  assigned_to_user_id?: string;
  due_at?: string;
  notes?: string;
  resolution_summary?: string;
  created_at?: string;
  updated_at?: string;
  priority_reasons?: string[];
  related_staged_resource_candidate_id?: string;
  related_staged_event_candidate_id?: string;
  related_change_event_id?: string;
  related_live_resource_id?: string;
  related_live_event_id?: string;
};

type ActivityItem = {
  id: string;
  action_type: string;
  actor_user_id: string;
  previous_status?: string;
  new_status?: string;
  previous_assignee_id?: string;
  new_assignee_id?: string;
  note?: string;
  created_at: string;
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

export const AdminReviewQueueDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem] = useState<QueueItem | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [assignees, setAssignees] = useState<Array<{ id: string; email?: string; full_name?: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusModal, setStatusModal] = useState<string | null>(null);
  const [resolveNote, setResolveNote] = useState('');
  const [deferDate, setDeferDate] = useState('');
  const [notesEdit, setNotesEdit] = useState('');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [it, act, assigneesRes] = await Promise.all([
        adminReviewQueueAPI.getItem(id),
        adminReviewQueueAPI.getActivity(id),
        adminReviewQueueAPI.getAssignees(),
      ]);
      setItem(it);
      setActivity(act.items ?? []);
      setAssignees(assigneesRes.items ?? []);
      setNotesEdit(it?.notes ?? '');
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (fn: () => Promise<unknown>) => {
    setActionLoading(true);
    try {
      await fn();
      await load();
      setStatusModal(null);
      setResolveNote('');
      setDeferDate('');
    } catch (e) {
      setError((e as Error)?.message || 'Action failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClaim = () => runAction(() => adminReviewQueueAPI.claim(id!));
  const handleUnassign = () => runAction(() => adminReviewQueueAPI.unassign(id!));
  const handleSetStatus = (status: string, note?: string) =>
    runAction(() => adminReviewQueueAPI.setStatus(id!, status, note));
  const handleResolve = () => runAction(() => adminReviewQueueAPI.resolve(id!, resolveNote));
  const handleDefer = () => runAction(() => adminReviewQueueAPI.defer(id!, deferDate || undefined));
  const handleReopen = () => runAction(() => adminReviewQueueAPI.reopen(id!));
  const handleAssign = (assigneeId: string) => runAction(() => adminReviewQueueAPI.assign(id!, assigneeId));
  const handleSaveNotes = () => runAction(() => adminReviewQueueAPI.updateNotes(id!, notesEdit));

  if (!id) {
    navigate(buildRoute('adminReviewQueue'));
    return null;
  }

  if (loading) {
    return (
      <AdminReviewQueueLayout title="Queue Item" subtitle="Loading...">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminReviewQueueLayout>
    );
  }

  if (error || !item) {
    return (
      <AdminReviewQueueLayout title="Queue Item" subtitle="Error">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {error || 'Item not found'}
          <Link to={buildRoute('adminReviewQueue')} className="ml-2 underline">Back to queue</Link>
        </div>
      </AdminReviewQueueLayout>
    );
  }

  const canAssign = ['new', 'triaged', 'assigned', 'deferred'].includes(item.status);
  const canClaim = ['new', 'triaged', 'assigned'].includes(item.status) && !item.assigned_to_user_id;
  const canChangeStatus = ['assigned', 'in_progress', 'blocked', 'waiting'].includes(item.status);
  const canResolve = ['in_progress', 'waiting'].includes(item.status);
  const canReopen = ['resolved', 'rejected', 'deferred'].includes(item.status);

  return (
    <AdminReviewQueueLayout title="Queue Item" subtitle={item.title?.slice(0, 80) || 'Detail'}>
      <div className="space-y-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Summary */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Summary</h3>
            <div className="space-y-2 text-sm">
              <div className="flex gap-2">
                <span className="text-slate-500">Type:</span>
                <span>{QUEUE_TYPES[item.queue_item_type] ?? item.queue_item_type}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500">Status:</span>
                <ReviewQueueStatusBadge status={item.status} />
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500">Priority:</span>
                <ReviewQueuePriorityBadge band={item.priority_band} score={item.priority_score} />
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500">Country/City:</span>
                <span>{[item.country_code, item.city_name].filter(Boolean).join(' / ') || '-'}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500">Assignee:</span>
                <span>{item.assigned_to_user_id ? 'Assigned' : 'Unassigned'}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500">Source:</span>
                <span>{item.source_name || '-'}</span>
              </div>
            </div>
          </div>

          {/* Priority reasons */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Why this item matters</h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
              {(item.priority_reasons ?? []).length > 0 ? (
                item.priority_reasons!.map((r, i) => <li key={i}>{r}</li>)
              ) : (
                <li>No explicit reasons recorded</li>
              )}
            </ul>
          </div>
        </div>

        {/* Related links */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Related objects</h3>
          <div className="flex flex-wrap gap-2">
            {item.related_staged_resource_candidate_id && (
              <Link
                to={buildRoute('adminStagingResourceDetail', { id: item.related_staged_resource_candidate_id })}
                className="rounded bg-blue-100 px-2 py-1 text-sm text-blue-800 hover:bg-blue-200"
              >
                Staged resource →
              </Link>
            )}
            {item.related_staged_event_candidate_id && (
              <Link
                to={buildRoute('adminStagingEventDetail', { id: item.related_staged_event_candidate_id })}
                className="rounded bg-blue-100 px-2 py-1 text-sm text-blue-800 hover:bg-blue-200"
              >
                Staged event →
              </Link>
            )}
            {item.related_live_resource_id && (
              <Link
                to={buildRoute('adminResourcesEdit', { id: item.related_live_resource_id })}
                className="rounded bg-green-100 px-2 py-1 text-sm text-green-800 hover:bg-green-200"
              >
                Live resource →
              </Link>
            )}
            {item.related_live_event_id && (
              <Link
                to={buildRoute('adminEventsEdit', { id: item.related_live_event_id })}
                className="rounded bg-green-100 px-2 py-1 text-sm text-green-800 hover:bg-green-200"
              >
                Live event →
              </Link>
            )}
            {item.source_url && (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded bg-slate-100 px-2 py-1 text-sm text-slate-700 hover:bg-slate-200"
              >
                Source URL →
              </a>
            )}
            {!item.related_staged_resource_candidate_id &&
              !item.related_staged_event_candidate_id &&
              !item.related_live_resource_id &&
              !item.related_live_event_id &&
              !item.source_url && (
                <span className="text-sm text-slate-500">No related links</span>
              )}
          </div>
        </div>

        {/* Notes */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Notes</h3>
          <textarea
            className="w-full rounded border border-slate-300 p-2 text-sm"
            rows={3}
            value={notesEdit}
            onChange={(e) => setNotesEdit(e.target.value)}
          />
          <button
            type="button"
            onClick={handleSaveNotes}
            disabled={actionLoading}
            className="mt-2 rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300 disabled:opacity-50"
          >
            Save notes
          </button>
        </div>

        {/* Actions */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Actions</h3>
          <div className="flex flex-wrap gap-2">
            {canClaim && (
              <button
                type="button"
                onClick={handleClaim}
                disabled={actionLoading}
                className="rounded bg-[#0b2b43] px-3 py-1 text-sm text-white hover:bg-[#0d3552] disabled:opacity-50"
              >
                Claim
              </button>
            )}
            {canAssign && assignees.length > 0 && (
              <select
                className="rounded border border-slate-300 px-2 py-1 text-sm"
                onChange={(e) => {
                  const v = e.target.value;
                  if (v) handleAssign(v);
                }}
              >
                <option value="">Assign to...</option>
                {assignees.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.full_name || a.email || a.id}
                  </option>
                ))}
              </select>
            )}
            {item.assigned_to_user_id && canAssign && (
              <button
                type="button"
                onClick={handleUnassign}
                disabled={actionLoading}
                className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300 disabled:opacity-50"
              >
                Unassign
              </button>
            )}
            {canChangeStatus && (
              <>
                <button
                  type="button"
                  onClick={() => setStatusModal('in_progress')}
                  disabled={actionLoading}
                  className="rounded bg-amber-100 px-2 py-1 text-sm text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                >
                  Set in progress
                </button>
                <button
                  type="button"
                  onClick={() => setStatusModal('blocked')}
                  disabled={actionLoading}
                  className="rounded bg-red-100 px-2 py-1 text-sm text-red-800 hover:bg-red-200 disabled:opacity-50"
                >
                  Block
                </button>
                <button
                  type="button"
                  onClick={() => setStatusModal('waiting')}
                  disabled={actionLoading}
                  className="rounded bg-amber-50 px-2 py-1 text-sm text-amber-900 hover:bg-amber-100 disabled:opacity-50"
                >
                  Waiting
                </button>
              </>
            )}
            {canResolve && (
              <button
                type="button"
                onClick={() => setStatusModal('resolve')}
                disabled={actionLoading}
                className="rounded bg-green-100 px-2 py-1 text-sm text-green-800 hover:bg-green-200 disabled:opacity-50"
              >
                Resolve
              </button>
            )}
            {canChangeStatus && (
              <button
                type="button"
                onClick={() => setStatusModal('defer')}
                disabled={actionLoading}
                className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300 disabled:opacity-50"
              >
                Defer
              </button>
            )}
            {canReopen && (
              <button
                type="button"
                onClick={handleReopen}
                disabled={actionLoading}
                className="rounded bg-blue-100 px-2 py-1 text-sm text-blue-800 hover:bg-blue-200 disabled:opacity-50"
              >
                Reopen
              </button>
            )}
          </div>

          {/* Status modal content inline */}
          {statusModal === 'in_progress' && (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <button
                type="button"
                onClick={() => handleSetStatus('in_progress')}
                disabled={actionLoading}
                className="rounded bg-amber-600 px-2 py-1 text-sm text-white"
              >
                Confirm in progress
              </button>
              <button
                type="button"
                onClick={() => setStatusModal(null)}
                className="ml-2 rounded bg-slate-200 px-2 py-1 text-sm"
              >
                Cancel
              </button>
            </div>
          )}
          {statusModal === 'blocked' && (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <button
                type="button"
                onClick={() => handleSetStatus('blocked')}
                disabled={actionLoading}
                className="rounded bg-red-600 px-2 py-1 text-sm text-white"
              >
                Confirm blocked
              </button>
              <button
                type="button"
                onClick={() => setStatusModal(null)}
                className="ml-2 rounded bg-slate-200 px-2 py-1 text-sm"
              >
                Cancel
              </button>
            </div>
          )}
          {statusModal === 'waiting' && (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <button
                type="button"
                onClick={() => handleSetStatus('waiting')}
                disabled={actionLoading}
                className="rounded bg-amber-600 px-2 py-1 text-sm text-white"
              >
                Confirm waiting
              </button>
              <button
                type="button"
                onClick={() => setStatusModal(null)}
                className="ml-2 rounded bg-slate-200 px-2 py-1 text-sm"
              >
                Cancel
              </button>
            </div>
          )}
          {statusModal === 'resolve' && (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <textarea
                placeholder="Resolution summary (optional)"
                className="mb-2 w-full rounded border border-slate-300 p-2 text-sm"
                rows={2}
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
              />
              <button
                type="button"
                onClick={handleResolve}
                disabled={actionLoading}
                className="rounded bg-green-600 px-2 py-1 text-sm text-white"
              >
                Confirm resolve
              </button>
              <button
                type="button"
                onClick={() => setStatusModal(null)}
                className="ml-2 rounded bg-slate-200 px-2 py-1 text-sm"
              >
                Cancel
              </button>
            </div>
          )}
          {statusModal === 'defer' && (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <input
                type="date"
                className="mb-2 rounded border border-slate-300 px-2 py-1 text-sm"
                value={deferDate}
                onChange={(e) => setDeferDate(e.target.value)}
              />
              <button
                type="button"
                onClick={handleDefer}
                disabled={actionLoading}
                className="ml-2 rounded bg-slate-600 px-2 py-1 text-sm text-white"
              >
                Confirm defer
              </button>
              <button
                type="button"
                onClick={() => setStatusModal(null)}
                className="ml-2 rounded bg-slate-200 px-2 py-1 text-sm"
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Internal discussion */}
        <InternalThreadPanel
          targetType="review_queue_item"
          targetId={id}
          title="Queue item discussion"
        />

        {/* Activity log */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Activity</h3>
          <div className="space-y-2 text-sm">
            {activity.length === 0 ? (
              <p className="text-slate-500">No activity yet</p>
            ) : (
              activity.map((a) => (
                <div key={a.id} className="rounded bg-slate-50 px-2 py-1">
                  <span className="font-medium">{a.action_type}</span>
                  {a.previous_status && a.new_status && (
                    <span className="text-slate-600"> {a.previous_status} → {a.new_status}</span>
                  )}
                  {a.note && <span className="text-slate-500"> · {a.note.slice(0, 100)}</span>}
                  <span className="text-slate-400"> • {new Date(a.created_at).toLocaleString()}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <Link to={buildRoute('adminReviewQueue')} className="text-sm text-[#0b2b43] underline">
          ← Back to queue
        </Link>
      </div>
    </AdminReviewQueueLayout>
  );
};
