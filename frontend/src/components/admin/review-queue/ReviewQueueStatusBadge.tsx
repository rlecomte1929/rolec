import React from 'react';

type Status = 'new' | 'triaged' | 'assigned' | 'in_progress' | 'blocked' | 'waiting' | 'resolved' | 'rejected' | 'deferred' | 'reopened';

const STYLES: Record<Status, string> = {
  new: 'bg-slate-100 text-slate-700',
  triaged: 'bg-blue-100 text-blue-800',
  assigned: 'bg-indigo-100 text-indigo-800',
  in_progress: 'bg-amber-100 text-amber-800',
  blocked: 'bg-red-100 text-red-800',
  waiting: 'bg-amber-50 text-amber-900',
  resolved: 'bg-green-100 text-green-800',
  rejected: 'bg-slate-200 text-slate-600',
  deferred: 'bg-slate-100 text-slate-600',
  reopened: 'bg-blue-50 text-blue-700',
};

interface Props {
  status: Status | string;
  label?: string;
}

export const ReviewQueueStatusBadge: React.FC<Props> = ({ status, label }) => {
  const s = (status || 'new').toLowerCase().replace(/-/g, '_') as Status;
  const cls = STYLES[s] || STYLES.new;
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label ?? s.replace(/_/g, ' ')}
    </span>
  );
};
