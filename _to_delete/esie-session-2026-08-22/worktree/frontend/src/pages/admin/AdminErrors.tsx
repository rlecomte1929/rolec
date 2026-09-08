import React from 'react';
import { ErrorTicketsTab } from '../../components/admin/ErrorTicketsTab';
import { AdminLayout } from './AdminLayout';

export const AdminErrors: React.FC = () => {
  return (
    <AdminLayout title="Errors" subtitle="Frontend errors captured in production, grouped by fingerprint.">
      <ErrorTicketsTab />
    </AdminLayout>
  );
};
