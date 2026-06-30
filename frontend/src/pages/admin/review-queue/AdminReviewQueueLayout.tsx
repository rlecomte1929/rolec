import React from 'react';
import { AdminTabLayout, type AdminTab } from '../AdminTabLayout';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Optional content rendered to the right of the page title (selectors, actions). */
  headerRight?: React.ReactNode;
}

// Queue uses an exact match so it stays distinct from the Workload sub-route.
const TABS: AdminTab[] = [
  { key: 'adminReviewQueue', label: 'Queue', exact: true },
  { key: 'adminReviewQueueWorkload', label: 'Workload' },
];

export const AdminReviewQueueLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => (
  <AdminTabLayout title={title} subtitle={subtitle} tabs={TABS} headerRight={headerRight}>
    {children}
  </AdminTabLayout>
);
