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
  country_code?: string;
  city_name?: string;
  status?: string;
  summary?: string;
  similarity_score?: number;
  match_reasons?: string[];
};

export const AdminStagingResourceDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [mergeTargetId, setMergeTargetId] = useState('');
  const [reviewReason, setReviewReason] = useState('');
  const [mergeFields] = useState<string[]>(['summary', 'body', 'external_url', 'content_json']);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [c, m] = await Promise.all([
        adminStagingAPI.getResourceCandidate(id),
        adminStagingAPI.getResourceCandidateMatches(id),
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
      await adminStagingAPI.approveResourceAsNew(id, reviewReason || undefined);
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
      await adminStagingAPI.mergeResource(id, {
        target_resource_id: mergeTargetId,
        fields_to_merge: mergeFields,
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
      await adminStagingAPI.rejectResource(id, reviewReason || undefined);
      load();
      setReviewReason('');
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleMarkDuplicate = async (targetId?: string) => {
    if (!id || actionLoading) return;
    const liveId = targetId || mergeTargetId;
    if (!liveId) {
      alert('Select a target (match) or enter live resource ID');
      return;
    }
    setActionLoading(true);
    try {
      await adminStagingAPI.markResourceDuplicate(id, {
        duplicate_of_live_resource_id: liveId,
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
      await adminStagingAPI.ignoreResource(id, reviewReason || undefined);
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
      await adminStagingAPI.restoreResourceToReview(id);
      load();
    } catch (e) {
      alert((e as Error)?.message || 'Failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <AdminLayout title="Staged Resource" subtitle="Loading...">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminLayout>
    );
  }

  if (error || !candidate) {
    return (
      <AdminLayout title="Staged Resource" subtitle="Error">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {error || 'Candidate not found'}
        </div>
        <Link
          to={buildRoute('adminStagingResources')}
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
      title="Staged Resource"
      subtitle={(candidate.title as string) || 'Detail'}
    >
      <div className="mb-4">
        <Link
          to={buildRoute('adminStagingResources')}
          className="text-sm text-[#0b2b43] hover:underline"
        >
          ← Back to resource candidates
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
                <dt className="text-slate-500">Summary</dt>
                <dd className="whitespace-pre-wrap">
                  {(candidate.summary as string) || '-'}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Body</dt>
                <dd className="whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {(candidate.body as string) || '-'}
                </dd>
              </div>
              <div className="flex gap-4">
                <div>
                  <dt className="text-slate-500">Country / City</dt>
                  <dd>
                    {String(candidate.country_code ?? '')} / {String(candidate.city_name ?? '-')}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Category / Type</dt>
                  <dd>
                    {String(candidate.category_key ?? '-')} / {String(candidate.resource_type ?? '-')}
                  </dd>
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
                        Merge into live resource
                      </label>
                      <select
                        value={mergeTargetId}
                        onChange={(e) => setMergeTargetId(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      >
                        <option value="">Select match...</option>
                        {matches.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.title} ({m.city_name ?? m.country_code})
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
                      onClick={() => handleMarkDuplicate(mergeTargetId || undefined)}
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
            targetType="staged_resource_candidate"
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
                      to={`/admin/resources/${m.id ?? ''}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#0b2b43] hover:underline"
                    >
                      {String(m.title ?? '')}
                    </Link>
                    <span className="ml-1 text-slate-500">
                      ({m.city_name ?? m.country_code})  - {' '}
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
