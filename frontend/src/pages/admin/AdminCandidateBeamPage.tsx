import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Button, Card, Textarea } from '../../components/antigravity';
import {
  candidateBeamAPI,
  type BeamItem,
  type BeamItemCounts,
  type BeamRun,
  type ConfidenceBand,
  type ImportPlan,
} from '../../api/candidateBeam';

/**
 * Corridor candidate beam — the review queue.
 *
 * Three rules this screen exists to hold, all of them about not letting model output look
 * more finished than it is:
 *
 * 1. **A source is a CLAIM until a human checks it.** The model's cited source is shown as
 *    an unverified claim, never as a citation and never as a link that implies it was
 *    followed. An invented source survives review by looking already-done, so the label
 *    does the work the styling would otherwise undo.
 *
 * 2. **Unsourced candidates are work, not waste.** They cannot be imported (the staging
 *    row requires a source), but they are the research worklist, so they get their own
 *    count and their own visible state rather than being filtered away.
 *
 * 3. **Where the passes disagreed is the evidence.** The merged text is a representative,
 *    not a consensus. Expanding a candidate shows every contributing variant with its pass
 *    and framing, because judging the merge without seeing the spread is judging the merge.
 *
 * There is no promote control here, and no endpoint behind one. Approved candidates travel
 * through the existing staging gate. Nothing on this page may describe a candidate as
 * verified, approved-by-counsel, or compliant — it is unreviewed drafting.
 */

const BAND_VARIANT: Record<ConfidenceBand, 'success' | 'info' | 'warning' | 'neutral'> = {
  'near-certain': 'success',
  strong: 'info',
  moderate: 'warning',
  low: 'neutral',
};

const STATUS_VARIANT: Record<BeamItem['status'], 'success' | 'error' | 'info' | 'neutral'> = {
  approved: 'success',
  rejected: 'error',
  imported: 'info',
  pending_review: 'neutral',
};

export function AdminCandidateBeamPage(): React.ReactElement {
  const [params, setParams] = useSearchParams();
  const runId = params.get('run') || '';

  const [runs, setRuns] = useState<BeamRun[]>([]);
  const [items, setItems] = useState<BeamItem[]>([]);
  const [counts, setCounts] = useState<BeamItemCounts | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    candidateBeamAPI
      .listRuns()
      .then(setRuns)
      .catch(() => setError('Could not load beam runs.'));
  }, []);

  const loadItems = useCallback((id: string) => {
    if (!id) return;
    candidateBeamAPI
      .listItems(id)
      .then((res) => {
        setItems(res.items);
        setCounts(res.counts);
        setError(null);
      })
      .catch(() => setError('Could not load candidates for this run.'));
  }, []);

  useEffect(() => {
    loadItems(runId);
    setPlan(null);
  }, [runId, loadItems]);

  const selectRun = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('run', id);
    setParams(next, { replace: true });
  };

  const review = async (item: BeamItem, status: 'approved' | 'rejected') => {
    setBusy(true);
    try {
      await candidateBeamAPI.review(item.id, status, notes[item.id]);
      loadItems(runId);
    } catch {
      setError(`Could not record the decision on "${item.title}".`);
    } finally {
      setBusy(false);
    }
  };

  const previewImport = async () => {
    if (!runId) return;
    setBusy(true);
    try {
      setPlan(await candidateBeamAPI.importPlan(runId, 'FRANCE'));
      setError(null);
    } catch {
      setError('Could not build the import preview.');
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectedRun = useMemo(() => runs.find((r) => r.id === runId) || null, [runs, runId]);

  return (
    <AdminLayout title="Corridor candidate beam">
      <Alert variant="info" className="mb-4">
        Unreviewed model drafting. Nothing here has been checked by a person, and sources are
        the model&apos;s own claims until someone verifies them. Approving a candidate queues
        it for staging — it does not publish it.
      </Alert>

      {error && (
        <Alert variant="error" className="mb-4">
          {error}
        </Alert>
      )}

      <Card padding="lg" className="mb-6">
        <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">Runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-slate-500">No beam runs yet.</p>
        ) : (
          <ul className="space-y-2">
            {runs.map((run) => (
              <li key={run.id}>
                <Button
                  unstyled
                  onClick={() => selectRun(run.id)}
                  className={`w-full text-left text-sm px-3 py-2 rounded-lg border ${
                    run.id === runId ? 'border-[#1f8e8b] bg-[#f0fbfa]' : 'border-slate-200'
                  }`}
                >
                  <span className="font-mono">{run.corridor}</span> · {run.employee_type} ·{' '}
                  {run.candidate_count} candidates ·{' '}
                  <span className="text-slate-500">
                    {run.passes_completed}/{run.passes_requested} passes
                  </span>
                  {run.status === 'failed' && (
                    <span className="ml-2">
                      <Badge variant="error">failed</Badge>
                    </span>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {selectedRun && counts && (
        <Card padding="lg" className="mb-6">
          <div className="flex flex-wrap gap-4 text-sm">
            <span>
              <strong>{counts.total}</strong> candidates
            </span>
            <span>{counts.pending_review} to review</span>
            <span>{counts.approved} approved</span>
            <span>{counts.rejected} rejected</span>
            <span>{counts.imported} imported</span>
            <span className="text-[#92400e]">
              {counts.source_missing} with no source — research worklist, not importable
            </span>
          </div>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={previewImport} disabled={busy}>
              Preview import
            </Button>
            <span className="ml-2 text-xs text-slate-500">
              Shows what an import would do. Writes nothing.
            </span>
          </div>
          {plan && (
            <div className="mt-3 text-sm">
              <p>
                <strong>{plan.importable}</strong> importable
                {plan.skipped.length > 0 && ` · ${plan.skipped.length} skipped`}
              </p>
              {plan.skipped.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {plan.skipped.map((skip) => (
                    <li key={skip.candidate_uid}>
                      <span className="font-medium">{skip.title}</span> — {skip.reason}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </Card>
      )}

      {items.map((item) => (
        <Card key={item.id} padding="lg" className="mb-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-[#0b2b43]">
                #{item.rank} {item.title}
              </h3>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={BAND_VARIANT[item.confidence_band]}>{item.confidence_band}</Badge>
                <span className="text-slate-500">
                  seen in {item.pass_frequency}/{item.passes_total} passes
                </span>
                {item.category && <span className="text-slate-500">· {item.category}</span>}
                <Badge variant={STATUS_VARIANT[item.status]}>{item.status}</Badge>
                {item.flagged && <Badge variant="warning">flagged</Badge>}
              </div>
            </div>
          </div>

          {item.action_required && (
            <p className="mt-3 text-sm text-slate-700">{item.action_required}</p>
          )}

          <p className="mt-2 text-xs">
            {item.source_missing || !item.source ? (
              <span className="text-[#92400e]">
                No source cited — research this before it can be staged.
              </span>
            ) : (
              <span className="text-slate-600">
                Claimed source (unverified): <span className="font-mono">{item.source}</span>
              </span>
            )}
          </p>

          <Button unstyled onClick={() => toggle(item.id)} className="mt-3 text-xs text-[#1f8e8b]">
            {expanded.has(item.id) ? 'Hide' : 'Show'} {item.variants?.length ?? 0} contributing
            variants
          </Button>

          {expanded.has(item.id) && (
            <ul className="mt-2 space-y-2 border-l-2 border-slate-200 pl-3">
              {(item.variants || []).map((variant, index) => (
                <li key={`${variant.pass}-${variant.arrival_ordinal ?? index}`} className="text-xs">
                  <span className="font-mono text-slate-500">
                    pass {variant.pass}
                    {variant.arrival_ordinal ? `.${variant.arrival_ordinal}` : ''}
                  </span>{' '}
                  <span className="text-slate-400">{variant.framing}</span>
                  <div className="text-slate-700">{variant.title}</div>
                </li>
              ))}
            </ul>
          )}

          {item.status === 'pending_review' && (
            <div className="mt-4">
              <Textarea
                rows={2}
                placeholder="Review note (optional)"
                value={notes[item.id] || ''}
                onChange={(value) => setNotes({ ...notes, [item.id]: value })}
              />
              <div className="mt-2 flex gap-2">
                <Button size="sm" disabled={busy} onClick={() => review(item, 'approved')}>
                  Approve for staging
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => review(item, 'rejected')}
                >
                  Reject
                </Button>
              </div>
            </div>
          )}

          {item.status === 'imported' && item.import_requirement_type && (
            <p className="mt-3 text-xs text-slate-500">
              Staged as {item.import_requirement_type} in {item.import_country} · ref{' '}
              {item.imported_ref}
            </p>
          )}
        </Card>
      ))}
    </AdminLayout>
  );
}

export default AdminCandidateBeamPage;
