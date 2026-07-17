import React from 'react';
import { FeedbackTab } from '../../components/admin/FeedbackTab';
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
const AdminFeedback: React.FC = () => (
  <AdminLayout
    title="Feedback & Work"
    subtitle="Pilot feedback and the engineering work it turns into — one place."
  >
    <FeedbackTab />
  </AdminLayout>
);

export default AdminFeedback;
