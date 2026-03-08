import React from 'react';
import { Link } from 'react-router-dom';
import { buildRoute } from '../../../navigation/routes';

type Summary = {
  comment_count: number;
  last_comment_at?: string;
  status?: string;
  is_unread?: boolean;
};

interface Props {
  targetType: 'review_queue_item' | 'ops_notification' | 'staged_resource_candidate' | 'staged_event_candidate' | 'live_resource' | 'live_event';
  targetId: string;
  summary: Summary | null;
  linkRoute?: string;
  linkParams?: Record<string, string>;
}

export const ThreadSummaryBadge: React.FC<Props> = ({
  targetType,
  targetId,
  summary,
  linkRoute,
  linkParams = {},
}) => {
  if (!summary || summary.comment_count === 0) return null;

  const to = linkRoute ? buildRoute(linkRoute as any, { ...linkParams, id: targetId }) : undefined;
  const badge = (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs ${
        summary.is_unread ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'
      }`}
      title={summary.last_comment_at ? `Last: ${new Date(summary.last_comment_at).toLocaleString()}` : undefined}
    >
      <span aria-hidden>💬</span>
      <span>{summary.comment_count}</span>
    </span>
  );

  if (to) {
    return <Link to={to} className="hover:opacity-80">{badge}</Link>;
  }
  return badge;
};
