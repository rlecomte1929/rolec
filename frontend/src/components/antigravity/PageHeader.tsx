import React from 'react';
import { Link } from 'react-router-dom';

export interface Crumb {
  label: string;
  /** Optional route; the last crumb is usually the current page (no href). */
  href?: string;
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Optional uppercase identity line above the breadcrumb (e.g. Admin console). */
  eyebrow?: string;
  /** Breadcrumb trail; rendered as a nav landmark. */
  breadcrumbs?: Crumb[];
  /** Right-aligned actions (buttons, scope chips). */
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Antigravity PageHeader — one shared page-title block (HEADER-1). The app had no
 * shared header: AppShell and AdminLayout each rendered their own, and ~58 pages
 * hand-rolled an <h1>. This standardises eyebrow + breadcrumb + title/subtitle +
 * an actions slot so every page header looks the same. Breadcrumbs render in a
 * `nav` landmark; crumbs with an href become router links.
 */
export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  eyebrow,
  breadcrumbs,
  actions,
  className = '',
}) => (
  <div className={`mb-6 ${className}`}>
    {eyebrow && (
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-600 mb-1">{eyebrow}</p>
    )}
    {breadcrumbs && breadcrumbs.length > 0 && (
      <nav aria-label="Breadcrumb" className="mb-1">
        <ol className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          {breadcrumbs.map((c, i) => {
            const last = i === breadcrumbs.length - 1;
            return (
              <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
                {c.href && !last ? (
                  <Link to={c.href} className="hover:text-navy-800 transition-colors">{c.label}</Link>
                ) : (
                  <span className={last ? 'text-slate-600' : undefined} aria-current={last ? 'page' : undefined}>
                    {c.label}
                  </span>
                )}
                {!last && <span className="text-slate-500" aria-hidden="true">/</span>}
              </li>
            );
          })}
        </ol>
      </nav>
    )}
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1 max-w-2xl text-pretty break-words">{subtitle}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  </div>
);
