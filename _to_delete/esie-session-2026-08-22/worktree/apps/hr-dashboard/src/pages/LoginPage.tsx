import { useLocation, Navigate } from 'react-router-dom';
import { isAuthenticated } from '../lib/auth';

interface LoginLocationState {
  from?: { pathname?: string };
}

/**
 * Scaffold-only login screen.
 *
 * The C1-11a scope is "login redirect works" — the actual login form is owned
 * by the existing relopass.com surface (frontend/src/pages/Login.tsx). For
 * now this page detects an existing token and bounces straight back to the
 * intended destination; otherwise it shows a single CTA that hands the user
 * off to the main login screen, preserving the original destination.
 */
export function LoginPage(): JSX.Element {
  const location = useLocation();
  const state = location.state as LoginLocationState | null;
  const target = state?.from?.pathname ?? '/cases';

  if (isAuthenticated()) {
    return <Navigate to={target} replace />;
  }

  // VITE_RELOPASS_LOGIN_URL is optional — defaults to the production login.
  // Local dev: set VITE_RELOPASS_LOGIN_URL=http://localhost:3000/login in .env.local.
  const loginHref =
    import.meta.env.VITE_API_URL?.replace(/\/api\/?$/, '') ??
    'https://relopass.com';
  const redirectAfter = encodeURIComponent(window.location.origin + target);
  const loginUrl = `${loginHref}/login?redirect=${redirectAfter}`;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-md">
        <h1 className="text-xl font-semibold text-foreground">Sign in to ReloPass HR</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The HR Dashboard uses your existing ReloPass account. We&rsquo;ll
          send you to the main sign-in page and bring you back here when
          you&rsquo;re done.
        </p>
        <a
          href={loginUrl}
          className="mt-6 inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
        >
          Continue to ReloPass sign-in
        </a>
      </div>
    </div>
  );
}
