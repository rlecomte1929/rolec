import React from 'react';
import { AdminLayout } from './AdminLayout';
import { FeedbackTab } from '../../components/admin/FeedbackTab';

const AdminFeedback: React.FC = () => {
  return (
    <AdminLayout
      title="Pilot Feedback"
      subtitle="Submissions from the feedback widget. Triage and track what to act on."
    >
      <FeedbackTab />
    </AdminLayout>
  );
};

export default AdminFeedback;
