import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FeedbackTab } from '../../components/admin/FeedbackTab';
import { WorkBoard } from './mission-control/WorkBoard';
import { AdminLayout } from './AdminLayout';

type View = 'inbox' | 'work';

/**
 * Merged "Feedback & Work" admin tab. Consolidates the former separate Feedback and
 * Mission Control tabs into one surface with two sub-views:
 *   - Inbox      → raw pilot-feedback submissions (triage, dismiss/delete)
 *   - Work board → the triaged/ranked demands those submissions feed into
 * The old /admin/mission-control route redirects here with ?view=work.
 */
const AdminFeedback: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState<View>(params.get('view') === 'work' ? 'work' : 'inbox');

  const select = (v: View) => {
    setView(v);
    const next = new URLSearchParams(params);
    if (v === 'work') next.set('view', 'work');
    else next.delete('view');
    setParams(next, { replace: true });
  };

  const TABS: { id: View; label: string }[] = [
    { id: 'inbox', label: 'Inbox' },
    { id: 'work', label: 'Work board' },
  ];

  return (
    <AdminLayout
      title="Feedback & Work"
      subtitle="Pilot feedback and the engineering work it turns into — one place."
    >
      <div
        className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-0.5"
        role="tablist"
        aria-label="Feedback and work views"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={view === t.id}
            onClick={() => select(t.id)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              view === t.id ? 'bg-navy-800 text-white' : 'text-slate-600 hover:text-navy-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === 'inbox' ? <FeedbackTab /> : <WorkBoard />}
    </AdminLayout>
  );
};

export default AdminFeedback;
