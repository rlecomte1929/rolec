import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth } from './routes/RequireAuth';
import { AppShell } from './components/AppShell';
import { CasesPage } from './pages/CasesPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { ResolutionPage } from './pages/ResolutionPage';
import { PolicyPage } from './pages/PolicyPage';
import { LoginPage } from './pages/LoginPage';

/**
 * Route tree for the HR Dashboard.
 *
 * Auth model: every authed route is wrapped in <RequireAuth>; the wrapper
 * reads `relopass_token` from localStorage (same key used by the main
 * frontend) and bounces unauthed users to /login.
 *
 * The 5 routes called out by the Notion brief:
 *   /            → redirect to /cases
 *   /cases       → list (C1-11b lands the real UI)
 *   /cases/:id   → detail (C1-11c lands the doc panels + C1-11d the viewer)
 *   /resolution  → C1-12 surface
 *   /policy      → C1-15 surface
 *   /login       → public; redirects to the main relopass.com sign-in flow
 */
export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/cases" replace />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:id" element={<CaseDetailPage />} />
        <Route path="/resolution" element={<ResolutionPage />} />
        <Route path="/policy" element={<PolicyPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}
