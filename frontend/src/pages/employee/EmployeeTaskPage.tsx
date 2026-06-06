/**
 * EmployeeTaskPage — lists and allows submission of tasks assigned to the employee.
 * Uses servicesAPI.getTasks() (AIQ-34-B).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { AppShell } from '../../components/AppShell';
import { servicesAPI } from '../../api/client';
import type { EmployeeTask } from '../../api/client';

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

// ── Task card ─────────────────────────────────────────────────────────────────

interface TaskCardProps {
  task: EmployeeTask;
  onSubmit: (task: EmployeeTask) => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onSubmit }) => {
  const [submitting, setSubmitting] = useState(false);
  const [note, setNote] = useState('');

  const handleSubmit = async () => {
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
            disabled={submitting}
            className="px-4 py-1.5 rounded bg-[#0b2b43] text-white text-sm font-medium hover:bg-[#0d3456] disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit'}
          </Button>
        </>
      )}
    </div>
  );
};

// ── Page ──────────────────────────────────────────────────────────────────────

export const EmployeeTaskPage: React.FC = () => {
  const [tasks, setTasks] = useState<EmployeeTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await servicesAPI.getTasks();
      setTasks(res.tasks);
    } catch {
      setError('Could not load your tasks. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleSubmit = (updated: EmployeeTask) => {
    setTasks((prev) => prev.map((t) => t.id === updated.id ? updated : t));
  };

  const pending   = tasks.filter((t) => t.status === 'pending' || t.status === 'revision_requested');
  const submitted = tasks.filter((t) => t.status === 'submitted');
  const approved  = tasks.filter((t) => t.status === 'approved');

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
            <Button unstyled onClick={load} className="ml-2 underline">Retry</Button>
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-sm text-slate-400">Loading your tasks…</div>
        ) : tasks.length === 0 && !error ? (
          <div className="text-center py-16">
            <p className="text-slate-500 text-sm">No tasks yet — your HR team hasn't assigned anything.</p>
          </div>
        ) : (
          <>
            {pending.length > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Action needed · {pending.length}
                </h2>
                <div className="space-y-3">
                  {pending.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} />)}
                </div>
              </section>
            )}
            {submitted.length > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Awaiting review · {submitted.length}
                </h2>
                <div className="space-y-3">
                  {submitted.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} />)}
                </div>
              </section>
            )}
            {approved.length > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Done · {approved.length}
                </h2>
                <div className="space-y-3">
                  {approved.map((t) => <TaskCard key={t.id} task={t} onSubmit={handleSubmit} />)}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
};
