import { generatePath } from 'react-router-dom';

export type RouteRole = 'PUBLIC' | 'HR' | 'EMPLOYEE' | 'ADMIN';

export const ROUTE_DEFS = {
  landing: { path: '/', roles: ['PUBLIC'] as RouteRole[] },
  auth: { path: '/auth', roles: ['PUBLIC'] as RouteRole[] },
  employeeJourney: { path: '/employee/journey', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrDashboard: { path: '/hr/dashboard', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployeeDashboard: { path: '/hr/employee-dashboard', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCaseSummary: { path: '/hr/cases/:caseId', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrAssignmentReview: { path: '/hr/assignments/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrComplianceIndex: { path: '/hr/compliance', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCompliance: { path: '/hr/compliance/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrPackage: { path: '/hr/package/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  auditNavigation: { path: '/audit/navigation', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  providers: { path: '/providers', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  messages: { path: '/messages', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  resources: { path: '/resources', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrMessages: { path: '/hr/messages', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrResources: { path: '/hr/resources', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrPolicy: { path: '/hr/policy', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  submissionCenter: { path: '/submission-center', roles: ['HR', 'ADMIN'] as RouteRole[] },
};

export type RouteKey = keyof typeof ROUTE_DEFS;

export const buildRoute = (key: RouteKey, params?: Record<string, string>) =>
  generatePath(ROUTE_DEFS[key].path, params);

export const routeKeys = Object.keys(ROUTE_DEFS) as RouteKey[];
