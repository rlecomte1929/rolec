import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import { clearAuthToken } from '../lib/auth';

const NAV = [
  { to: '/cases', label: 'Cases' },
  { to: '/resolution', label: 'Resolution' },
  { to: '/policy', label: 'Policy' },
];

/**
 * Persistent chrome for the authed dashboard — top bar with brand + nav, main
 * outlet below. Styling stays token-only: nothing references hardcoded colors
 * or spacing values.
 */
export function AppShell(): JSX.Element {
  const navigate = useNavigate();

  const handleSignOut = (): void => {
    clearAuthToken();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <NavLink
              to="/cases"
              className="text-lg font-semibold tracking-tight text-primary"
            >
              ReloPass HR
            </NavLink>
            <nav aria-label="Primary" className="flex items-center gap-1">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      'hover:bg-muted',
                      isActive
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className={cn(
              'rounded-md border border-border px-3 py-2 text-sm font-medium',
              'text-muted-foreground hover:bg-muted hover:text-foreground',
              'transition-colors',
            )}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto w-full max-w-7xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
