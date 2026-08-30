/**
 * ProviderRow — displays a provider and their tasks for a case,
 * with inline status controls on each task.
 */
import React, { useState } from 'react';
import { Button } from '../antigravity/Button';
import { patchProviderTask } from '../../api/providers';
import type { ProviderItem, ProviderTaskItem } from '../../api/providers';

const STATUS_LABELS: Record<ProviderTaskItem['status'], { label: string; cls: string }> = {
  pending:     { label: 'Pending',     cls: 'bg-[#e0f2fe] text-[#0369a1]' },
  in_progress: { label: 'In progress', cls: 'bg-[#fef9c3] text-[#854d0e]' },
  completed:   { label: 'Completed',   cls: 'bg-[#dcfce7] text-[#166534]' },
  blocked:     { label: 'Blocked',     cls: 'bg-[#fee2e2] text-[#991b1b]' },
};

const NEXT_STATUSES: Record<ProviderTaskItem['status'], ProviderTaskItem['status'][]> = {
  pending:     ['in_progress', 'blocked'],
  in_progress: ['completed',   'blocked'],
  blocked:     ['pending',     'in_progress'],
  completed:   ['pending'],
};

interface TaskRowProps {
  task: ProviderTaskItem;
  onUpdated: (t: ProviderTaskItem) => void;
}

const TaskRow: React.FC<TaskRowProps> = ({ task, onUpdated }) => {
  const [saving, setSaving] = useState(false);
  const s = STATUS_LABELS[task.status] ?? STATUS_LABELS.pending;

  const advance = async (newStatus: ProviderTaskItem['status']) => {
    setSaving(true);
    try {
      const updated = await patchProviderTask(task.id, { status: newStatus });
      onUpdated(updated);
    } finally {
      setSaving(false);
    }
  };

  return (
    <li className="flex flex-wrap items-start gap-3 py-2 border-t border-[#f1f5f9] first:border-t-0">
      {/* task info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-[#0b2b43]">{task.title}</span>
          <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${s.cls}`}>{s.label}</span>
          {task.due_date && (
            <span className="text-xs text-slate-500">Due {task.due_date}</span>
          )}
        </div>
        {task.description && (
          <p className="mt-0.5 text-xs text-[#6b7280] leading-snug">{task.description}</p>
        )}
      </div>

      {/* status advance buttons */}
      <div className="flex gap-1 shrink-0 flex-wrap">
        {NEXT_STATUSES[task.status]?.map((ns) => (
          <Button unstyled
            key={ns}
            disabled={saving}
            onClick={() => advance(ns)}
            className="text-xs px-2.5 py-1 rounded border border-[#d1d5db] text-[#374151] bg-white hover:bg-[#f9fafb] disabled:opacity-50 transition-colors"
          >
            {saving ? '…' : STATUS_LABELS[ns]?.label}
          </Button>
        ))}
      </div>
    </li>
  );
};


interface ProviderRowProps {
  provider: ProviderItem;
  tasks: ProviderTaskItem[];
  caseId: string;
  onTaskUpdated: (t: ProviderTaskItem) => void;
  onInvite: (provider: ProviderItem) => void;
  onAssignTask: (provider: ProviderItem) => void;
}

export const ProviderRow: React.FC<ProviderRowProps> = ({
  provider, tasks, onTaskUpdated, onInvite, onAssignTask,
}) => {
  const [expanded, setExpanded] = useState(true);
  const done = tasks.filter((t) => t.status === 'completed').length;
  const blocked = tasks.filter((t) => t.status === 'blocked').length;

  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white overflow-hidden">
      {/* Provider header */}
      <Button unstyled
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-[#f8fafc] transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* avatar */}
          <div className="w-8 h-8 rounded-full bg-[#0b2b43] text-white text-xs font-semibold flex items-center justify-center shrink-0">
            {provider.name.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-[#0b2b43] truncate">{provider.name}</div>
            {provider.service_type && (
              <div className="text-xs text-[#6b7280]">{provider.service_type}</div>
            )}
          </div>
          {/* task summary chips */}
          {tasks.length > 0 && (
            <div className="flex gap-1.5 ml-2">
              <span className="text-xs text-[#6b7280] bg-[#f1f5f9] rounded-full px-2 py-0.5">
                {done}/{tasks.length} done
              </span>
              {blocked > 0 && (
                <span className="text-xs text-[#991b1b] bg-[#fee2e2] rounded-full px-2 py-0.5">
                  {blocked} blocked
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button unstyled
            onClick={(e) => { e.stopPropagation(); onAssignTask(provider); }}
            className="text-xs font-medium px-2.5 py-1 rounded border border-[#d1d5db] text-[#374151] bg-white hover:bg-[#f9fafb] transition-colors"
          >
            + Task
          </Button>
          <Button unstyled
            onClick={(e) => { e.stopPropagation(); onInvite(provider); }}
            className="text-xs font-medium px-2.5 py-1 rounded border border-[#bfdbfe] bg-[#eff6ff] text-[#1d4ed8] hover:bg-[#dbeafe] transition-colors"
          >
            Invite
          </Button>
          <span className="text-slate-500 text-sm select-none">{expanded ? '▲' : '▼'}</span>
        </div>
      </Button>

      {/* Task list */}
      {expanded && (
        <div className="px-4 pb-3">
          {tasks.length === 0 ? (
            <p className="text-xs text-slate-500 py-2">No tasks assigned yet.</p>
          ) : (
            <ul>
              {tasks.map((t) => (
                <TaskRow key={t.id} task={t} onUpdated={onTaskUpdated} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
