import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Button, Card, Checkbox, Pagination, Textarea } from '../../components/antigravity';
import {
  decideFacts,
  editFact,
  getReviewSummary,
  listReviewFacts,
  type EvidenceStatus,
  type ReviewFact,
  type ReviewSummary,
} from '../../api/contentReview';

/**
 * [AIQ-1821] The content review queue.
 *
 * The design rule this page exists to serve: a reviewer must never be asked to judge a fact
 * without its evidence on screen. So every row shows the stored quote highlighted INSIDE the
 * surrounding source text — that is what makes the difference between "you can get a D number
 * if you provide X" and "you MUST provide X" visible without opening anything.
 *
 * Filters live in the URL so a queue view is bookmarkable and shareable, matching
 * AdminReviewQueuePage. Bulk is the default gesture: most of a queue is decidable in groups
 * once the machine-checkable rows are separated from the ones needing judgement.
 */

const PAGE_SIZE = 25;

const EVIDENCE_META: Record<EvidenceStatus, { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'neutral'; help: string }> = {
  verified: {
    label: 'Quote in source',
    variant: 'success',
    help: 'Found word-for-word in the archived page.',
  },
  translated: {
    label: 'Translated',
    variant: 'info',
    help: 'The source is in another language, so a word-for-word check cannot apply. This says nothing about whether the fact is right.',
  },
  unverified: {
    label: 'Not found in source',
    variant: 'warning',
    help: 'Same language, source in hand, quote not in it. Read this one.',
  },
  no_source: {
    label: 'No archived source',
    variant: 'neutral',
    help: 'Nothing to check against — the page was unreachable when we last fetched it.',
  },
};

/** Renders the surrounding source text with the quote marked. */
const EvidenceContext: React.FC<{ context: string; quote: string | null }> = ({ context, quote }) => {
  if (!context) return null;
  const q = (quote ?? '').trim();
  const i = q ? context.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i === -1) {
    return <p className="mt-2 rounded-md bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-600">{context}</p>;
  }
  return (
    <p className="mt-2 rounded-md bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-600">
      {context.slice(0, i)}
      <mark className="rounded bg-amber-100 px-0.5 text-slate-900">{context.slice(i, i + q.length)}</mark>
      {context.slice(i + q.length)}
    </p>
  );
};

export const AdminContentReviewPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') || 'pending';
  const destination = searchParams.get('destination') || '';
  const evidence = (searchParams.get('evidence') || '') as '' | 'verified' | 'unverified' | 'unchecked';
  const q = searchParams.get('q') || '';
  const page = Math.max(1, Number(searchParams.get('page') || '1'));

  const [facts, setFacts] = useState<ReviewFact[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const updateFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setSearchParams(next);
  };

  const load = useCallback(async () => {
    setState('loading');
    try {
      const res = await listReviewFacts({
        status,
        destination: destination || undefined,
        evidence: evidence || undefined,
        q: q || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setFacts(res.items);
      setTotal(res.total);
      setSelected(new Set());
      setState('ready');
    } catch {
      // Never render an empty queue on failure — an empty list reads as "all reviewed".
      setState('failed');
    }
  }, [status, destination, evidence, q, page, reloadKey]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    getReviewSummary().then(setSummary).catch(() => setSummary(null));
  }, [reloadKey]);

  const allSelected = facts.length > 0 && selected.size === facts.length;
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(facts.map((f) => f.id)));

  const decide = async (action: 'approve' | 'reject') => {
    if (!selected.size) return;
    if (action === 'reject' && !rejectNotes.trim()) {
      setError('A reason is required when rejecting.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await decideFacts([...selected], action, rejectNotes.trim() || undefined);
      setRejectNotes('');
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save that decision.');
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async () => {
    if (!editing || editing.text.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      await editFact(editing.id, editing.text.trim());
      setEditing(null);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save that edit.');
    } finally {
      setBusy(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const destinations = useMemo(
    () => Object.keys(summary?.by_destination ?? {}).sort(),
    [summary],
  );

  return (
    <AdminLayout
      title="Content review"
      subtitle="Requirement facts extracted from official sources, with the evidence behind each one"
    >
      {summary && (
        <div className="mb-4 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-4">
          <div className="bg-white px-4 py-3">
            <div className="text-2xl font-semibold tabular-nums text-[#0b2b43]">{summary.pending}</div>
            <div className="text-xs text-slate-500">Pending</div>
          </div>
          <div className="bg-white px-4 py-3">
            <div className="text-2xl font-semibold tabular-nums text-emerald-700">
              {summary.pending_evidence.verified ?? 0}
            </div>
            <div className="text-xs text-slate-500">Quote proven in source</div>
          </div>
          <div className="bg-white px-4 py-3">
            <div className="text-2xl font-semibold tabular-nums text-amber-700">
              {summary.pending_evidence.unverified ?? 0}
            </div>
            <div className="text-xs text-slate-500">Needs reading</div>
          </div>
          <div className="bg-white px-4 py-3">
            <div className="text-2xl font-semibold tabular-nums text-slate-500">
              {summary.pending_evidence.unchecked ?? 0}
            </div>
            <div className="text-xs text-slate-500">Not yet checked</div>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3">
        <select
          aria-label="Status"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          value={status}
          onChange={(e) => updateFilter('status', e.target.value)}
        >
          {['pending', 'approved', 'rejected'].map((s) => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
        <select
          aria-label="Destination"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          value={destination}
          onChange={(e) => updateFilter('destination', e.target.value || undefined)}
        >
          <option value="">All destinations</option>
          {destinations.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <select
          aria-label="Evidence"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          value={evidence}
          onChange={(e) => updateFilter('evidence', e.target.value || undefined)}
        >
          <option value="">Any evidence state</option>
          <option value="verified">Quote proven in source</option>
          <option value="unverified">Not found in source</option>
          <option value="unchecked">Not yet checked</option>
        </select>
        <input
          aria-label="Search fact text"
          placeholder="Search fact text…"
          className="min-w-[200px] flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          defaultValue={q}
          onKeyDown={(e) => {
            if (e.key === 'Enter') updateFilter('q', (e.target as HTMLInputElement).value || undefined);
          }}
        />
        <span className="ml-auto text-sm tabular-nums text-slate-500">{total} facts</span>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {state === 'failed' && (
        <div data-testid="content-review-error" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          <div className="mb-1 font-semibold">We couldn’t load the review queue</div>
          <div className="mb-2">
            This is a problem on our side — it does <strong>not</strong> mean the queue is empty.
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>
        </div>
      )}

      {state === 'loading' && <p className="text-sm text-slate-500" aria-busy="true">Loading the queue…</p>}

      {state === 'ready' && facts.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
          Nothing matches these filters.
        </div>
      )}

      {state === 'ready' && facts.length > 0 && (
        <>
          <Card padding="none">
            <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-2.5">
              <Checkbox checked={allSelected} onChange={toggleAll} aria-label="Select all on this page" />
              <span className="text-sm text-slate-600">
                {selected.size ? `${selected.size} selected` : 'Select all on this page'}
              </span>
            </div>
            <ul className="divide-y divide-slate-200">
              {facts.map((f) => {
                const meta = EVIDENCE_META[f.evidence_status];
                return (
                  <li key={f.id} data-testid="review-row" className="px-4 py-3">
                    <div className="flex gap-3">
                      <Checkbox
                        checked={selected.has(f.id)}
                        onChange={() => toggle(f.id)}
                        aria-label={`Select ${f.fact_text.slice(0, 40)}`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <Badge variant={meta.variant} size="sm">{meta.label}</Badge>
                          <span className="font-mono text-xs text-slate-500">
                            {f.destination_country} · {f.fact_type} · {f.topic_key}
                          </span>
                        </div>

                        {editing?.id === f.id ? (
                          <div className="mt-1">
                            <Textarea
                              value={editing.text}
                              onChange={(v: string) => setEditing({ id: f.id, text: v })}
                              rows={3}
                              aria-label="Corrected fact text"
                            />
                            <div className="mt-2 flex gap-2">
                              <Button size="sm" onClick={saveEdit} disabled={busy}>Save correction</Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <p data-testid="fact-text" className="text-sm text-slate-800">{f.fact_text}</p>
                        )}

                        <p className="mt-1 text-xs text-slate-500">{meta.help}</p>
                        <EvidenceContext context={f.evidence_context} quote={f.evidence_quote} />

                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                          <a href={f.source_url} target="_blank" rel="noreferrer" className="text-[#1f8e8b] hover:underline">
                            Open source ↗
                          </a>
                          {f.status === 'pending' && editing?.id !== f.id && (
                            <button
                              type="button"
                              className="text-[#1f8e8b] hover:underline"
                              onClick={() => setEditing({ id: f.id, text: f.fact_text })}
                            >
                              Correct the wording
                            </button>
                          )}
                          {f.reviewed_by && <span className="text-slate-500">Reviewed by {f.reviewed_by}</span>}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>

          <div className="mt-4 flex justify-center">
            <Pagination page={page} totalPages={totalPages} onChange={(p) => updateFilter('page', String(p))} />
          </div>
        </>
      )}

      {selected.size > 0 && (
        <div className="sticky bottom-4 mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-3 shadow-lg">
          <span className="text-sm font-medium text-[#0b2b43]">{selected.size} selected</span>
          <input
            aria-label="Reason (required to reject)"
            placeholder="Reason (required to reject)"
            className="min-w-[220px] flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
          />
          <Button size="sm" onClick={() => decide('approve')} disabled={busy}>Approve</Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => decide('reject')}
            disabled={busy || !rejectNotes.trim()}
          >
            Reject
          </Button>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminContentReviewPage;
