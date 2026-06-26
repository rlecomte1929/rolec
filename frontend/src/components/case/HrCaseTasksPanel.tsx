/**
 * HrCaseTasksPanel  (AIQ-34-C)
 *
 * Shows all employee tasks for a relocation case from the HR perspective:
 *   - Progress bar + completion badge
 *   - Per-task approve / request-revision inline actions
 *   - "Add task" form (HR creates a task for the employee)
 *
 * Polls every 8 seconds so the HR user sees fresh status without refreshing
 * the whole page (reduced from original 60s to match demo UX requirements).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Checkbox } from '../antigravity/Checkbox';
import { Input } from '../antigravity/Input';
import { hrAPI } from '../../api/client';
import type { EmployeeTask, EmployeeTaskListResponse, TaskType } from '../../api/client';
import { Alert, Button, Card, LoadingButton, ProgressBar } from '../antigravity';
import { ProviderCoordinationPanel } from '../ProviderCoordinationPanel';

// ── helpers ──────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  submitted: 'Submitted',
  revision_requested: 'Revision requested',
  approved: 'Approved',
};

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-[#f3f4f6] text-[#4b5563]',
  submitted: 'bg-[#eef4f8] text-[#1d4ed8]',
  revision_requested: 'bg-[#f6f2e9] text-[#7a5e2a]',
  approved: 'bg-[#eef7f6] text-[#1f8e8b]',
};

function formatDue(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return 'Due today';
  if (diff < 0) return `${Math.abs(diff)}d overdue`;
  if (diff === 1) return 'Due tomorrow';
  return `Due in ${diff}d`;
}

function isOverdue(iso: string | null | undefined): boolean {
  if (!iso) return false;
  return new Date(iso) < new Date(new Date().toDateString());
}

const TASK_TYPES: { value: TaskType; label: string }[] = [
  { value: 'document_upload', label: 'Document upload' },
  { value: 'address_confirmation', label: 'Address confirmation' },
  { value: 'acknowledgment', label: 'Acknowledgment' },
  { value: 'selection', label: 'Selection' },
  { value: 'custom', label: 'Custom / other' },
];

// ── TaskRow ───────────────────────────────────────────────────────────────────

interface TaskRowProps {
  task: EmployeeTask;
  caseId: string;
  onUpdated: (t: EmployeeTask) => void;
}

const TaskRow: React.FC<TaskRowProps> = ({ task, caseId, onUpdated }) => {
  const [reviewNote, setReviewNote] = useState('');
  const [loading, setLoading] = useState<'approve' | 'revision' | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const canReview = task.status === 'submitted';

  const handleAction = async (action: 'approved' | 'revision_requested') => {
    setLoading(action === 'approved' ? 'approve' : 'revision');
    setRowError(null);
    try {
      const updated = await hrAPI.reviewTask(caseId, task.id, {
        action,
        review_note: reviewNote.trim() || undefined,
      });
      onUpdated(updated);
      setReviewNote('');
    } catch {
      setRowError('Failed to save review. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div
      className={`border rounded-lg p-4 space-y-2 ${
        isOverdue(task.due_date) && task.status === 'pending'
          ? 'border-[#fca5a5]'
          : 'border-[#e2e8f0]'
      }`}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-start gap-3 justify-between">
        <div className="flex-1 min-w-0">
          <Button unstyled
            type="button"
            className="text-left w-full"
            onClick={() => setExpanded((v) => !v)}
          >
            <span className="font-medium text-[#0b2b43] text-sm">{task.title}</span>
          </Button>
          {task.description && (
            <p className="text-xs text-[#6b7280] mt-0.5 line-clamp-1">{task.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {task.due_date && (
            <span
              className={`text-xs ${
                isOverdue(task.due_date) && task.status === 'pending'
                  ? 'text-[#ef4444] font-medium'
                  : 'text-[#6b7280]'
              }`}
            >
              {formatDue(task.due_date)}
            </span>
          )}
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              STATUS_COLOR[task.status] ?? 'bg-[#f3f4f6] text-[#4b5563]'
            }`}
          >
            {STATUS_LABEL[task.status] ?? task.status}
          </span>
        </div>
      </div>

      {/* Expanded details + review form */}
      {expanded && (
        <div className="space-y-3 pt-2 border-t border-[#f1f5f9]">
          {task.submitted_at && (
            <div className="text-xs text-[#6b7280]">
              Submitted {new Date(task.submitted_at).toLocaleString()}
              {task.review_note && (
                <span className="ml-2 text-[#7a5e2a]">Note: {task.review_note}</span>
              )}
            </div>
          )}
          {task.file_url && (
            <div className="text-xs">
              <a
                href={task.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#1d4ed8] underline"
              >
                View uploaded file ↗
              </a>
            </div>
          )}
          {task.submission_data && (
            <pre className="text-xs bg-[#f8fafc] border border-[#e2e8f0] rounded p-2 overflow-x-auto max-h-40">
              {JSON.stringify(task.submission_data, null, 2)}
            </pre>
          )}

          {canReview && (
            <div className="space-y-2">
              <textarea
                className="w-full text-sm border border-[#e2e8f0] rounded p-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
                rows={2}
                placeholder="Review note (optional)"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
              />
              <div className="flex gap-2">
                <LoadingButton
                  loading={loading === 'approve'}
                  onClick={() => handleAction('approved')}
                  variant="primary"
                  size="sm"
                >
                  Approve
                </LoadingButton>
                <LoadingButton
                  loading={loading === 'revision'}
                  onClick={() => handleAction('revision_requested')}
                  variant="outline"
                  size="sm"
                >
                  Request revision
                </LoadingButton>
              </div>
              {rowError && <Alert variant="error">{rowError}</Alert>}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── AddTaskForm ───────────────────────────────────────────────────────────────

interface AddTaskFormProps {
  caseId: string;
  employeeId: string;
  onAdded: (t: EmployeeTask) => void;
  onCancel: () => void;
}

const AddTaskForm: React.FC<AddTaskFormProps> = ({ caseId, employeeId, onAdded, onCancel }) => {
  const [taskType, setTaskType] = useState<TaskType>('custom');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [requireFile, setRequireFile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setFormError('Title is required.');
      return;
    }
    setLoading(true);
    setFormError(null);
    try {
      const created = await hrAPI.addCaseTask(caseId, {
        employee_id: employeeId,
        task_type: taskType,
        title: title.trim(),
        description: description.trim() || undefined,
        due_date: dueDate || undefined,
        required_file_upload: requireFile,
      });
      onAdded(created);
    } catch {
      setFormError('Failed to create task. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 border border-[#e2e8f0] rounded-lg p-4 bg-[#f8fafc]"
    >
      <div className="text-sm font-semibold text-[#0b2b43]">New task</div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Type</label>
          <select
            className="w-full text-sm border border-[#e2e8f0] rounded p-2 bg-white focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
            value={taskType}
            onChange={(e) => setTaskType(e.target.value as TaskType)}
          >
            {TASK_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Due date</label>
          <Input unstyled
            type="date"
            className="w-full text-sm border border-[#e2e8f0] rounded p-2 focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
            value={dueDate}
            onChange={(v) => setDueDate(v)}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-1">Title *</label>
        <Input unstyled
          type="text"
          className="w-full text-sm border border-[#e2e8f0] rounded p-2 focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
          placeholder="e.g. Upload proof of address"
          value={title}
          onChange={(v) => setTitle(v)}
        />
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-1">Description / instructions</label>
        <textarea
          className="w-full text-sm border border-[#e2e8f0] rounded p-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <Checkbox
          checked={requireFile}
          onChange={(e) => setRequireFile(e.target.checked)}
          className="rounded border-[#e2e8f0]"
        />
        <span className="text-[#4b5563]">Require file upload</span>
      </label>

      {formError && <Alert variant="error">{formError}</Alert>}

      <div className="flex gap-2">
        <LoadingButton loading={loading} variant="primary" size="sm">
          Create task
        </LoadingButton>
        <Button variant="outline" size="sm" onClick={onCancel} type="button">
          Cancel
        </Button>
      </div>
    </form>
  );
};

// ── HrCaseTasksPanel ──────────────────────────────────────────────────────────

interface HrCaseTasksPanelProps {
  caseId: string;
}

export const HrCaseTasksPanel: React.FC<HrCaseTasksPanelProps> = ({ caseId }) => {
  const [data, setData] = useState<EmployeeTaskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const result = await hrAPI.getCaseTasks(caseId);
      setData(result);
      setError(null);
    } catch {
      setError('Could not load tasks.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void fetchTasks();
    // Poll every 8s — fast enough for demo UX, light enough not to hammer the API
    pollRef.current = setInterval(() => void fetchTasks(), 8_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchTasks]);

  const recomputeStats = (tasks: EmployeeTask[]) => {
    const completed = tasks.filter(
      (t) => t.status === 'submitted' || t.status === 'approved'
    ).length;
    const total = tasks.length;
    return { total, completed, pct: total ? Math.round((completed / total) * 100) : 0 };
  };

  const handleTaskUpdated = (updated: EmployeeTask) => {
    if (!data) return;
    const tasks = data.tasks.map((t) => (t.id === updated.id ? updated : t));
    setData({ ...data, tasks, stats: recomputeStats(tasks) });
  };

  const handleTaskAdded = (newTask: EmployeeTask) => {
    if (!data) return;
    const tasks = [...data.tasks, newTask];
    setData({ ...data, tasks, stats: recomputeStats(tasks) });
    setShowAddForm(false);
  };

  // Derive employee_id from first task — all tasks share the same employee
  const employeeId = data?.tasks[0]?.employee_id ?? '';

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Employee tasks</div>
        <div className="text-sm text-[#94a3b8]">Loading tasks…</div>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-[#0b2b43]">Employee tasks</span>
          {data && data.stats.total > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[#eef4f8] text-[#0b2b43]">
              {data.stats.completed}/{data.stats.total}
            </span>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowAddForm((v) => !v)}>
          {showAddForm ? 'Cancel' : '+ Add task'}
        </Button>
      </div>

      {/* Progress bar */}
      {data && data.stats.total > 0 && (
        <div className="mb-4">
          <ProgressBar
            value={data.stats.pct}
            color={
              data.stats.pct === 100 ? 'green' : data.stats.pct >= 60 ? 'indigo' : 'yellow'
            }
          />
        </div>
      )}

      {error && (
        <Alert variant="error" className="mb-4">
          {error}
        </Alert>
      )}

      {/* Add task form */}
      {showAddForm && (
        <div className="mb-4">
          <AddTaskForm
            caseId={caseId}
            employeeId={employeeId}
            onAdded={handleTaskAdded}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}

      {/* Task list — pending/revision first, then submitted, then approved */}
      {!data || data.tasks.length === 0 ? (
        <div className="text-sm text-[#94a3b8]">No tasks assigned yet.</div>
      ) : (
        <div className="space-y-2">
          {[...data.tasks]
            .sort((a, b) => {
              const order = { pending: 0, revision_requested: 1, submitted: 2, approved: 3 };
              return (order[a.status] ?? 9) - (order[b.status] ?? 9);
            })
            .map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                caseId={caseId}
                onUpdated={handleTaskUpdated}
              />
            ))}
        </div>
      )}

      {/* Provider coordination — housing, immigration, shipping tasks */}
      <ProviderCoordinationPanel caseId={caseId} />
    </Card>
  );
};
