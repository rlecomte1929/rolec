import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { buildRoute, type RouteKey } from '../../navigation/routes';

export interface AdminTab {
  /** Route key passed to buildRoute() — must be a valid RouteKey. */
  key: RouteKey;
  label: string;
  /**
   * When true, the tab is only active on an exact path match.
   * Use for "overview/dashboard" tabs that would otherwise match all sub-routes.
   * Defaults to false (prefix match).
   */
  exact?: boolean;
}

interface Props {
  title: string;
  subtitle?: string;
  tabs: AdminTab[];
  children: React.ReactNode;
  /** Optional content rendered to the right of the page title (selectors, actions). */
  headerRight?: React.ReactNode;
}

/**
 * Unified admin sub-section layout: page header + a consistent tab strip.
 *
 * Replaces the three independent tab implementations that previously existed
 * (AdminOpsLayout, AdminReviewQueueLayout, AdminFreshnessLayout) which each
 * used incompatible visual styles. All three are now thin wrappers around this
 * component.
 *
 * Token spec:
 *   active   — bg #0b2b43 (navy), text white, no border
 *   inactive — bg white, border var(--border-secondary, #e2e8f0), text slate-600
 *   shape    — border-radius 6px, padding 5px 12px, font-size 12px / font-weight 500
 *
 * Always exposes `headerRight` so callers can place filters or actions in the
 * page header without needing a separate wrapper.
 */
export const AdminTabLayout: React.FC<Props> = ({
  title,
  subtitle,
  tabs,
  children,
  headerRight,
}) => {
  const { pathname } = useLocation();

  const isActive = (tab: AdminTab): boolean => {
    const path = buildRoute(tab.key);
    return tab.exact
      ? pathname === path
      : pathname === path || pathname.startsWith(`${path}/`);
  };

  return (
    <AdminLayout title={title} subtitle={subtitle} headerRight={headerRight}>
      <div className="mb-5 flex flex-wrap items-center gap-1.5 border-b border-slate-200 pb-3">
        {tabs.map((tab) => {
          const active = isActive(tab);
          return (
            <Link
              key={tab.key}
              to={buildRoute(tab.key)}
              className={
                active
                  ? 'rounded-md bg-[#0b2b43] px-3 py-1 text-xs font-medium text-white'
                  : 'rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300 hover:bg-slate-50'
              }
              aria-current={active ? 'page' : undefined}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {children}
    </AdminLayout>
  );
};
