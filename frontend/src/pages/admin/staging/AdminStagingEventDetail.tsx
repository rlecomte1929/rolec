import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { adminStagingAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import { InternalThreadPanel } from '../../../components/admin/collaboration/InternalThreadPanel';

type Candidate = Record<string, unknown>;
type Match = {
  id: string;
  title?: string;
  city_name?: string;
  start_datetime?: string;
  status?: string;
  similarity_score?: number;
  match_reasons?: string[];
};

export const AdminStagingEventDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [mergeTargetId, setMergeTargetId] = useState('');
  const [reviewReason, setReviewReason] = useState('');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [c, m] = await Promise.all([
        adminStagingAPI.getEventCandidate(id),
        adminStagingAPI.getEventCandidateMatches(id),
      ]);
      setCandidate(c);
      setMatches(m.matches || []);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load candidate');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const status = (candidate?.status as string) ?? 'new';
  const isApproved = status === 'approved_new' || status === 'approved_merged';
  const canRestore =
    ['rejected', 'duplicate', 'ignored'].includes(status) && !isApproved;

  const handleApproveNew = async () => {
    if (!id || actionLoading) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.approveEventAsNew(id, reviewReason || undefined);
      load();
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleMerge = async () => {
    if (!id || !mergeTargetId || actionLoading) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.mergeEvent(id, {
        target_event_id: mergeTargetId,
        fields_to_merge: ['description', 'venue_name', 'address', 'external_url'],
        reason: reviewReason || undefined,
      });
      load();
      setMergeTargetId('');
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!id || actionLoading) return;
    if (!confirm('Reject this candidate?')) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.rejectEvent(id, reviewReason || undefined);
      load();
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleMarkDuplicate = async () => {
    if (!id || !mergeTargetId || actionLoading) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.markEventDuplicate(id, {
        duplicate_of_live_event_id: mergeTargetId,
        reason: reviewReason || undefined,
      });
      load();
      setMergeTargetId('');
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleIgnore = async () => {
    if (!id || actionLoading) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.ignoreEvent(id, reviewReason || undefined);
      load();
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestore = async () => {
    if (!id || actionLoading) return;
    setActionLoading(true);
    try {
      await adminStagingAPI.restoreEventToReview(id);
      load();
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <AdminLayout title="Staged Event" subtitle="Loading...">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminLayout>
    );
  }

  if (error || !candidate) {
    return (
      <AdminLayout title="Staged Event" subtitle="Error">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {error || 'Candidate not found'}
        </div>
        <Link
          to={buildRoute('adminStagingEvents')}
          className="mt-4 inline-block text-[#0b2b43] hover:underline"
        >
          ← Back to list
        </Link>
      </AdminLayout>
    );
  }

  const prov = (candidate.provenance_json as Record<string, unknown>) || {};

  return (
    <AdminLayout
      title="Staged Event"
      subtitle={(candidate.title as string) || 'Detail'}
    >
      <div className="mb-4">
        <Link
          to={buildRoute('adminStagingEvents')}
          className="text-sm text-[#0b2b43] hover:underline"
        >
          ← Back to event candidates
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Candidate content</h3>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-slate-500">Title</dt>
                <dd className="font-medium">{String(candidate.title ?? '-')}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Description</dt>
                <dd className="whitespace-pre-wrap">
                  {(candidate.description as string) || '-'}
                </dd>
              </div>
              <div className="flex gap-4 flex-wrap">
                <div>
                  <dt className="text-slate-500">Event type</dt>
                  <dd>{String(candidate.event_type ?? '-')}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Venue</dt>
                  <dd>{String(candidate.venue_name ?? '-')}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Address</dt>
                  <dd>{String(candidate.address ?? '-')}</dd>
                </div>
              </div>
              <div className="flex gap-4 flex-wrap">
                <div>
                  <dt className="text-slate-500">Start</dt>
                  <dd>
                    {candidate.start_datetime
                      ? new Date(candidate.start_datetime as string).toLocaleString()
                      : '-'}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">End</dt>
                  <dd>
                    {candidate.end_datetime
                      ? new Date(candidate.end_datetime as string).toLocaleString()
                      : '-'}
                  </dd>
                </div>
              </div>
              <div className="flex gap-4">
                <div>
                  <dt className="text-slate-500">Price</dt>
                  <dd>
                    {candidate.is_free ? 'Free' : String(candidate.price_text ?? '-')}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Family friendly</dt>
                  <dd>{candidate.is_family_friendly ? 'Yes' : 'No'}</dd>
                </div>
              </div>
              <div>
                <dt className="text-slate-500">Source URL</dt>
                <dd>
                  <a
                    href={(candidate.source_url as string) || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#0b2b43] hover:underline"
                  >
                    {String(candidate.source_url ?? '-')}
                  </a>
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="mb-3 font-medium text-slate-800">Provenance</h3>
            <dl className="space-y-1 text-sm text-slate-600">
              <div>
                <dt className="inline font-medium">Source:</dt>{' '}
                <dd className="inline">{String(candidate.source_name ?? '-')}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Trust tier:</dt>{' '}
                <dd className="inline">{String(candidate.trust_tier ?? '-')}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Confidence:</dt>{' '}
                <dd className="inline">
                  {candidate.confidence_score != null
                    ? (Number(candidate.confidence_score) * 100).toFixed(0) + '%'
                    : '-'}
                </dd>
              </div>
              <div>
                <dt className="inline font-medium">Extraction method:</dt>{' '}
                <dd className="inline">{String(candidate.extraction_method ?? '-')}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Fetched:</dt>{' '}
                <dd className="inline">
                  {candidate.created_at
                    ? new Date(candidate.created_at as string).toLocaleString()
                    : '-'}
                </dd>
              </div>
              {Boolean((prov as Record<string, unknown>)?.snippet) && (
                <div>
                  <dt className="block font-medium">Snippet</dt>
                  <dd className="mt-1 rounded bg-white p-2 text-xs">
                    {String((prov as Record<string, unknown>)?.snippet ?? '').slice(0, 300)}...
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Status</h3>
            <p>
              <span
                className={`rounded px-2 py-0.5 text-sm ${
                  isApproved
                    ? 'bg-green-100 text-green-800'
                    : ['rejected', 'error'].includes(status)
                      ? 'bg-red-100 text-red-800'
                      : 'bg-amber-100 text-amber-800'
                }`}
              >
                {String(status)}
              </span>
            </p>
            {Boolean((candidate as Record<string, unknown>).review_reason) && (
              <p className="mt-2 text-sm text-slate-600">
                <strong>Review note:</strong> {String((candidate as Record<string, unknown>).review_reason ?? '')}
              </p>
            )}
          </div>

          {!isApproved && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 font-medium text-slate-800">Review actions</h3>
              <textarea
                placeholder="Review reason (optional)"
                value={reviewReason}
                onChange={(e) => setReviewReason(e.target.value)}
                className="mb-3 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                rows={2}
              />
              <div className="space-y-2">
                <button
                  onClick={handleApproveNew}
                  disabled={actionLoading}
                  className="block w-full rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
                >
                  Approve as new live draft
                </button>
                {matches.length > 0 && (
                  <>
                    <div className="border-t border-slate-100 pt-2">
                      <label className="block text-xs text-slate-500">
                        Merge into live event
                      </label>
                      <select
                        value={mergeTargetId}
                        onChange={(e) => setMergeTargetId(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      >
                        <option value="">Select match...</option>
                        {matches.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.title} ({m.city_name})  - {' '}
                            {m.start_datetime
                              ? new Date(m.start_datetime).toLocaleDateString()
                              : '-'}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={handleMerge}
                        disabled={!mergeTargetId || actionLoading}
                        className="mt-2 block w-full rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        Merge into selected
                      </button>
                    </div>
                    <button
                      onClick={handleMarkDuplicate}
                      disabled={!mergeTargetId || actionLoading}
                      className="block w-full rounded bg-slate-600 px-3 py-1.5 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
                    >
                      Mark as duplicate of selected
                    </button>
                  </>
                )}
                <button
                  onClick={handleReject}
                  disabled={actionLoading}
                  className="block w-full rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                >
                  Reject
                </button>
                <button
                  onClick={handleIgnore}
                  disabled={actionLoading}
                  className="block w-full rounded border border-slate-400 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  Ignore
                </button>
              </div>
              {canRestore && (
                <button
                  onClick={handleRestore}
                  disabled={actionLoading}
                  className="mt-3 block w-full rounded border border-amber-500 px-3 py-1.5 text-sm text-amber-700 hover:bg-amber-50"
                >
                  Restore to needs review
                </button>
              )}
            </div>
          )}

          <InternalThreadPanel
            targetType="staged_event_candidate"
            targetId={id ?? ''}
            title="Internal discussion"
          />

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Suggested live matches</h3>
            {matches.length === 0 ? (
              <p className="text-sm text-slate-500">No matches found</p>
            ) : (
              <ul className="space-y-2">
                {matches.map((m) => (
                  <li key={m.id} className="text-sm">
                    <Link
                      to={`/admin/events/${m.id ?? ''}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#0b2b43] hover:underline"
                    >
                      {String(m.title ?? '')}
                    </Link>
                    <span className="ml-1 text-slate-500">
                      {m.city_name}  - {' '}
                      {((m.similarity_score ?? 0) * 100).toFixed(0)}% match
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};
