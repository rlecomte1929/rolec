import React, { useState } from 'react';
import { FeedbackTab } from '../../components/admin/FeedbackTab';
import { ProductMetricsTab } from '../../components/admin/ProductMetricsTab';
import { Tabs, tabPanelProps, type TabItem } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';

/**
 * "Feedback & Work" admin tab — the pilot-feedback Inbox.
 *
 * AIQ-1565 (BUG-260716-BB94): the Work board sub-view (the former "Mission Control"
 * page) was retired. It ranked the demands the Inbox submissions feed into, but the
 * Inbox already carries that information and is where triage-to-Notion actually
 * happens, so the second view was redundant — two buttons, one useful surface.
 *
 * The sub-view toggle is gone: this route now renders the Inbox and nothing else.
 * `?view=work` is inert (harmless on an old bookmark), and the legacy
 * /admin/mission-control route redirects here — see App.tsx.
 */
const TABS: TabItem[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'metrics', label: 'Product metrics' },
];

const AdminFeedback: React.FC = () => {
  const [active, setActive] = useState<'inbox' | 'metrics'>('inbox');
  return (
    <AdminLayout
      title="Feedback & Work"
      subtitle="Pilot feedback and the product analytics behind it — one place."
    >
      <Tabs
        tabs={TABS}
        activeId={active}
        onChange={(id) => setActive(id as 'inbox' | 'metrics')}
        aria-label="Feedback views"
        className="mb-4"
      />
      <div {...tabPanelProps(active)}>
        {active === 'inbox' ? <FeedbackTab /> : <ProductMetricsTab />}
      </div>
    </AdminLayout>
  );
};

export default AdminFeedback;
