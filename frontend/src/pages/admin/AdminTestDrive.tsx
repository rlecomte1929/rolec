import React from 'react';
import { TestDriveTab } from '../../components/admin/TestDriveTab';
import { AdminLayout } from './AdminLayout';

const AdminTestDrive: React.FC = () => {
  return (
    <AdminLayout
      title="Test Drive"
      subtitle="INSEAD corridor campaign — funnel, pilot leads, and testimonials."
    >
      <TestDriveTab />
    </AdminLayout>
  );
};

export default AdminTestDrive;
