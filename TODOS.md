# TODOS

## E4 - Do not show /hr/welcome to a company that already has cases (P2, M -> CC S)
Why: "Testing April" (30 cases) is still greeted with the setup welcome. AIQ-2321 softened the copy; the page itself is still wrong for them.
How: add `has_cases` (or a case count) to the login payload next to `welcome_seen` (backend/app/routers/auth.py, the /api/auth/login response) and seed it in `useAuth.setSession`; `useWelcomeRedirect` stays synchronous (AIQ-1701) and treats has_cases=true as seen. Alternative: the welcome page fetches once on mount and bounces (fail open). Decide with Romain.
Files: backend/app/routers/auth.py, frontend/src/hooks/useAuth.ts, frontend/src/hooks/useWelcomeRedirect.ts, tests.

## E9 - Fold the welcome into the HR home (P2, L -> CC M)
Blocked on AIQ-2177 (intent-based HR home). When the home exists, the welcome becomes a checklist panel on it with live completion state; exits collapse to one. Do not start before 2177 is decided.

## E10 - One home resolver (P3, S -> CC S)
`navigation/roleHome.ts:roleHomePath()` (used by NotFoundRedirect) and `navigation/routes.ts:homeRouteKeyForRole()` (login redirect, AppShell identity link, breadcrumb, HR welcome exits) already disagree for ADMIN (`adminOverview` vs `adminConsole`): a 404 and the header link send an admin to two different homes. Make `roleHomePath` delegate to `buildRoute(homeRouteKeyForRole(role))` and add one test asserting equality for HR/EMPLOYEE/ADMIN/unknown.
