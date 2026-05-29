import { ReactElement } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { isAuthenticated } from '../lib/auth';

/**
 * Wrap any route element that requires a logged-in HR user.
 *
 *   <Route element={<RequireAuth><AppShell /></RequireAuth>}>
 *     <Route path="/cases" element={<CasesPage />} />
 *     ...
 *   </Route>
 *
 * Unauthed users are bounced to /login with the original path tucked into
 * location state so the login flow can return them after a successful auth.
 */
export function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}
