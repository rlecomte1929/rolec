import React from 'react';
import { AdminTabLayout, type AdminTab } from '../AdminTabLayout';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Optional content rendered to the right of the page title (selectors, actions). */
  headerRight?: React.ReactNode;
}

// Dashboard tab needs an exact match (otherwise it matches all /admin/ops/* sub-routes).
const TABS: AdminTab[] = [
  { key: 'adminOps', label: 'Dashboard', exact: true },
  { key: 'adminOpsSla', label: 'SLA' },
  { key: 'adminOpsQueue', label: 'Queue' },
  { key: 'adminOpsReviewers', label: 'Reviewers' },
  { key: 'adminOpsDestinations', label: 'Destinations' },
  { key: 'adminOpsNotifications', label: 'Alerts' },
];

/**
 * Shared Ops-section chrome. Thin wrapper around AdminTabLayout with six tabs:
 * Dashboard / SLA / Queue / Reviewers / Destinations / Alerts. Sidebar's
 * "Ops analytics" link points to /admin/ops which lands on the Dashboard tab.
 */
export const AdminOpsLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => (
  <AdminTabLayout title={title} subtitle={subtitle} tabs={TABS} headerRight={headerRight}>
    {children}
  </AdminTabLayout>
);
