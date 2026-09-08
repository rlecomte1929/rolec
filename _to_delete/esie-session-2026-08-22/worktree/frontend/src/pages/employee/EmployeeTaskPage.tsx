/**
 * EmployeeTaskPage — lists and allows submission of tasks assigned to the employee.
 * Uses servicesAPI.getTasks() (AIQ-34-B).
 */
import React, { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { Badge } from '../../components/antigravity/Badge';
import { AlertTriangle } from 'lucide-react';
import { AppShell } from '../../components/AppShell';
import { buildRoute } from '../../navigation/routes';
import { servicesAPI, apiGet } from '../../api/client';
import type { EmployeeTask, TaskType } from '../../api/client';
import { getCaseRoadmapV2 } from '../../api/roadmapV2';
import type { RoadmapV2Step } from '../../api/roadmapV2';
import { PrivacyNotice } from '../../features/privacy/PrivacyNotice';
import { PRIVACY_NOTICE_VERSION } from '../../features/privacy/privacyNoticeContent';
import { useSelectedCase } from '../../contexts/SelectedCaseContext';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';

// ── Status colours ────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<EmployeeTask['status'], string> = {
  pending:            'bg-amber-100 text-amber-800',
  submitted:          'bg-blue-100 text-blue-800',
  revision_requested: 'bg-orange-100 text-orange-800',
  approved:           'bg-green-100 text-green-800',
};

const STATUS_LABEL: Record<EmployeeTask['status'], string> = {
  pending:            'To do',
  submitted:          'Submitted',
  revision_requested: 'Needs revision',
  approved:           'Approved',
};

// ── Task-completion confirmation copy (audit 3.4) ───────────────────────────────
// Affirming, task-type-specific feedback shown briefly on the card the employee
// just submitted. Upload copy deliberately says "we'll check this over" — NOT
// "HR notified" — since no upload→HR notification trigger is confirmed.
function getCompletionMessage(taskType: TaskType): string {
  switch (taskType) {
    case 'document_upload':
      return '✓ Uploaded — we’ll check this over shortly.';
    case 'address_confirmation':
    case 'acknowledgment':
    case 'selection':
      return '✓ Saved — we’ll review this shortly.';
    default:
      return '✓ Done — your plan has been updated.';
  }
}

// ── Task card ─────────────────────────────────────────────────────────────────

interface TaskCardProps {
  task: EmployeeTask;
  onSubmit: (task: EmployeeTask) => void;
  /** PRIV-005: block submission until the Art. 13 notice is acknowledged. */
  submitDisabled: boolean;
  /** audit 3.4: show the transient completion confirmation on the just-submitted card. */
  justCompleted?: boolean;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onSubmit, submitDisabled, justCompleted = false }) => {
  const [submitting, setSubmitting] = useState(false);
  const [note, setNote] = useState('');

  const handleSubmit = async () => {
    if (submitDisabled) return;
    setSubmitting(true);
    try {
      const updated = await servicesAPI.submitTask(task.id, { submission_data: { note } });
      onSubmit(updated);
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = task.status === 'pending' || task.status === 'revision_requested';

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="mb-1.5">
            <Badge variant="info" size="sm">HR request</Badge>
          </div>
          <h3 className="font-medium text-slate-900">{task.title}</h3>
          {task.due_date && (
            <p className="text-xs text-slate-400 mt-0.5">
              Due {new Date(task.due_date).toLocaleDateString()}
            </p>
          )}
        </div>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[task.status]}`}>
          {STATUS_LABEL[task.status]}
        </span>
      </div>

      {task.description && (
        <p className="text-sm text-slate-600 mb-3">{task.description}</p>
      )}

      {task.status === 'revision_requested' && task.review_note && (
        <div className="mb-3 rounded bg-orange-50 border border-orange-200 px-3 py-2 text-xs text-orange-800">
          <span className="font-medium">Revision requested:</span> {task.review_note}
        </div>
      )}

      {task.status === 'approved' && (
        <div className="mb-3 rounded bg-green-50 border border-green-100 px-3 py-2 text-xs text-green-800">
          ✓ Approved by HR
        </div>
      )}

      {justCompleted && (
        <div
          role="status"
          aria-live="polite"
          className="mb-3 rounded bg-green-50 border border-green-100 px-3 py-2 text-xs font-medium text-green-800"
        >
          {getCompletionMessage(task.task_type)}
        </div>
      )}

      {canSubmit && (
        <>
          <textarea
            className="w-full rounded border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#0b2b43] mb-3"
            rows={2}
            placeholder="Add a note (optional)…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button unstyled
            onClick={handleSubmit}
            disabled={submitting || submitDisabled}
            className="px-4 py-1.5 rounded bg-[#0b2b43] text-white text-sm font-medium hover:bg-[#0d3456] disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit'}
          </Button>
          {submitDisabled && (
            <p className="text-xs text-slate-400 mt-2">
              Acknowledge the privacy notice above to submit.
            </p>
          )}
        </>
      )}
    </div>
  );
};

// ── Roadmap (move) tasks ────────────────────────────────────────────────────────
// AIQ-1248b: surface employee-owned roadmap steps alongside HR-requested tasks so
// "Tasks" is the single place an employee sees everything they need to act on.

type TaskSection = 'action' | 'review' | 'done';

const ROADMAP_STATUS_LABEL: Record<RoadmapV2Step['status'], string> = {
  pending:            'To do',
  in_progress:        'In progress',
  awaiting_employee:  'Your action',
  awaiting_vendor:    'With vendor',
  awaiting_hr:        'With HR',
  blocked:            'Blocked',
  completed:          'Done',
  skipped:            'Skipped',
};

const ROADMAP_STATUS_STYLE: Record<RoadmapV2Step['status'], string> = {
  pending:            'bg-amber-100 text-amber-800',
  in_progress:        'bg-blue-100 text-blue-800',
  awaiting_employee:  'bg-amber-100 text-amber-800',
  awaiting_vendor:    'bg-slate-100 text-slate-700',
  awaiting_hr:        'bg-slate-100 text-slate-700',
  blocked:            'bg-red-100 text-red-800',
  completed:          'bg-green-100 text-green-800',
  skipped:            'bg-slate-100 text-slate-500',
};

/** Which of the 3 sections a roadmap step belongs to (null = not shown). */
function roadmapSection(status: RoadmapV2Step['status']): TaskSection | null {
  switch (status) {
    case 'pending':
    case 'in_progress':
    case 'awaiting_employee':
    case 'blocked':
      return 'action';
    case 'awaiting_vendor':
    case 'awaiting_hr':
      return 'review';
    case 'completed':
      return 'done';
    default:
      return null;
  }
}

export const RoadmapStepCard: React.FC<{ step: RoadmapV2Step }> = ({ step }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between gap-3 mb-3">
      <div>
        <div className="mb-1.5">
          <Badge variant="neutral" size="sm">Move task</Badge>
        </div>
        <h3 className="font-medium text-slate-900">{step.title}</h3>
        {step.due_date && (
          <p className="text-xs text-slate-400 mt-0.5">
            Due {new Date(step.due_date).toLocaleDateString()}
          </p>
        )}
      </div>
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROADMAP_STATUS_STYLE[step.status]}`}>
        {ROADMAP_STATUS_LABEL[step.status]}
      </span>
    </div>
    {step.description && (
      <p className="text-sm text-slate-600">{step.description}</p>
    )}
    {step.non_obvious && step.non_obvious_note && (
      // The trap this step exists to warn about — the reason it matters, in the mover's
      // terms. Amber, matching the "Easy to miss" treatment used on requirement cards, so
      // the two surfaces read as one product. role="note" is announced, not interrupting.
      <div
        role="note"
        className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3"
        data-testid="roadmap-step-trap"
      >
        <div className="mb-1 flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-700" aria-hidden="true" />
          <span className="text-xs font-semibold uppercase tracking-wide text-amber-800">
            Easy to miss
          </span>
        </div>
        <p className="text-sm text-amber-900">{step.non_obvious_note}</p>
      </div>
    )}
  </div>
);

// ── Page ──────────────────────────────────────────────────────────────────────

export const EmployeeTaskPage: React.FC = () => {
  // A2: scope tasks to the viewed case so this page never shows another case's
  // tasks. When no case is selected, getTasks() falls back server-side to the
  // most-recently-updated case (matching the dashboard's active-case selection).
  const { selectedCaseId } = useSelectedCase();
  const { primaryCaseId } = useEmployeeAssignment();
  // AIQ-1248b: the roadmap is fetched for the same case the page is scoped to;
  // fall back to the employee's primary case when nothing is selected. The
  // case-scoped roadmap route accepts the assignment id (matching how the roadmap
  // page is linked elsewhere), so selectedCaseId works directly.
  const roadmapCaseId = selectedCaseId ?? primaryCaseId;
  const queryClient = useQueryClient();
  const tasksQueryKey = ['employee', 'tasks', selectedCaseId ?? null];
  // PRIV-005: one-time persistent privacy-notice gate. Submission stays blocked
  // until the current notice version is acknowledged; a version bump re-prompts.
  // Kept as local state so the PrivacyNotice can still toggle it; seeded from
  // the consent query below.
  const [acknowledged, setAcknowledged] = useState(false);
  // audit 3.4: id of the task whose completion confirmation is currently showing.
  const [completedTaskId, setCompletedTaskId] = useState<string | null>(null);

  const tasksQuery = useQuery({
    queryKey: tasksQueryKey,
    queryFn: async () => {
      const res = await servicesAPI.getTasks(selectedCaseId ?? undefined);
      return res.tasks;
    },
  });
  const tasks: EmployeeTask[] = tasksQuery.data ?? [];

  // AIQ-1248b: employee-owned roadmap steps surfaced as tasks. Completed steps are
  // kept so they show under "Done" (progress visibility); only 'skipped' (not
  // applicable to this case) is dropped. Merged into the same 3 sections as HR tasks.
  const roadmapQuery = useQuery({
    queryKey: ['employee', 'roadmap-tasks', roadmapCaseId ?? null],
    queryFn: async () => {
      const res = await getCaseRoadmapV2(roadmapCaseId as string);
      return res.tracks.flatMap((t) => t.steps);
    },
    enabled: Boolean(roadmapCaseId),
  });
  const roadmapSteps: RoadmapV2Step[] = (roadmapQuery.data ?? []).filter(
    (s) => s.owner === 'employee' && s.status !== 'skipped',
  );

  const loading = tasksQuery.isLoading || (Boolean(roadmapCaseId) && roadmapQuery.isLoading);
  // Only the HR-task source failing is surfaced as an error; a missing/empty
  // roadmap is a normal state, not an error.
  const error = tasksQuery.isError ? 'Could not load your tasks. Please try again.' : null;

  const consentQuery = useQuery({
    queryKey: ['privacy', 'consents', PRIVACY_NOTICE_VERSION],
    queryFn: async () => {
      const res = await apiGet<{ acknowledged: boolean }>(
        `/api/privacy/consents?notice_version=${encodeURIComponent(PRIVACY_NOTICE_VERSION)}`,
      );
      return res.acknowledged;
    },
  });

  // Seed the acknowledgement gate from the consent query (defaults to false,
  // matching the old fetch's catch).
  useEffect(() => {
    if (consentQuery.data !== undefined) setAcknowledged(consentQuery.data);
  }, [consentQuery.data]);

  // Auto-dismiss the completion confirmation after ~4s.
  useEffect(() => {
    if (!completedTaskId) return;
    const timer = setTimeout(() => setCompletedTaskId(null), 4000);
    return () => clearTimeout(timer);
  }, [completedTaskId]);

  const handleSubmit = (updated: EmployeeTask) => {
    queryClient.setQueryData<EmployeeTask[]>(tasksQueryKey, (prev) =>
      prev ? prev.map((t) => (t.id === updated.id ? updated : t)) : prev,
    );
    setCompletedTaskId(updated.id);
  };

  const pending   = tasks.filter((t) => t.status === 'pending' || t.status === 'revision_requested');
  const submitted = tasks.filter((t) => t.status === 'submitted');
  const approved  = tasks.filter((t) => t.status === 'approved');

  // Roadmap steps split into the same 3 sections (action / review / done).
  const rmAction = roadmapSteps.filter((s) => roadmapSection(s.status) === 'action');
  const rmReview = roadmapSteps.filter((s) => roadmapSection(s.status) === 'review');
  const rmDone   = roadmapSteps.filter((s) => roadmapSection(s.status) === 'done');

  const actionCount = pending.length + rmAction.length;
  const reviewCount = submitted.length + rmReview.length;
  const doneCount   = approved.length + rmDone.length;
  // Empty only when BOTH sources have nothing to show.
  const bothEmpty = tasks.length === 0 && roadmapSteps.length === 0;

  return (
    <AppShell>
      <div className="px-4 py-6 max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">My tasks</h1>
          <p className="text-sm text-slate-500 mt-1">
            Documents and actions requested by your HR team.
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
            <Button unstyled onClick={() => void tasksQuery.refetch()} className="ml-2 underline">Retry</Button>
          </div>
        )}

        {!acknowledged && !loading && pending.length > 0 && (
          <div className="mb-6">
            <PrivacyNotice
              noticeVersion={PRIVACY_NOTICE_VERSION}
              context="task_submission"
              variant="banner"
              checked={acknowledged}
              onChange={setAcknowledged}
            />
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-sm text-slate-400">Loading your tasks…</div>
        ) : bothEmpty && !error ? (
          <div className="text-center py-16">
            <p className="text-slate-500 text-sm">No tasks yet — your HR team hasn&rsquo;t assigned anything.</p>
            {/* EMP-2: don't dead-end — point the employee back to where they can make progress. */}
            <p className="mt-2 text-sm">
              <Link to={buildRoute('employeeDashboard')} className="font-medium text-[#1f8e8b] hover:underline">
                While you wait, continue your relocation from your dashboard →
              </Link>
            </p>
          </div>
        ) : (
          <>
            {actionCount > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Action needed · {actionCount}
                </h2>
                <div className="space-y-3">
                  {pending.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} submitDisabled={!acknowledged} justCompleted={completedTaskId === t.id} />)}
                  {rmAction.map((s) => <RoadmapStepCard key={s.id} step={s} />)}
                </div>
              </section>
            )}
            {reviewCount > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Awaiting review · {reviewCount}
                </h2>
                <div className="space-y-3">
                  {submitted.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} submitDisabled={!acknowledged} justCompleted={completedTaskId === t.id} />)}
                  {rmReview.map((s) => <RoadmapStepCard key={s.id} step={s} />)}
                </div>
              </section>
            )}
            {doneCount > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Done · {doneCount}
                </h2>
                <div className="space-y-3">
                  {approved.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} submitDisabled={!acknowledged} justCompleted={completedTaskId === t.id} />)}
                  {rmDone.map((s) => <RoadmapStepCard key={s.id} step={s} />)}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
};
