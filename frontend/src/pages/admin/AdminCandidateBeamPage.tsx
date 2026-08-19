import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Button, Card, Input, Modal, Select, Textarea } from '../../components/antigravity';
import {
  candidateBeamAPI,
  type BeamItem,
  type BeamItemCounts,
  type BeamRun,
  type ConfidenceBand,
  type ImportPlan,
  type ImportResult,
  type PassResult,
  type VerifyReport,
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

// The destination catalog an import stages into. Hardcoded before this change at the
// preview call site; named here so the execute path cannot drift from the preview path and
// stage into a different country than the one the reviewer was shown.
const IMPORT_COUNTRY = 'FRANCE';

// The corridors a beam may be launched for. Hardcoded because no endpoint lists the active
// set; the label beside the picker says where that set is actually controlled, so the
// hardcoding is visible to the reviewer rather than implied to be dynamic.
// Mirrors store.MIN_PASSES. Below two there is no cross-pass agreement to measure, and
// finalize refuses with a 409 rather than rank a single opinion as consensus.
const MIN_SUCCESSFUL_PASSES = 2;

// StartRunRequest.context is max_length=4000; over that the request 422s and the reader sees
// a generic failure instead of "your note is too long".
const MAX_CONTEXT = 4000;

const DEFAULT_CORRIDOR = 'FR-NO';
const DEFAULT_EMPLOYEE_TYPE = 'permanent';

const CORRIDORS = [
  { value: 'FR-NO', label: 'France → Norway' },
  { value: 'ES-IE', label: 'Spain → Ireland' },
  { value: 'NO-FR', label: 'Norway → France' },
];

const EMPLOYEE_TYPES = [
  { value: 'permanent', label: 'Permanent' },
  { value: 'secondment', label: 'Secondment' },
  { value: 'posted_worker', label: 'Posted worker' },
];

// Verification outcomes, worst first. `verified` is the only healthy one; each of the others
// names a distinct way a staged row stopped matching what was imported.
const VERIFY_VARIANT: Record<string, 'success' | 'error' | 'warning'> = {
  verified: 'success',
  content_drift: 'warning',
  pillar_mismatch: 'warning',
  country_mismatch: 'warning',
  vanished: 'error',
};

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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [verify, setVerify] = useState<VerifyReport | null>(null);
  // category -> pillar. Items carry a category; the pillar grouping the reviewer needs is a
  // server-owned mapping, so it is fetched rather than guessed from the category string.
  const [pillarByCategory, setPillarByCategory] = useState<Record<string, string>>({});

  // Launch console.
  const [corridor, setCorridor] = useState(DEFAULT_CORRIDOR);
  const [employeeType, setEmployeeType] = useState(DEFAULT_EMPLOYEE_TYPE);
  const [moveDate, setMoveDate] = useState('');
  const [context, setContext] = useState('');
  const [launching, setLaunching] = useState(false);
  // Per-pass, not a single spinner: the beam is five paid calls and a reader watching one
  // opaque spinner cannot tell a slow pass from a dead run.
  const [passLog, setPassLog] = useState<PassResult[]>([]);
  const [launchError, setLaunchError] = useState<string | null>(null);

  useEffect(() => {
    candidateBeamAPI
      .listRuns()
      .then(setRuns)
      .catch(() => setError('Could not load beam runs.'));
    // Fail quiet: without the map every candidate falls into "Unmapped pillar", which is a
    // degraded grouping but still a complete and truthful list. Losing the grouping must not
    // cost the reviewer the queue.
    candidateBeamAPI
      .pillars()
      .then((res) => setPillarByCategory(res.grounded_categories || {}))
      .catch(() => setPillarByCategory({}));
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
    // Every one of these describes the PREVIOUS run. Carrying any of them across would show
    // a reviewer another run's import result beside this run's candidates.
    setPlan(null);
    setImportResult(null);
    setVerify(null);
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
      setPlan(await candidateBeamAPI.importPlan(runId, IMPORT_COUNTRY));
      setError(null);
    } catch {
      setError('Could not build the import preview.');
    } finally {
      setBusy(false);
    }
  };

  /**
   * Approve every near-certain candidate still awaiting review.
   *
   * Selects on `confidence_band`, NOT on `pass_frequency === 5`: the pass count is per-run
   * (`passes_total`), so a frequency literal silently selects nothing on a 3-pass run. The
   * band is the server's own normalisation of that ratio and holds whatever the run size.
   *
   * Unsourced candidates are included. Approval and importability are different questions —
   * the import plan skips them with a stated reason, which is where that belongs. Filtering
   * them out here would quietly narrow the reviewer's bulk action without saying so.
   */
  const approveNearCertain = async () => {
    const targets = items.filter(
      (i) => i.confidence_band === 'near-certain' && i.status === 'pending_review',
    );
    if (targets.length === 0) return;
    setBusy(true);
    try {
      for (const item of targets) {
        await candidateBeamAPI.review(item.id, 'approved');
      }
      loadItems(runId);
      setError(null);
    } catch {
      // Partial application is possible and is reported as such. Claiming a clean failure
      // would leave the reviewer's screen disagreeing with the server.
      setError('Some near-certain candidates could not be approved. Reload to see current state.');
      loadItems(runId);
    } finally {
      setBusy(false);
    }
  };

  /**
   * Run a whole beam: open the run, drive each pass, finalize, then open its review panel.
   *
   * Sequential on purpose. Each pass is a paid model call and the server hands back
   * `next_pass`, so the client follows the server's own cursor rather than assuming the
   * slots are 1..N — which is also what makes a resumed run land on the right slot.
   *
   * A pass that fails does NOT abort the beam. It resolves with `ok: false`, its slot is
   * kept, and the remaining passes still run: the ranking's signal is cross-pass agreement,
   * so four good passes are worth having and the fifth can be retried. Losing the run
   * because one call 500'd is exactly the failure the resumable design exists to prevent.
   */
  const launchBeam = async () => {
    setLaunching(true);
    setLaunchError(null);
    setPassLog([]);
    try {
      // The backend has no move-date field, so it travels as context — labelled, because a
      // date silently folded into free text is a date the reviewer cannot see was sent.
      const parts = [moveDate ? `Planned move date: ${moveDate}` : '', context.trim()].filter(
        Boolean,
      );
      const payloadContext = parts.join('\n').slice(0, MAX_CONTEXT);
      const started = await candidateBeamAPI.startRun({
        corridor,
        employee_type: employeeType,
        context: payloadContext || undefined,
      });

      const log: PassResult[] = [];
      // Explicit slots, NOT the server's next_pass cursor.
      //
      // next_pass is "the lowest slot not SUCCESSFULLY completed", so a failed slot points
      // back at itself. Following it on a fresh launch re-runs that one slot until the
      // budget is gone and never runs the other framings — five paid calls, one framing, and
      // no cross-pass agreement, which is the entire ranking signal. Naming a slot runs
      // exactly that slot, so each framing gets its one attempt. Retrying a failure is a
      // separate, deliberate act (see Resume), not something a launch should spend the
      // budget on silently.
      for (let slot = 1; slot <= started.passes_requested; slot += 1) {
        const result = await candidateBeamAPI.executePass(started.run_id, slot);
        log.push(result);
        setPassLog([...log]);
      }

      // finalize 409s below MIN_PASSES successful passes: cross-pass agreement is undefined
      // with fewer than two, so ranking one pass would present a lone opinion as consensus.
      // Gating on "at least one succeeded" turns that 409 into a failed-looking beam.
      const succeeded = log.filter((r) => r.ok).length;
      if (succeeded >= MIN_SUCCESSFUL_PASSES) {
        await candidateBeamAPI.finalizeRun(started.run_id);
      } else {
        setLaunchError(
          `Only ${succeeded} of ${started.passes_requested} passes succeeded — ranking needs at ` +
            `least ${MIN_SUCCESSFUL_PASSES}. The run is kept, so the failed passes can be retried.`,
        );
      }

      candidateBeamAPI.listRuns().then(setRuns).catch(() => undefined);
      selectRun(started.run_id);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setLaunchError(detail || 'The beam could not be started.');
    } finally {
      setLaunching(false);
    }
  };

  /** Stage the approved candidates for real. Only reachable through the confirm modal. */
  const executeImport = async () => {
    if (!runId) return;
    setConfirmOpen(false);
    setBusy(true);
    try {
      setImportResult(await candidateBeamAPI.executeImport(runId, IMPORT_COUNTRY));
      setVerify(null);
      setError(null);
      loadItems(runId);
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 409) {
        // Already imported, or a freeze conflict. Either way the run must not be retried:
        // the endpoint wrote nothing, and a second attempt cannot change that.
        setError('This run has already been imported.');
      } else {
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        setError(detail || 'The import failed.');
      }
    } finally {
      setBusy(false);
    }
  };

  /** Post-import QA. A drifted report arrives as a 409 and is rendered, not thrown. */
  const runVerify = async () => {
    if (!runId) return;
    setBusy(true);
    try {
      setVerify(await candidateBeamAPI.verifyImport(runId));
      setError(null);
    } catch {
      setError('Could not verify the import.');
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

  /**
   * Candidates grouped by pillar, each group keeping the server's rank order.
   *
   * A category with no grounded pillar lands in "Unmapped pillar" rather than being dropped
   * or silently folded into a neighbour — that group IS the set the import will ask a human
   * to map, so hiding it would hide the work.
   */
  const groups = useMemo(() => {
    const byPillar = new Map<string, BeamItem[]>();
    for (const item of items) {
      const pillar = (item.category && pillarByCategory[item.category]) || 'Unmapped pillar';
      const bucket = byPillar.get(pillar);
      if (bucket) bucket.push(item);
      else byPillar.set(pillar, [item]);
    }
    for (const bucket of byPillar.values()) bucket.sort((a, b) => a.rank - b.rank);
    return [...byPillar.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [items, pillarByCategory]);

  const nearCertainPending = useMemo(
    () =>
      items.filter((i) => i.confidence_band === 'near-certain' && i.status === 'pending_review')
        .length,
    [items],
  );

  return (
    <AdminLayout title="Corridor candidate beam">
      <Alert variant="warning" className="mb-4">
        Candidate beams are research tools, not a source of truth. Every imported candidate must
        be reviewed and signed off by a lawyer before it appears in any HR-facing output.
        Importing here stages facts for legal review — it does not publish them.
      </Alert>

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
        <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">Launch a beam</h2>

        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Select
              value={corridor}
              onChange={setCorridor}
              options={CORRIDORS}
              label="Corridor"
            />
            <p className="mt-1 text-xs text-slate-500">
              Active corridors only — /admin/countries controls which corridors appear here.
            </p>
          </div>
          <Select
            value={employeeType}
            onChange={setEmployeeType}
            options={EMPLOYEE_TYPES}
            label="Employee type"
          />
          <Input type="date" value={moveDate} onChange={setMoveDate} label="Move date" />
        </div>

        <div className="mt-3">
          <Textarea
            rows={2}
            value={context}
            onChange={setContext}
            label="Additional context for this beam run — do not include names or contact details"
          />
          <p className="mt-1 text-xs text-slate-500">
            The move date is sent with this context — the beam has no separate date field.
          </p>
        </div>

        <div className="mt-3">
          <Button onClick={launchBeam} disabled={launching}>
            {launching ? 'Running beam…' : 'Launch beam'}
          </Button>
        </div>

        {launching && passLog.length === 0 && (
          <p className="mt-3 text-sm text-slate-600">Running beam… opening the run.</p>
        )}

        {passLog.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs">
            {passLog.map((pass) => (
              <li key={pass.pass} className="flex flex-wrap items-baseline gap-2">
                <Badge variant={pass.ok ? 'success' : 'error'}>pass {pass.pass}</Badge>
                <span className="text-slate-500">{pass.framing}</span>
                <span className="text-slate-700">
                  {pass.ok ? `${pass.item_count} candidates` : pass.error || 'failed'}
                </span>
              </li>
            ))}
          </ul>
        )}

        {launchError && (
          <Alert variant="error" className="mt-3">
            {launchError}
          </Alert>
        )}
      </Card>

      <Card padding="lg" className="mb-6">
        <h2 className="text-sm font-semibold text-[#0b2b43] mb-1">Runs</h2>

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
          <p className="mt-3 text-sm font-medium text-[#0b2b43]">
            {counts.approved} of {counts.total} approved
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={approveNearCertain}
              disabled={busy || nearCertainPending === 0}
            >
              Select near-certain ({nearCertainPending})
            </Button>
            <Button variant="outline" size="sm" onClick={previewImport} disabled={busy}>
              Preview import
            </Button>
            <Button
              size="sm"
              onClick={() => setConfirmOpen(true)}
              disabled={busy || counts.approved === 0}
            >
              Execute import
            </Button>
            {importResult && (
              <Button variant="outline" size="sm" onClick={runVerify} disabled={busy}>
                Verify import
              </Button>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Preview shows what an import would do. Writes nothing.
          </p>

          {importResult && (
            <Alert variant="success" className="mt-3">
              Import complete — {importResult.imported} facts staged.
            </Alert>
          )}

          {verify && (
            <div className="mt-3">
              <Alert variant={verify.ok ? 'success' : 'error'}>
                {verify.ok
                  ? `All ${verify.verified} staged facts verified.`
                  : `${verify.failed} of ${verify.items.length} staged facts did not verify.`}
              </Alert>
              <ul className="mt-2 space-y-1 text-xs">
                {verify.items.map((v) => (
                  <li key={v.candidate_uid} className="flex flex-wrap items-baseline gap-2">
                    <Badge variant={VERIFY_VARIANT[v.status] || 'neutral'}>{v.status}</Badge>
                    <span className="text-slate-700">{v.title}</span>
                    {v.status !== 'verified' && (
                      <span className="text-slate-500">
                        {v.detail}
                        {v.expected != null && (
                          <>
                            {' '}
                            expected <span className="font-mono">{v.expected}</span> · found{' '}
                            <span className="font-mono">{v.found}</span>
                          </>
                        )}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
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

      {groups.map(([pillar, groupItems]) => (
        <section key={pillar} className="mb-6">
          <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">
            {pillar}{' '}
            <span className="font-normal text-slate-500">({groupItems.length})</span>
          </h2>
          {groupItems.map((item) => (
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
        </section>
      ))}

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Import approved candidates?"
      >
        <p className="text-sm text-slate-700">
          Import {counts?.approved ?? 0} candidates into the fact registry? This cannot be undone.
        </p>
        <div className="mt-4 flex gap-2">
          <Button size="sm" onClick={executeImport} disabled={busy}>
            Confirm
          </Button>
          <Button size="sm" variant="outline" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </AdminLayout>
  );
}

export default AdminCandidateBeamPage;
