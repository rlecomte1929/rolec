import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { buildRoute } from '../../../navigation/routes';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const AdminFreshnessLayout: React.FC<Props> = ({ title, subtitle, children }) => {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <AdminLayout title={title} subtitle={subtitle}>
      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <Link
          to={buildRoute('adminFreshness')}
          className={`rounded px-2 py-1 text-sm ${
            location.pathname === '/admin/freshness'
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Overview
        </Link>
        <Link
          to={buildRoute('adminFreshnessCountries')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/freshness/countries')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Countries
        </Link>
        <Link
          to={buildRoute('adminFreshnessCities')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/freshness/cities')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Cities
        </Link>
        <Link
          to={buildRoute('adminFreshnessSources')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/freshness/sources')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Sources
        </Link>
        <Link
          to={buildRoute('adminFreshnessChanges')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/freshness/changes')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Changes
        </Link>
        <Link
          to={buildRoute('adminFreshnessStaleContent')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/freshness/stale-content')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Stale content
        </Link>
        <Link
          to={buildRoute('adminCrawlSchedules')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/crawl/schedules')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Schedules
        </Link>
        <Link
          to={buildRoute('adminCrawlJobRuns')}
          className={`rounded px-2 py-1 text-sm ${
            isActive('/admin/crawl/job-runs')
              ? 'bg-[#0b2b43] text-white'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Job runs
        </Link>
      </div>
      {children}
    </AdminLayout>
  );
};
