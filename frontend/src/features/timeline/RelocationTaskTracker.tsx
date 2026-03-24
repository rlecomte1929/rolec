import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, Button, Badge, LoadingButton } from '../../components/antigravity';
import {
  timelineAPI,
  type TimelineMilestone,
  type TimelineTaskSummary,
} from '../../api/client';
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../../utils/apiDetail';
import type { RelocationPlanViewResponseDTO } from '../../types/relocationPlanView';
import { getTaskUrgency, sortTasksForTracker, parseYmd } from './taskTrackerSort';
import { planPhasesToMilestones, planSummaryToTimelineSummary } from './planViewToMilestones';

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Not started' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
  { value: 'skipped', label: 'Skipped' },
] as const;

const OWNER_OPTIONS = [
  { value: 'hr', label: 'HR' },
  { value: 'employee', label: 'Employee' },
  { value: 'provider', label: 'Provider' },
  { value: 'joint', label: 'Joint' },
] as const;

const CRITICALITY_OPTIONS = [
  { value: 'critical', label: 'Critical path' },
  { value: 'normal', label: 'Standard' },
] as const;

function urgencyStripeClass(u: ReturnType<typeof getTaskUrgency>): string {
  switch (u) {
    case 'red':
      return 'bg-red-500';
    case 'orange':
      return 'bg-orange-400';
    case 'green':
      return 'bg-emerald-500';
    default:
      return 'bg-slate-200';
  }
}

function panelAccentClass(u: ReturnType<typeof getTaskUrgency>): string {
  switch (u) {
    case 'red':
      return 'border-l-4 border-red-500';
    case 'orange':
      return 'border-l-4 border-orange-400';
    case 'green':
      return 'border-l-4 border-emerald-500';
    default:
      return 'border-l-4 border-slate-200';
  }
}

function ownerBadgeVariant(o: string): 'neutral' | 'info' | 'warning' | 'success' {
  switch (o) {
    case 'hr':
      return 'info';
    case 'employee':
      return 'warning';
    case 'provider':
      return 'success';
    default:
      return 'neutral';
  }
}

const emptySummary: TimelineTaskSummary = {
  total: 0,
  completed: 0,
  overdue: 0,
  due_this_week: 0,
  blocked: 0,
  in_progress: 0,
};

export type RelocationPlanDataSource = 'phased' | 'timeline';

function resolvePlanDataSource(explicit?: RelocationPlanDataSource): RelocationPlanDataSource {
  if (explicit) return explicit;
  return import.meta.env.VITE_USE_LEGACY_RELOCATION_PLAN === 'true' ? 'timeline' : 'phased';
}

export interface RelocationTaskTrackerProps {
  assignmentId: string;
  /** HR / flows that should persist default milestones on first load. */
  ensureDefaults?: boolean;
  /**
   * `phased` (default): GET /api/relocation-plans/{id}/view.
   * `timeline`: legacy flat milestones (assignments or cases timeline).
   * Override with `VITE_USE_LEGACY_RELOCATION_PLAN=true` when unset.
   */
  planDataSource?: RelocationPlanDataSource;
  /** Forwarded as `role=` query param when using phased API; optional — server defaults from auth. */
  planViewRole?: 'employee' | 'hr';
  /** Shown in card header */
  title?: string;
  /** When embedded under a page section title, hide duplicate H3 */
  hideMainTitle?: boolean;
}

export const RelocationTaskTracker: React.FC<RelocationTaskTrackerProps> = ({
  assignmentId,
  ensureDefaults = false,
  planDataSource: planDataSourceProp,
  planViewRole,
  title = 'Relocation plan & actions',
  hideMainTitle = false,
}) => {
  const planDataSource = resolvePlanDataSource(planDataSourceProp);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [milestones, setMilestones] = useState<TimelineMilestone[]>([]);
  const [summary, setSummary] = useState<TimelineTaskSummary>(emptySummary);
  const [phasedSnapshot, setPhasedSnapshot] = useState<RelocationPlanViewResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');

  const load = useCallback(
    async (opts?: { forceEnsure?: boolean }) => {
      if (!assignmentId) return;
      setLoading(true);
      setError(null);
      const useEnsure = Boolean(ensureDefaults || opts?.forceEnsure);
      try {
        if (planDataSource === 'phased') {
          const loadPhasedOnce = async () =>
            fetchRelocationPlanView(assignmentId, { role: planViewRole });

          let view = await loadPhasedOnce();
          if (view.summary.total_tasks === 0 && useEnsure) {
            await timelineAPI.getByAssignment(assignmentId, {
              ensureDefaults: true,
              includeLinks: false,
            });
            view = await loadPhasedOnce();
          }
          setPhasedSnapshot(view);
          setCaseId(view.case_id);
          const ms = planPhasesToMilestones(view.phases || [], view.case_id);
          setMilestones(ms);
          setSummary(planSummaryToTimelineSummary(view.summary));
          setSelectedId((prev) => {
            if (!ms.length) return null;
            if (view.next_action?.task_id && ms.some((m) => m.id === view.next_action!.task_id)) {
              return view.next_action.task_id;
            }
            if (prev && ms.some((m) => m.id === prev)) return prev;
            return sortTasksForTracker(ms)[0]?.id ?? null;
          });
        } else {
          setPhasedSnapshot(null);
          const data = await timelineAPI.getByAssignment(assignmentId, {
            ensureDefaults: useEnsure,
            includeLinks: false,
          });
          setCaseId(data.case_id);
          const ms = data.milestones || [];
          setMilestones(ms);
          setSummary(data.summary ?? emptySummary);
          setSelectedId((prev) => {
            if (!ms.length) return null;
            if (prev && ms.some((m) => m.id === prev)) return prev;
            return sortTasksForTracker(ms)[0]?.id ?? null;
          });
        }
      } catch (err: unknown) {
        const transport = getClientTransportErrorMessage(err);
        const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message || '');
        setError(msg.trim() ? msg : 'Failed to load tasks');
        setMilestones([]);
        setSummary(emptySummary);
        setPhasedSnapshot(null);
      } finally {
        setLoading(false);
      }
    },
    [assignmentId, ensureDefaults, planDataSource, planViewRole]
  );

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(() => sortTasksForTracker(milestones), [milestones]);
  const selected = milestones.find((m) => m.id === selectedId);

  useEffect(() => {
    if (selected) setNoteDraft(selected.notes ?? '');
  }, [selected?.id, selected?.notes]);

  const nextCritical = useMemo(() => {
    return sorted.find((m) => {
      const st = (m.status || '').toLowerCase();
      if (st === 'done' || st === 'skipped') return false;
      const u = getTaskUrgency(m);
      return u === 'red' || u === 'orange' || m.criticality === 'critical';
    });
  }, [sorted]);

  const patchMilestone = useCallback(
    async (milestoneId: string, patch: Parameters<typeof timelineAPI.updateMilestone>[2]) => {
      if (!caseId) return;
      setUpdating(true);
      setError(null);
      try {
        await timelineAPI.updateMilestone(caseId, milestoneId, patch);
        await load();
      } catch (err: unknown) {
        const transport = getClientTransportErrorMessage(err);
        const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message || '');
        setError(msg.trim() ? msg : 'Update failed');
      } finally {
        setUpdating(false);
      }
    },
    [caseId, load]
  );

  const saveNotes = useCallback(() => {
    if (!selected) return;
    const trimmed = noteDraft.trim();
    const prev = (selected.notes ?? '').trim();
    if (trimmed === prev) return;
    void patchMilestone(selected.id, { notes: trimmed || null });
  }, [selected, noteDraft, patchMilestone]);

  if (loading && milestones.length === 0) {
    return (
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">Loading relocation plan…</div>
      </Card>
    );
  }

  if (error && milestones.length === 0) {
    return (
      <Card padding="lg">
        <div className="text-sm text-red-600">{error}</div>
        <LoadingButton
          variant="outline"
          size="sm"
          className="mt-2"
          loading={loading}
          loadingLabel="Retrying…"
          onClick={() => void load({ forceEnsure: true })}
        >
          Retry
        </LoadingButton>
      </Card>
    );
  }

  if (milestones.length === 0) {
    return (
      <Card padding="lg">
        <h3 className="text-base font-semibold text-[#0b2b43] mb-2">{title}</h3>
        <div className="text-sm text-[#6b7280]">No tasks yet.</div>
        {planDataSource === 'phased' && phasedSnapshot?.empty_state_reason && (
          <p className="text-xs text-[#64748b] mt-2">{phasedSnapshot.empty_state_reason}</p>
        )}
        <Button
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void load({ forceEnsure: true })}
        >
          Create default plan
        </Button>
      </Card>
    );
  }

  return (
    <Card id="hr-rel-tracker-root" padding="lg" className="overflow-hidden scroll-mt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-3">
        <div>
          {!hideMainTitle && (
            <h3 className="text-base font-semibold text-[#0b2b43]">{title}</h3>
          )}
          <p className={`text-xs text-[#6b7280] max-w-xl ${hideMainTitle ? '' : 'mt-0.5'}`}>
            Shared operational checklist tied to this case. Same tasks are visible to HR and the employee;
            ownership shows who is expected to drive each step.
          </p>
        </div>
      </div>

      {(phasedSnapshot?.next_action || nextCritical) && (
        <div className="mb-3 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm">
          <span className="font-semibold text-[#9a3412]">Next focus: </span>
          <span className="text-[#0b2b43]">
            {phasedSnapshot?.next_action?.title ?? nextCritical?.title}
          </span>
          <span className="text-[#6b7280] text-xs ml-2">
            (
            {OWNER_OPTIONS.find(
              (o) =>
                o.value ===
                (phasedSnapshot?.next_action?.owner || nextCritical?.owner || 'joint')
            )?.label ?? 'Joint'}
            )
          </span>
          {phasedSnapshot?.next_action?.reason && (
            <div className="text-xs text-[#64748b] mt-1">{phasedSnapshot.next_action.reason}</div>
          )}
        </div>
      )}

      {planDataSource === 'phased' && phasedSnapshot && !phasedSnapshot.next_action && phasedSnapshot.empty_state_reason && (
        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-[#64748b]">
          {phasedSnapshot.empty_state_reason}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4 text-xs">
        <Badge variant="neutral">Total {summary.total}</Badge>
        <Badge variant="success">Done {summary.completed}</Badge>
        <Badge variant="error">Overdue {summary.overdue}</Badge>
        <Badge variant="warning">Due ≤7d {summary.due_this_week}</Badge>
        <Badge variant="warning">Blocked {summary.blocked}</Badge>
        <Badge variant="info">In progress {summary.in_progress}</Badge>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-2" role="alert">
          {error}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-4 min-h-[280px]">
        <div className="lg:w-[42%] lg:max-w-md flex flex-col gap-1 border-b lg:border-b-0 lg:border-r border-[#e2e8f0] lg:pr-3 pb-3 lg:pb-0">
          {sorted.map((m) => {
            const u = getTaskUrgency(m);
            const active = m.id === selectedId;
            return (
              <button
                key={m.id}
                id={m.milestone_type ? `hr-op-task-${m.milestone_type}` : undefined}
                type="button"
                onClick={() => setSelectedId(m.id)}
                className={`flex w-full text-left rounded-lg overflow-hidden border transition-colors ${
                  active ? 'border-[#0b2b43] bg-[#f0f9ff]' : 'border-transparent hover:bg-[#f8fafc]'
                }`}
              >
                <div className={`w-1.5 flex-shrink-0 ${urgencyStripeClass(u)}`} aria-hidden />
                <div className="flex-1 min-w-0 px-2 py-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-medium truncate ${
                        (m.status || '').toLowerCase() === 'done' || (m.status || '').toLowerCase() === 'skipped'
                          ? 'text-[#94a3b8] line-through'
                          : 'text-[#0b2b43]'
                      }`}
                    >
                      {m.title}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 mt-1">
                    <span className="inline-flex scale-90 origin-left">
                      <Badge variant={ownerBadgeVariant(m.owner || 'joint')}>
                        {OWNER_OPTIONS.find((o) => o.value === (m.owner || 'joint'))?.label ?? 'Joint'}
                      </Badge>
                    </span>
                    {m.criticality === 'critical' && (
                      <span className="text-[10px] font-medium text-red-700">Critical</span>
                    )}
                    {m.target_date && (
                      <span className="text-[10px] text-[#6b7280]">
                        Due {m.target_date.slice(0, 10)}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className={`flex-1 min-w-0 pl-0 lg:pl-2 ${selected ? panelAccentClass(getTaskUrgency(selected)) : ''}`}>
          {selected ? (
            <div className="pl-3">
              <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                <h4 className="font-semibold text-[#0b2b43] text-lg">{selected.title}</h4>
                <Badge
                  variant={
                    getTaskUrgency(selected) === 'red'
                      ? 'error'
                      : getTaskUrgency(selected) === 'green'
                        ? 'success'
                        : getTaskUrgency(selected) === 'orange'
                          ? 'warning'
                          : 'neutral'
                  }
                >
                  {getTaskUrgency(selected) === 'red'
                    ? 'Overdue / urgent'
                    : getTaskUrgency(selected) === 'orange'
                      ? 'Attention'
                      : getTaskUrgency(selected) === 'green'
                        ? 'Complete'
                        : 'On list'}
                </Badge>
              </div>
              {selected.description && (
                <p className="text-sm text-[#4b5563] mb-3">{selected.description}</p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mb-4">
                <label className="block">
                  <span className="text-xs font-medium text-[#6b7280]">Status</span>
                  <select
                    className="mt-1 w-full rounded-md border border-[#e2e8f0] px-2 py-1.5 text-sm"
                    value={(selected.status || 'pending').toLowerCase()}
                    disabled={updating}
                    onChange={(e) => patchMilestone(selected.id, { status: e.target.value })}
                  >
                    {STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-[#6b7280]">Owner</span>
                  <select
                    className="mt-1 w-full rounded-md border border-[#e2e8f0] px-2 py-1.5 text-sm"
                    value={selected.owner || 'joint'}
                    disabled={updating}
                    onChange={(e) => patchMilestone(selected.id, { owner: e.target.value })}
                  >
                    {OWNER_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-[#6b7280]">Criticality</span>
                  <select
                    className="mt-1 w-full rounded-md border border-[#e2e8f0] px-2 py-1.5 text-sm"
                    value={selected.criticality === 'critical' ? 'critical' : 'normal'}
                    disabled={updating}
                    onChange={(e) => patchMilestone(selected.id, { criticality: e.target.value })}
                  >
                    {CRITICALITY_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-[#6b7280]">Due date</span>
                  <input
                    type="date"
                    className="mt-1 w-full rounded-md border border-[#e2e8f0] px-2 py-1.5 text-sm"
                    value={selected.target_date ? selected.target_date.slice(0, 10) : ''}
                    disabled={updating}
                    onChange={(e) =>
                      patchMilestone(selected.id, {
                        target_date: e.target.value || undefined,
                      })
                    }
                  />
                </label>
              </div>

              <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
                {selected.actual_date && (
                  <div>
                    <dt className="text-[#6b7280] text-xs">Completed</dt>
                    <dd>{selected.actual_date.slice(0, 10)}</dd>
                  </div>
                )}
                {selected.target_date && (
                  <div>
                    <dt className="text-[#6b7280] text-xs">Due</dt>
                    <dd>
                      {selected.target_date.slice(0, 10)}
                      {parseYmd(selected.target_date) &&
                        getTaskUrgency(selected) === 'red' && (
                          <span className="text-red-600 text-xs ml-1">(overdue)</span>
                        )}
                    </dd>
                  </div>
                )}
              </dl>

              <label className="block text-sm mb-2">
                <span className="text-xs font-medium text-[#6b7280]">Notes</span>
                <textarea
                  className="mt-1 w-full min-h-[88px] rounded-md border border-[#e2e8f0] px-2 py-1.5 text-sm"
                  placeholder="Status updates, blockers, links…"
                  value={noteDraft}
                  disabled={updating}
                  onChange={(e) => setNoteDraft(e.target.value)}
                  onBlur={() => saveNotes()}
                />
              </label>
              <Button variant="outline" size="sm" disabled={updating} onClick={() => saveNotes()}>
                Save notes
              </Button>
            </div>
          ) : (
            <div className="text-sm text-[#6b7280] pl-3">Select a task</div>
          )}
        </div>
      </div>
    </Card>
  );
};
