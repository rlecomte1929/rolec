import React from 'react';

export type JourneyStatus =
  | 'done' | 'in-progress' | 'upcoming' | 'blocked'
  | 'action' | 'ready' | 'submitted' | 'in-review';

const STYLES: Record<JourneyStatus, string> = {
  done:          'bg-navy-50 text-navy-800',
  'in-progress': 'bg-accent-50 text-accent-600',
  upcoming:      'bg-[#f3f4f6] text-[#6b7280]',
  blocked:       'bg-[#f4efe5] text-[#7a5e2a]',
  action:        'bg-[#f4efe5] text-[#7a5e2a]',
  ready:         'bg-accent-50 text-accent-600',
  submitted:     'bg-navy-50 text-navy-800',
  'in-review':   'bg-[#f3f4f6] text-[#374151]',
};

interface StatusPillProps {
  status: JourneyStatus;
  children: React.ReactNode;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, children, className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${STYLES[status]} ${className}`}
  >
    {children}
  </span>
);
