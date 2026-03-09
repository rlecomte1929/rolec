import React from 'react';

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-200 text-gray-700',
  in_review: 'bg-amber-100 text-amber-800',
  approved: 'bg-blue-100 text-blue-800',
  published: 'bg-green-100 text-green-800',
  archived: 'bg-slate-200 text-slate-600',
};

export const StatusBadge: React.FC<{ status?: string; label?: string }> = ({
  status = 'draft',
  label,
}) => (
  <span
    className={`px-2 py-0.5 rounded text-xs font-medium ${
      STATUS_STYLES[status] || 'bg-gray-200 text-gray-700'
    }`}
  >
    {label ?? status}
  </span>
);
