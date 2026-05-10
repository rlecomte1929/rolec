import React from 'react';
import { AdminLayout } from './AdminLayout';
import { ErrorTicketsTab } from '../../components/admin/ErrorTicketsTab';

export const AdminErrors: React.FC = () => {
  return (
    <AdminLayout title="Errors" subtitle="Frontend errors captured in production, grouped by fingerprint.">
      <ErrorTicketsTab />
    </AdminLayout>
  );
};
