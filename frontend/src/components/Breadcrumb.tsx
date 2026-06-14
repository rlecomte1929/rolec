// Breadcrumb.tsx — single source of truth for the page-top breadcrumb.
//
// Renders: ReloPass / Section / Page
// Used by:
//   - AppShell.tsx (inline, above the H1)
//   - v2 custom-layout pages that don't use AppShell (Company Profile,
//     Mobility command center, Provider Status, Policy Builder, etc.) —
//     they import this directly and render it above their custom header
//
// Section labels mirror the sidebar SECTIONS config in
// PlatformShellSidebar.tsx ('Employee' / 'HR Operations' / 'Admin · ReloPass').
// Pages pass section + title explicitly so a sidebar section rename does
// not silently break individual page breadcrumbs.

import React from 'react';
import { Link } from 'react-router-dom';

export interface BreadcrumbProps {
  /** Top-level section, e.g. 'HR Operations' or 'Employee'. */
  section?: string;
  /** Current page title, e.g. 'Cases', 'Provider status'. */
  title: string;
  /** Optional href for the ReloPass root link. Default: '/'. */
  homeHref?: string;
  /** Extra utility classes (e.g. for margin / inline placement). */
  className?: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({
  section,
  title,
  homeHref = '/',
  className = '',
}) => {
  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center gap-1.5 text-sm text-slate-500 min-w-0 ${className}`}
    >
      <Link
        to={homeHref}
        className="text-slate-400 hover:text-slate-700 transition-colors"
      >
        ReloPass
      </Link>
      {section && (
        <>
          <span className="text-slate-300" aria-hidden="true">/</span>
          <span className="text-slate-500 truncate">{section}</span>
        </>
      )}
      <span className="text-slate-300" aria-hidden="true">/</span>
      <span className="text-slate-700 font-medium truncate" aria-current="page">
        {title}
      </span>
    </nav>
  );
};

export default Breadcrumb;
