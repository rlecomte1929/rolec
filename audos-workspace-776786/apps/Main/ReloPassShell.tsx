import { Menu, X } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { NAV_GROUPS, ROUTES, navigateTo, type RouteDef } from './routes';
import { assetUrl } from '../../components/landingContent';

export function ReloPassShell({
  currentPath,
  children,
}: {
  currentPath: string;
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const linksForGroup = (group: RouteDef['group']) =>
    ROUTES.filter((r) => r.group === group && r.path !== '/').slice(0, 8);

  return (
    <div className="min-h-full flex flex-col bg-[var(--space-surface-page)]">
      <header
        className="flex items-center justify-between gap-4 px-4 py-3 border-b"
        style={{ borderColor: 'var(--space-border-default)', backgroundColor: 'var(--space-surface-panel)' }}
      >
        <button
          type="button"
          className="md:hidden p-2 rounded-lg"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <button type="button" className="flex items-center gap-2" onClick={() => navigateTo('/')}>
          <img src={assetUrl('relopass-logo.png')} alt="ReloPass" style={{ height: 28 }} />
          <span className="font-semibold text-[var(--space-text-primary)] hidden sm:inline">ReloPass</span>
        </button>
        <div className="hidden md:flex items-center gap-2 text-xs">
          <button type="button" className="px-3 py-1.5 rounded-lg font-medium text-[var(--space-text-brand)]" onClick={() => navigateTo('/hr/command-center')}>
            Command center
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg font-medium text-[var(--space-text-secondary)]" onClick={() => navigateTo('/employee/dashboard')}>
            Employee demo
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg font-medium text-[var(--space-text-secondary)]" onClick={() => navigateTo('/platform')}>
            Platform
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside
          className={`${mobileOpen ? 'flex' : 'hidden'} md:flex flex-col w-64 border-r overflow-y-auto absolute md:relative z-20 inset-y-0 left-0 md:inset-auto`}
          style={{ borderColor: 'var(--space-border-default)', backgroundColor: 'var(--space-surface-card)' }}
        >
          {NAV_GROUPS.map((g) => {
            const links = linksForGroup(g.id);
            if (links.length === 0) return null;
            return (
              <div key={g.id} className="px-3 py-4 border-b" style={{ borderColor: 'var(--space-border-default)' }}>
                <p className="text-[10px] font-bold uppercase tracking-wider mb-2 text-[var(--space-text-muted)]">{g.label}</p>
                <nav className="space-y-0.5">
                  {links.map((r) => {
                    const active = currentPath === r.path || currentPath.startsWith(r.path.replace(/:[^/]+/g, ''));
                    return (
                      <button
                        key={r.path}
                        type="button"
                        onClick={() => {
                          navigateTo(r.path);
                          setMobileOpen(false);
                        }}
                        className={`w-full text-left px-2 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          active
                            ? 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]'
                            : 'text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
                        }`}
                      >
                        {r.label}
                      </button>
                    );
                  })}
                </nav>
              </div>
            );
          })}
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
