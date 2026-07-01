import { useState, useMemo, useEffect, useRef } from 'react';
import {
  CheckSquare, Search, Filter, LayoutGrid, List, Calendar, User,
  Plane, Globe, Shield, Package, AlertTriangle, ChevronDown,
  Plus, X, Layers, Clock,
} from 'lucide-react';
import { tw } from '../../lib/colors';
import {
  SAMPLE_TASKS,
  TASK_STATUSES,
  TASK_PRIORITIES,
  TASK_CATEGORIES,
  RELOCATION_CASES,
  daysUntil,
  formatDate,
  countTasksByStatus,
  countByCategory,
  countOverdue,
  getUrgentTasks,
  caseTaskCounts,
  type RelocationTask,
  type TaskStatus,
  type TaskPriority,
  type TaskCategory,
} from './sample-data';

// ─── Styles ──────────────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<TaskPriority, string> = {
  High: tw.priority.high,
  Medium: tw.priority.medium,
  Low: tw.priority.low,
};

const STATUS_STYLE: Record<TaskStatus, { badge: string; column: string }> = {
  'To Do': {
    badge: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] border-[var(--space-border-default)]',
    column: 'bg-[var(--space-surface-muted)]',
  },
  'In Progress': {
    badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]',
    column: 'bg-[var(--space-brand-primary-50)]/50',
  },
  Done: {
    badge: 'bg-green-500/15 text-green-300 border-green-500/30',
    column: 'bg-green-500/10',
  },
};

const CATEGORY_META: Record<TaskCategory, { label: string; icon: typeof Globe; badge: string }> = {
  immigration: { label: 'Immigration', icon: Globe, badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]' },
  compliance: { label: 'Compliance', icon: Shield, badge: 'bg-amber-500/15 text-amber-300' },
  logistics: { label: 'Logistics', icon: Package, badge: 'bg-[var(--space-brand-highlight-100)] text-[var(--space-text-accent)]' },
};

const CASE_STATUS_DOT: Record<string, string> = {
  Active: 'bg-[var(--space-brand-primary)]',
  'At Risk': 'bg-amber-500',
  Completed: 'bg-[var(--space-semantic-success)]',
};

declare global {
  function useWorkspaceDB<T = unknown>(
    table: string,
    options?: {
      shared?: boolean;
      limit?: number;
      offset?: number;
      orderBy?: { column: string; direction: 'asc' | 'desc' };
      filters?: Array<{ column: string; operator: string; value: unknown }>;
    },
  ): { data: T[]; loading: boolean; error: Error | null; total: number; refresh: () => void };

  interface Window {
    __workspaceDb: {
      from: (table: string, opts?: { shared?: boolean }) => {
        insert: (row: Record<string, unknown>) => Promise<void>;
        bulkInsert: (rows: Record<string, unknown>[]) => Promise<void>;
        update: (id: number, row: Record<string, unknown>) => Promise<void>;
        delete: (id: number) => Promise<void>;
      };
    };
  }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function DueDateBadge({ date, status }: { date: string; status: TaskStatus }) {
  const days = daysUntil(date);
  if (status === 'Done') {
    return <span className="text-xs text-[var(--space-text-muted)]">{formatDate(date)}</span>;
  }
  if (days === null) return <span className="text-xs text-[var(--space-text-muted)]">{formatDate(date)}</span>;
  if (days < 0) {
    return (
      <span className="text-xs font-semibold text-red-600 flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" />
        {formatDate(date)} · {Math.abs(days)}d overdue
      </span>
    );
  }
  if (days <= 7) {
    return (
      <span className="text-xs font-semibold text-amber-600">
        {formatDate(date)} · {days}d left
      </span>
    );
  }
  return <span className="text-xs text-[var(--space-text-secondary)]">{formatDate(date)}</span>;
}

function CaseReference({ reference, onClick }: { reference: string; onClick?: () => void }) {
  const caseMeta = RELOCATION_CASES.find((c) => c.reference === reference);
  const inner = (
    <>
      {caseMeta ? (
        <span className="flex items-center gap-1 min-w-0">
          <span className="px-1 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-muted)] text-[9px] font-bold flex-shrink-0">
            {caseMeta.originCode}
          </span>
          <Plane className="w-3 h-3 flex-shrink-0 text-[var(--space-brand-primary)]" />
          <span className="px-1 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-muted)] text-[9px] font-bold flex-shrink-0">
            {caseMeta.destinationCode}
          </span>
          <span className="truncate">{caseMeta.employeeName}</span>
        </span>
      ) : (
        <span className="flex items-center gap-1 truncate">
          <Plane className="w-3 h-3 flex-shrink-0" />
          {reference}
        </span>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="text-xs text-[var(--space-text-brand)] font-medium hover:underline text-left min-w-0"
      >
        {inner}
      </button>
    );
  }
  return <p className="text-xs text-[var(--space-text-brand)] font-medium min-w-0">{inner}</p>;
}

function TaskCard({
  task,
  onStatusChange,
  onCaseClick,
  compact,
}: {
  task: RelocationTask;
  onStatusChange: (id: number, status: TaskStatus) => void;
  onCaseClick?: (caseRef: string) => void;
  compact?: boolean;
}) {
  const cat = CATEGORY_META[task.category as TaskCategory] || CATEGORY_META.immigration;
  const CatIcon = cat.icon;

  return (
    <div className={`p-3.5 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] shadow-sm hover:shadow-md transition-shadow ${
      task.status === 'Done' ? 'opacity-75' : ''
    }`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className={`text-sm font-semibold leading-snug ${
          task.status === 'Done' ? 'text-[var(--space-text-muted)] line-through' : 'text-[var(--space-text-primary)]'
        }`}>
          {task.task_name}
        </h4>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${PRIORITY_STYLE[task.priority as TaskPriority]}`}>
          {task.priority}
        </span>
      </div>

      <div className="mb-2">
        <CaseReference reference={task.case_reference} onClick={onCaseClick ? () => onCaseClick(task.case_reference) : undefined} />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--space-text-muted)] mb-3">
        <span className="flex items-center gap-1"><User className="w-3 h-3" /> {task.assigned_owner}</span>
        <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${cat.badge}`}>
          <CatIcon className="w-3 h-3" /> {cat.label}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2">
        <DueDateBadge date={task.due_date} status={task.status as TaskStatus} />
        {!compact && (
          <select
            value={task.status}
            onChange={(e) => onStatusChange(task.id, e.target.value as TaskStatus)}
            className="text-[10px] border border-[var(--space-border-default)] rounded-md px-1.5 py-1 bg-[var(--space-surface-card)] text-[var(--space-text-secondary)]"
          >
            {TASK_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

function KanbanColumn({
  status,
  tasks,
  onStatusChange,
  onCaseClick,
}: {
  status: TaskStatus;
  tasks: RelocationTask[];
  onStatusChange: (id: number, status: TaskStatus) => void;
  onCaseClick: (caseRef: string) => void;
}) {
  const style = STATUS_STYLE[status];

  return (
    <div className="flex flex-col min-w-[260px] flex-1">
      <div className={`px-3 py-2 rounded-t-xl border border-b-0 border-[var(--space-border-default)] ${style.column}`}>
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)]">{status}</h3>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${style.badge}`}>{tasks.length}</span>
        </div>
      </div>
      <div className="flex-1 p-2 space-y-2.5 rounded-b-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/40 min-h-[200px]">
        {tasks.length === 0 ? (
          <p className="text-xs text-[var(--space-text-muted)] text-center py-8 italic">No tasks</p>
        ) : (
          tasks.map((t) => (
            <TaskCard key={t.id} task={t} onStatusChange={onStatusChange} onCaseClick={onCaseClick} />
          ))
        )}
      </div>
    </div>
  );
}

function ListRow({
  task,
  onStatusChange,
  onCaseClick,
}: {
  task: RelocationTask;
  onStatusChange: (id: number, status: TaskStatus) => void;
  onCaseClick: (caseRef: string) => void;
}) {
  const cat = CATEGORY_META[task.category as TaskCategory] || CATEGORY_META.immigration;
  const CatIcon = cat.icon;
  const statusStyle = STATUS_STYLE[task.status as TaskStatus];

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-[1.5fr_1.3fr_0.9fr_0.7fr_0.8fr_0.7fr] gap-2 sm:gap-3 items-center px-4 py-3 border-b border-[var(--space-border-default)] hover:bg-[var(--space-surface-card-hover)] transition-colors ${
      task.status === 'Done' ? 'opacity-70' : ''
    }`}>
      <p className={`text-sm font-medium truncate ${task.status === 'Done' ? 'line-through text-[var(--space-text-muted)]' : 'text-[var(--space-text-primary)]'}`}>
        {task.task_name}
      </p>
      <div className="min-w-0">
        <CaseReference reference={task.case_reference} onClick={() => onCaseClick(task.case_reference)} />
      </div>
      <p className="text-xs text-[var(--space-text-secondary)] truncate hidden sm:block">{task.assigned_owner}</p>
      <div className="hidden sm:block">
        <DueDateBadge date={task.due_date} status={task.status as TaskStatus} />
      </div>
      <span className={`hidden sm:inline-flex w-fit px-2 py-0.5 rounded-full text-[10px] font-semibold ${PRIORITY_STYLE[task.priority as TaskPriority]}`}>
        {task.priority}
      </span>
      <div className="flex items-center gap-2">
        <span className={`hidden sm:inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium border ${statusStyle.badge}`}>
          {task.status}
        </span>
        <span className={`sm:hidden inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${cat.badge}`}>
          <CatIcon className="w-3 h-3" /> {cat.label}
        </span>
        <select
          value={task.status}
          onChange={(e) => onStatusChange(task.id, e.target.value as TaskStatus)}
          className="text-[10px] border border-[var(--space-border-default)] rounded-md px-1.5 py-1 bg-[var(--space-surface-card)]"
        >
          {TASK_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

function CaseChip({
  caseRef,
  openCount,
  totalCount,
  selected,
  onSelect,
}: {
  caseRef: (typeof RELOCATION_CASES)[0];
  openCount: number;
  totalCount: number;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex-shrink-0 px-3 py-2 rounded-xl border text-left transition-all min-w-[160px] ${
        selected
          ? 'border-[var(--space-brand-primary)] bg-[var(--space-brand-primary-50)] ring-1 ring-[var(--space-brand-primary)]'
          : 'border-[var(--space-border-default)] bg-[var(--space-surface-card)] hover:border-[var(--space-border-strong)]'
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${CASE_STATUS_DOT[caseRef.status] || 'bg-[var(--space-text-muted)]'}`} />
        <span className="text-[10px] font-bold text-[var(--space-text-secondary)]">
          {caseRef.originCode} → {caseRef.destinationCode}
        </span>
      </div>
      <p className="text-xs font-semibold text-[var(--space-text-primary)] truncate">{caseRef.employeeName}</p>
      <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5">
        {openCount} open · {totalCount} total
      </p>
    </button>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────

export default function TasksDB() {
  const { data: tasks, loading, error, total, refresh } = useWorkspaceDB<RelocationTask>('relocation_tasks', {
    shared: true,
    orderBy: { column: 'due_date', direction: 'asc' },
    limit: 100,
  });

  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');
  const [groupByCase, setGroupByCase] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<'all' | TaskCategory>('all');
  const [filterCase, setFilterCase] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<'all' | TaskPriority>('all');
  const [filterStatus, setFilterStatus] = useState<'all' | TaskStatus>('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const seededRef = useRef(false);

  const [newTask, setNewTask] = useState({
    task_name: '',
    assigned_owner: '',
    due_date: '',
    priority: 'Medium' as TaskPriority,
    case_reference: 'Sarah Chen — Singapore → London',
    category: 'immigration' as TaskCategory,
  });

  useEffect(() => {
    if (loading || seededRef.current) return;
    if (total > 0) {
      seededRef.current = true;
      return;
    }
    seededRef.current = true;
    (async () => {
      try {
        await window.__workspaceDb.from('relocation_tasks', { shared: true }).bulkInsert(SAMPLE_TASKS);
        refresh();
      } catch {
        seededRef.current = false;
      }
    })();
  }, [loading, total, refresh]);

  const taskList = tasks || [];
  const metrics = useMemo(() => countTasksByStatus(taskList), [taskList]);
  const categoryCounts = useMemo(() => countByCategory(taskList), [taskList]);
  const overdueCount = useMemo(() => countOverdue(taskList), [taskList]);
  const urgentTasks = useMemo(() => getUrgentTasks(taskList), [taskList]);
  const caseCounts = useMemo(() => caseTaskCounts(taskList), [taskList]);

  const filteredTasks = useMemo(() => {
    let result = taskList;
    if (filterCategory !== 'all') result = result.filter((t) => t.category === filterCategory);
    if (filterCase !== 'all') result = result.filter((t) => t.case_reference === filterCase);
    if (filterPriority !== 'all') result = result.filter((t) => t.priority === filterPriority);
    if (filterStatus !== 'all') result = result.filter((t) => t.status === filterStatus);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (t) =>
          t.task_name.toLowerCase().includes(q) ||
          t.case_reference.toLowerCase().includes(q) ||
          t.assigned_owner.toLowerCase().includes(q),
      );
    }
    return result;
  }, [taskList, filterCategory, filterCase, filterPriority, filterStatus, searchQuery]);

  const tasksByStatus = useMemo(() => {
    const map: Record<TaskStatus, RelocationTask[]> = {
      'To Do': [],
      'In Progress': [],
      Done: [],
    };
    filteredTasks.forEach((t) => {
      const s = t.status as TaskStatus;
      if (map[s]) map[s].push(t);
    });
    return map;
  }, [filteredTasks]);

  const groupedByCase = useMemo(() => {
    const groups: Record<string, RelocationTask[]> = {};
    filteredTasks.forEach((t) => {
      if (!groups[t.case_reference]) groups[t.case_reference] = [];
      groups[t.case_reference].push(t);
    });
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredTasks]);

  const handleStatusChange = async (id: number, status: TaskStatus) => {
    await window.__workspaceDb.from('relocation_tasks', { shared: true }).update(id, { status });
    refresh();
  };

  const handleCaseClick = (caseRef: string) => {
    setFilterCase((prev) => (prev === caseRef ? 'all' : caseRef));
  };

  const handleAddTask = async () => {
    const name = newTask.task_name.trim();
    const owner = newTask.assigned_owner.trim();
    if (!name || !owner || !newTask.due_date) return;
    const caseMeta = RELOCATION_CASES.find((c) => c.reference === newTask.case_reference);
    setBusy(true);
    try {
      await window.__workspaceDb.from('relocation_tasks', { shared: true }).insert({
        task_name: name,
        assigned_owner: owner,
        due_date: newTask.due_date,
        priority: newTask.priority,
        status: 'To Do',
        case_id: caseMeta?.id ?? null,
        case_reference: newTask.case_reference,
        category: newTask.category,
      });
      setNewTask({
        task_name: '',
        assigned_owner: '',
        due_date: '',
        priority: 'Medium',
        case_reference: 'Sarah Chen — Singapore → London',
        category: 'immigration',
      });
      setShowAddForm(false);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <CheckSquare className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)]">Relocation Tasks</h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                Coordinator workboard — daily tasks linked to active mobility cases
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-[var(--space-border-default)] overflow-hidden">
              <button
                onClick={() => setViewMode('kanban')}
                className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                  viewMode === 'kanban' ? tw.button.primary : 'bg-[var(--space-surface-card)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
                }`}
                title="Kanban board"
              >
                <LayoutGrid className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Board</span>
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                  viewMode === 'list' ? tw.button.primary : 'bg-[var(--space-surface-card)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
                }`}
                title="List view"
              >
                <List className="w-3.5 h-3.5" /> <span className="hidden sm:inline">List</span>
              </button>
            </div>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${tw.button.accent}`}
            >
              {showAddForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{showAddForm ? 'Cancel' : 'Add task'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="px-5 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel)]">
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {[
            { label: 'To do', value: metrics.todo, color: 'text-[var(--space-text-secondary)]' },
            { label: 'In progress', value: metrics.inProgress, color: 'text-[var(--space-brand-primary)]' },
            { label: 'Done', value: metrics.done, color: 'text-[var(--space-semantic-success)]' },
            { label: 'Overdue', value: overdueCount, color: overdueCount > 0 ? 'text-red-600' : 'text-[var(--space-text-muted)]' },
            { label: 'Immigration', value: categoryCounts.immigration, color: 'text-[var(--space-text-brand)]' },
            { label: 'Compliance / Logistics', value: categoryCounts.compliance + categoryCounts.logistics, color: 'text-[var(--space-text-accent)]' },
          ].map((m) => (
            <div key={m.label} className="text-center">
              <p className={`text-lg sm:text-xl font-bold ${m.color}`}>{m.value}</p>
              <p className="text-[10px] sm:text-xs text-[var(--space-text-secondary)]">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Urgent tasks */}
      {urgentTasks.length > 0 && filterStatus !== 'Done' && (
        <div className="px-5 py-3 border-b border-amber-500/30 bg-amber-500/10">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-amber-400" />
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-300">Needs attention today</p>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-200">{urgentTasks.length}</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {urgentTasks.slice(0, 6).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setFilterCase(t.case_reference);
                  setSearchQuery('');
                }}
                className="flex-shrink-0 px-3 py-2 rounded-lg border border-amber-500/30 bg-[var(--space-surface-card)] text-left hover:border-amber-500/50 transition-colors max-w-[220px]"
              >
                <p className="text-xs font-semibold text-[var(--space-text-primary)] truncate">{t.task_name}</p>
                <p className="text-[10px] text-amber-300 mt-0.5 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                  <DueDateBadge date={t.due_date} status={t.status as TaskStatus} />
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Case corridor chips */}
      <div className="px-5 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-2 mb-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-secondary)]">Active cases</p>
          {filterCase !== 'all' && (
            <button
              type="button"
              onClick={() => setFilterCase('all')}
              className="text-[10px] font-medium text-[var(--space-text-brand)] hover:underline"
            >
              Clear case filter
            </button>
          )}
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          <button
            type="button"
            onClick={() => setFilterCase('all')}
            className={`flex-shrink-0 px-3 py-2 rounded-xl border text-left transition-all ${
              filterCase === 'all'
                ? 'border-[var(--space-brand-primary)] bg-[var(--space-brand-primary-50)]'
                : 'border-[var(--space-border-default)] bg-[var(--space-surface-muted)] hover:border-[var(--space-border-strong)]'
            }`}
          >
            <p className="text-xs font-semibold text-[var(--space-text-primary)]">All cases</p>
            <p className="text-[10px] text-[var(--space-text-muted)]">{taskList.length} tasks</p>
          </button>
          {RELOCATION_CASES.filter((c) => c.status !== 'Completed' || (caseCounts[c.reference]?.open ?? 0) > 0).map((c) => {
            const counts = caseCounts[c.reference] || { total: 0, open: 0 };
            return (
              <CaseChip
                key={c.id}
                caseRef={c}
                openCount={counts.open}
                totalCount={counts.total}
                selected={filterCase === c.reference}
                onSelect={() => setFilterCase(c.reference)}
              />
            );
          })}
        </div>
      </div>

      {/* Add task form */}
      {showAddForm && (
        <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-brand-highlight-50)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3">New relocation task</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <input
              type="text"
              placeholder="Task name"
              value={newTask.task_name}
              onChange={(e) => setNewTask({ ...newTask, task_name: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            />
            <input
              type="text"
              placeholder="Assigned owner"
              value={newTask.assigned_owner}
              onChange={(e) => setNewTask({ ...newTask, assigned_owner: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            />
            <input
              type="date"
              value={newTask.due_date}
              onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            />
            <select
              value={newTask.case_reference}
              onChange={(e) => setNewTask({ ...newTask, case_reference: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            >
              {RELOCATION_CASES.map((c) => (
                <option key={c.id} value={c.reference}>{c.reference}</option>
              ))}
            </select>
            <select
              value={newTask.priority}
              onChange={(e) => setNewTask({ ...newTask, priority: e.target.value as TaskPriority })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            >
              {TASK_PRIORITIES.map((p) => <option key={p} value={p}>{p} priority</option>)}
            </select>
            <select
              value={newTask.category}
              onChange={(e) => setNewTask({ ...newTask, category: e.target.value as TaskCategory })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg'}
            >
              {TASK_CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_META[c].label}</option>)}
            </select>
          </div>
          <button
            onClick={handleAddTask}
            disabled={busy || !newTask.task_name.trim() || !newTask.assigned_owner.trim() || !newTask.due_date}
            className={`mt-3 px-4 py-2 text-sm rounded-lg ${tw.button.primary} disabled:opacity-50`}
          >
            Add to board
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="px-5 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)] space-y-2.5">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
          <Search className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search task, case, or owner…"
            className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-[var(--space-text-muted)]" />
          <div className="flex items-center gap-1 flex-wrap">
            {(['all', ...TASK_STATUSES] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                  filterStatus === s ? tw.button.primary : tw.button.secondary
                }`}
              >
                {s === 'all' ? 'All statuses' : s}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 flex-wrap">
            {(['all', ...TASK_CATEGORIES] as const).map((c) => (
              <button
                key={c}
                onClick={() => setFilterCategory(c)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                  filterCategory === c ? tw.button.primary : tw.button.secondary
                }`}
              >
                {c === 'all' ? 'All categories' : CATEGORY_META[c].label}
              </button>
            ))}
          </div>
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value as 'all' | TaskPriority)}
            className="text-xs border border-[var(--space-border-default)] rounded-full px-2.5 py-1 bg-[var(--space-surface-card)] text-[var(--space-text-secondary)]"
          >
            <option value="all">All priorities</option>
            {TASK_PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          {viewMode === 'list' && (
            <button
              type="button"
              onClick={() => setGroupByCase(!groupByCase)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1 transition-all ${
                groupByCase ? tw.button.primary : tw.button.secondary
              }`}
            >
              <Layers className="w-3 h-3" /> Group by case
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 sm:p-5">
        {loading ? (
          <div className="text-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--space-brand-primary)] mx-auto" />
            <p className="text-sm text-[var(--space-text-muted)] mt-3">Loading relocation tasks…</p>
          </div>
        ) : error ? (
          <div className="text-center py-16 text-red-600 text-sm">Error: {error.message}</div>
        ) : filteredTasks.length === 0 ? (
          <div className="text-center py-16">
            <CheckSquare className="w-10 h-10 text-[var(--space-text-muted)] mx-auto mb-3" />
            <p className="text-sm text-[var(--space-text-secondary)]">No tasks match your filters.</p>
          </div>
        ) : viewMode === 'kanban' ? (
          <div className="flex gap-4 overflow-x-auto pb-2 min-h-[400px]">
            {TASK_STATUSES.map((status) => (
              <KanbanColumn
                key={status}
                status={status}
                tasks={tasksByStatus[status]}
                onStatusChange={handleStatusChange}
                onCaseClick={handleCaseClick}
              />
            ))}
          </div>
        ) : groupByCase ? (
          <div className="space-y-5">
            {groupedByCase.map(([caseRef, caseTasks]) => {
              const caseMeta = RELOCATION_CASES.find((c) => c.reference === caseRef);
              return (
                <div key={caseRef} className="rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] overflow-hidden">
                  <div className="px-4 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-muted)] flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <CaseReference reference={caseRef} onClick={() => handleCaseClick(caseRef)} />
                      {caseMeta && (
                        <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5">
                          Coordinator: {caseMeta.coordinator} · {caseMeta.status}
                        </p>
                      )}
                    </div>
                    <span className="text-xs font-semibold text-[var(--space-text-secondary)] flex-shrink-0">
                      {caseTasks.length} task{caseTasks.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  {caseTasks.map((t) => (
                    <ListRow key={t.id} task={t} onStatusChange={handleStatusChange} onCaseClick={handleCaseClick} />
                  ))}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] overflow-hidden">
            <div className="hidden sm:grid grid-cols-[1.5fr_1.3fr_0.9fr_0.7fr_0.8fr_0.7fr] gap-3 px-4 py-2.5 border-b border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
              {['Task', 'Case', 'Owner', 'Due date', 'Priority', 'Status'].map((h) => (
                <p key={h} className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">{h}</p>
              ))}
            </div>
            {filteredTasks.map((t) => (
              <ListRow key={t.id} task={t} onStatusChange={handleStatusChange} onCaseClick={handleCaseClick} />
            ))}
          </div>
        )}
      </div>

      <div className="px-5 py-2.5 border-t border-[var(--space-border-default)] bg-[var(--space-surface-muted)] flex items-center justify-between">
        <p className="text-[10px] text-[var(--space-text-muted)]">
          {filteredTasks.length} of {taskList.length} tasks · Immigration, compliance & logistics
        </p>
        <span className="text-[10px] font-medium text-[var(--space-text-brand)] flex items-center gap-1">
          <Calendar className="w-3 h-3" /> Sorted by due date
          <ChevronDown className="w-3 h-3" />
        </span>
      </div>
    </div>
  );
}
