# Block 5: Auth + Role Sourcing

## Where role is sourced

- **Storage**: `localStorage` via `relopass_role` key
- **Helper**: `getAuthItem('relopass_role')` from `frontend/src/utils/demo.ts`
- **Set on**: Login (`useAuth` in `hooks/useAuth.ts`), SwitchUserModal
- **Values**: `'HR' | 'EMPLOYEE' | 'ADMIN'`
- **Nav visibility**: `AppShell` uses `role === 'HR' || role === 'ADMIN'` for HR nav, `role === 'EMPLOYEE' || role === 'ADMIN'` for employee nav
- **Route defs**: `ROUTE_DEFS` in `navigation/routes.ts` - each route has `roles: RouteRole[]`
- **Supabase JWT**: Used for RPC/PostgREST; `VITE_SUPABASE_ACCESS_TOKEN` fallback when no session (dev)

## RBAC for Block 5

- HR pages: require `relopass_role === 'HR' || 'ADMIN'` (client) + RLS on Supabase (server)
- Employee: require `relopass_role === 'EMPLOYEE' || 'ADMIN'` (client) + RLS
- No transition RPCs from UI
