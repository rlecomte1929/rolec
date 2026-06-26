import React, { useEffect, useState } from 'react';
import { Badge, Button } from '../../../components/antigravity';
import { sourceChangeReviewAPI } from '../../../api/client';

// P2-02d (AIQ-692) — admin review queue for material source-page changes.
// An admin approves a pending change (→ affected active cases are notified) or
// rejects it (→ logged, no user notification). This is the human-in-the-loop
// gate that sits between the material-change classifier and any user banner.

type ChangedSection = {
  kind?: string;
  category?: string;
  text?: string;
};

type Review = {
  id: string;
  rule_version_id?: string;
  source_url?: string;
  source_name?: string;
  old_excerpt?: string;
  new_excerpt?: string;
  changed_sections?: ChangedSection[];
  created_at?: string;
};

type Banner = { kind: 'success' | 'error'; text: string };

const categoryVariant = (category?: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' => {
  switch (category) {
    case 'fee':
      return 'error';
    case 'date':
      return 'warning';
    case 'requirement':
      return 'info';
    case 'form':
      return 'success';
    default:
      return 'neutral';
  }
};

export const AdminSourceChangeReviewsPage: React.FC = () => {
  const [items, setItems] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [banner, setBanner] = useState<Banner | null>(null);

  const load = () => {
    setLoading(true);
    sourceChangeReviewAPI
      .listPending({ limit: 100 })
      .then((r) => setItems((r.items ?? []) as Review[]))
      .catch((e) => setError((e as Error)?.message || 'Failed to load review queue'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleApprove = async (review: Review) => {
    setBusyId(review.id);
    setBanner(null);
    try {
      const res = await sourceChangeReviewAPI.approve(review.id);
      const count = (((res as { notified_case_ids?: unknown[] })?.notified_case_ids) ?? []).length;
      setItems((prev) => prev.filter((r) => r.id !== review.id));
      setBanner({
        kind: 'success',
        text: `Approved — notified ${count} active case${count === 1 ? '' : 's'}.`,
      });
    } catch (e) {
      setBanner({ kind: 'error', text: (e as Error)?.message || 'Approve failed' });
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (review: Review) => {
    setBusyId(review.id);
    setBanner(null);
    try {
      await sourceChangeReviewAPI.reject(review.id);
      setItems((prev) => prev.filter((r) => r.id !== review.id));
      setBanner({ kind: 'success', text: 'Rejected — no users notified.' });
    } catch (e) {
      setBanner({ kind: 'error', text: (e as Error)?.message || 'Reject failed' });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-1 text-2xl font-semibold text-slate-900">Source change review</div>
      <p className="mb-6 text-sm text-slate-500">
        Material changes detected on monitored source pages. Approve to notify affected active
        cases, or reject to dismiss without notifying anyone.
      </p>

      {banner && (
        <div
          role="status"
          className={`mb-4 rounded-lg p-3 text-sm ${
            banner.kind === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}
        >
          {banner.text}
        </div>
      )}

      {loading && <div className="py-12 text-center text-slate-500">Loading...</div>}
      {error && !loading && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="py-12 text-center text-slate-500">No pending material changes</div>
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="space-y-4">
          {items.map((review) => (
            <li key={review.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-900">{review.source_name || 'Unknown source'}</div>
                  {review.source_url && (
                    <a
                      href={review.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-[#0b2b43] hover:underline"
                    >
                      {review.source_url}
                    </a>
                  )}
                  <div className="mt-1 text-xs text-slate-400">
                    rule_version {review.rule_version_id || '-'}
                    {review.created_at ? ` · detected ${new Date(review.created_at).toLocaleString()}` : ''}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={busyId === review.id}
                    onClick={() => handleApprove(review)}
                  >
                    {busyId === review.id ? 'Working...' : 'Approve & notify'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busyId === review.id}
                    onClick={() => handleReject(review)}
                  >
                    Reject
                  </Button>
                </div>
              </div>

              {review.changed_sections && review.changed_sections.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {review.changed_sections.map((s, i) => (
                    <Badge key={i} variant={categoryVariant(s.category)} size="sm">
                      {s.category || 'other'}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Before
                  </div>
                  <pre className="whitespace-pre-wrap rounded-lg bg-red-50 p-3 text-sm text-slate-700">
                    {review.old_excerpt || '—'}
                  </pre>
                </div>
                <div>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    After
                  </div>
                  <pre className="whitespace-pre-wrap rounded-lg bg-green-50 p-3 text-sm text-slate-700">
                    {review.new_excerpt || '—'}
                  </pre>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default AdminSourceChangeReviewsPage;
