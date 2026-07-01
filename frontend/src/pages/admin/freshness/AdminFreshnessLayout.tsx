import React from 'react';
import { AdminTabLayout, type AdminTab } from '../AdminTabLayout';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Optional content rendered to the right of the page title (selectors, actions). */
  headerRight?: React.ReactNode;
}

// Overview uses an exact match so it doesn't stay active across all sub-routes.
const TABS: AdminTab[] = [
  { key: 'adminFreshness', label: 'Overview', exact: true },
  { key: 'adminFreshnessCountries', label: 'Countries' },
  { key: 'adminFreshnessCities', label: 'Cities' },
  { key: 'adminFreshnessSources', label: 'Sources' },
  { key: 'adminSourceMonitor', label: 'Source pages' },
  { key: 'adminFreshnessChanges', label: 'Changes' },
  { key: 'adminFreshnessStaleContent', label: 'Stale content' },
  { key: 'adminCrawlSchedules', label: 'Schedules' },
  { key: 'adminCrawlJobRuns', label: 'Job runs' },
];

export const AdminFreshnessLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => (
  <AdminTabLayout title={title} subtitle={subtitle} tabs={TABS} headerRight={headerRight}>
    {children}
  </AdminTabLayout>
);
