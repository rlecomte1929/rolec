/**
 * ProviderPortal — public magic-link landing page for external providers.
 *
 * Flow:
 *  1. Read ?token= from URL query params
 *  2. Verify token with backend (no regular auth required)
 *  3. Fetch and display the provider's tasks
 *
 * This page intentionally does NOT use AppShell (no HR/employee nav needed).
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../components/antigravity/Button';
import {
  storeProviderToken,
  getStoredProviderToken,
  verifyProviderToken,
  getPortalTasks,
  patchPortalTask,
  getPortalCaseSummary,
} from '../api/providerPortal';
import type { PortalTask, CaseSummary } from '../api/providerPortal';

// ── Status badge ─────────────────────────────────────────────────────────────

const STATUS_COLOURS: Record<PortalTask['status'], string> = {
  pending:    'bg-amber-100 text-amber-800',
  in_progress:'bg-blue-100 text-blue-800',
  completed:  'bg-green-100 text-green-800',
  blocked:    'bg-red-100 text-red-800',
};

const StatusBadge: React.FC<{ status: PortalTask['status'] }> = ({ status }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_COLOURS[status]}`}>
    {status.replace('_', ' ')}
  </span>
);

// ── Task card ─────────────────────────────────────────────────────────────────

interface TaskCardProps {
  task: PortalTask;
  token: string;
  onUpdate: (updated: PortalTask) => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, token, onUpdate }) => {
  const [note, setNote] = useState(task.provider_note ?? '');
  const [saving, setSaving] = useState(false);

  const markInProgress = async () => {
    setSaving(true);
    try {
      const updated = await patchPortalTask(token, task.id, { status: 'in_progress' });
      onUpdate(updated);
    } finally { setSaving(false); }
  };

  const markComplete = async () => {
    setSaving(true);
    try {
      const updated = await patchPortalTask(token, task.id, { status: 'completed', provider_note: note });
      onUpdate(updated);
    } finally { setSaving(false); }
  };

  const saveNote = async () => {
    setSaving(true);
    try {
      const updated = await patchPortalTask(token, task.id, { provider_note: note });
      onUpdate(updated);
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <h3 className="font-medium text-slate-900">{task.title}</h3>
        <StatusBadge status={task.status} />
      </div>

      {task.description && (
        <p className="text-sm text-slate-600 mb-3">{task.description}</p>
      )}

      {task.due_date && (
        <p className="text-xs text-slate-400 mb-3">
          Due: {new Date(task.due_date).toLocaleDateString()}
        </p>
      )}

      {task.billable_amount != null && (
        <p className="text-xs text-slate-500 mb-3">
          Billable: {task.billable_amount.toFixed(2)}
        </p>
      )}

      {task.hr_notes && (
        <div className="mb-3 rounded bg-slate-50 border border-slate-100 px-3 py-2 text-xs text-slate-600">
          <span className="font-medium">HR note:</span> {task.hr_notes}
        </div>
      )}

      <textarea
        className="w-full rounded border border-slate-200 px-3 py-2 text-sm text-slate-800 resize-none focus:outline-none focus:ring-2 focus:ring-[#0b2b43] mb-3"
        rows={2}
        placeholder="Add a note for HR…"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />

      <div className="flex gap-2 flex-wrap">
        {task.status === 'pending' && (
          <Button unstyled
            onClick={markInProgress}
            disabled={saving}
            className="px-3 py-1.5 rounded bg-navy-800 text-white text-xs font-medium hover:bg-navy-900 disabled:opacity-50"
          >
            Mark in progress
          </Button>
        )}
        {task.status !== 'completed' && (
          <Button unstyled
            onClick={markComplete}
            disabled={saving}
            className="px-3 py-1.5 rounded bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50"
          >
            Mark complete
          </Button>
        )}
        {note !== (task.provider_note ?? '') && (
          <Button unstyled
            onClick={saveNote}
            disabled={saving}
            className="px-3 py-1.5 rounded bg-slate-700 text-white text-xs font-medium hover:bg-slate-800 disabled:opacity-50"
          >
            Save note
          </Button>
        )}
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────

type Phase = 'verifying' | 'ready' | 'invalid';

export const ProviderPortal: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [phase, setPhase] = useState<Phase>('verifying');
  const [token, setToken] = useState<string>('');
  const [tasks, setTasks] = useState<PortalTask[]>([]);
  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [providerName, setProviderName] = useState<string | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(false);

  useEffect(() => {
    const urlToken = searchParams.get('token');
    const storedToken = getStoredProviderToken();
    const resolvedToken = urlToken ?? storedToken ?? '';

    if (!resolvedToken) {
      setPhase('invalid');
      return;
    }

    verifyProviderToken(resolvedToken)
      .then((result) => {
        if (!result.valid) { setPhase('invalid'); return; }
        if (urlToken) storeProviderToken(urlToken);
        setToken(resolvedToken);
        setPhase('ready');
      })
      .catch(() => setPhase('invalid'));
  }, [searchParams]);

  useEffect(() => {
    if (phase !== 'ready' || !token) return;
    setLoadingTasks(true);
    Promise.all([
      getPortalTasks(token),
      getPortalCaseSummary(token).catch(() => null),
    ]).then(([tasksRes, summaryRes]) => {
      setTasks(tasksRes.tasks);
      setProviderName(tasksRes.provider_name);
      setSummary(summaryRes);
    }).finally(() => setLoadingTasks(false));
  }, [phase, token]);

  const handleTaskUpdate = (updated: PortalTask) => {
    setTasks((prev) => prev.map((t) => t.id === updated.id ? updated : t));
  };

  // ── Verifying ──
  if (phase === 'verifying') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-8 h-8 rounded-full border-2 border-[#0b2b43] border-t-transparent animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Verifying your access link…</p>
        </div>
      </div>
    );
  }

  // ── Invalid token ──
  if (phase === 'invalid') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="max-w-sm text-center">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
            <span className="text-red-600 text-xl">✕</span>
          </div>
          <h2 className="text-lg font-semibold text-slate-900 mb-2">Link expired or invalid</h2>
          <p className="text-sm text-slate-500">
            This portal link is no longer valid. Please ask HR to send you a new invite link.
          </p>
        </div>
      </div>
    );
  }

  // ── Ready ──
  const pending   = tasks.filter((t) => t.status === 'pending');
  const active    = tasks.filter((t) => t.status === 'in_progress');
  const completed = tasks.filter((t) => t.status === 'completed');

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-3">
        <img src="/relopass-logo.png" alt="ReloPass" className="h-7 w-auto" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
        <span className="font-semibold text-slate-900">ReloPass · Provider Portal</span>
        {providerName && (
          <span className="ml-auto text-sm text-slate-500">{providerName}</span>
        )}
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Summary strip */}
        {summary && (
          <div className="mb-6 grid grid-cols-3 gap-4">
            {[
              { label: 'Tasks total',     value: String(summary.tasks_total) },
              { label: 'Completed',       value: String(summary.tasks_completed) },
              { label: 'Total billable',  value: summary.total_billable != null ? `${summary.total_billable.toFixed(2)} ${summary.currency}` : '—' },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-white border border-slate-200 px-4 py-3 text-center shadow-sm">
                <p className="text-xs text-slate-500 mb-1">{label}</p>
                <p className="text-lg font-semibold text-slate-900">{value}</p>
              </div>
            ))}
          </div>
        )}

        {loadingTasks ? (
          <div className="text-center py-16 text-sm text-slate-400">Loading your tasks…</div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-16 text-sm text-slate-400">No tasks assigned yet.</div>
        ) : (
          <>
            {active.length > 0 && (
              <section className="mb-8">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">In progress</h2>
                <div className="space-y-3">
                  {active.map((t) => <TaskCard key={t.id} task={t} token={token} onUpdate={handleTaskUpdate} />)}
                </div>
              </section>
            )}
            {pending.length > 0 && (
              <section className="mb-8">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">Pending</h2>
                <div className="space-y-3">
                  {pending.map((t) => <TaskCard key={t.id} task={t} token={token} onUpdate={handleTaskUpdate} />)}
                </div>
              </section>
            )}
            {completed.length > 0 && (
              <section className="mb-8">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">Completed</h2>
                <div className="space-y-3">
                  {completed.map((t) => <TaskCard key={t.id} task={t} token={token} onUpdate={handleTaskUpdate} />)}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
};
