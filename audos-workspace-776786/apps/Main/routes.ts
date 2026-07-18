/**
 * Route registry for ReloPass Main — hash-based navigation replaces react-router-dom.
 * Paths mirror the imported SPA inventory from .audos-import validation.
 */

export type RouteKind =
  | 'landing'
  | 'public'
  | 'demo-case-command'
  | 'demo-move-roadmaps'
  | 'unavailable';

export interface RouteDef {
  path: string;
  name: string;
  label: string;
  group: 'public' | 'employee' | 'hr' | 'admin' | 'vendor' | 'other';
  kind: RouteKind;
  /** public page content key */
  publicKey?: string;
  unavailableReason?: string;
  unmappableId?: string;
}

export const ROUTES: RouteDef[] = [
  { path: '/', name: 'landing', label: 'Home', group: 'public', kind: 'landing' },
  { path: '/platform', name: 'platform', label: 'Platform', group: 'public', kind: 'public', publicKey: 'platform' },
  { path: '/why', name: 'why', label: 'Why ReloPass', group: 'public', kind: 'public', publicKey: 'why' },
  { path: '/why-relopass', name: 'whyRelopassAlias', label: 'Why ReloPass', group: 'public', kind: 'public', publicKey: 'why' },
  { path: '/how-it-works', name: 'howItWorks', label: 'How it works', group: 'public', kind: 'public', publicKey: 'howItWorks' },
  { path: '/get-started', name: 'getStarted', label: 'Get started', group: 'public', kind: 'public', publicKey: 'getStarted' },
  { path: '/test-drive', name: 'testDrive', label: 'Test drive', group: 'public', kind: 'unavailable', unavailableReason: 'Test drive provisioning requires server-functions and WorkspaceDB tables that are not yet registered in this draft.', unmappableId: 'TestDriveAnonymousSession' },
  { path: '/test-drive/survey', name: 'testDriveSurvey', label: 'Test drive survey', group: 'public', kind: 'unavailable', unavailableReason: 'Test drive survey persistence requires the FastAPI backend and Supabase session bridge.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/security', name: 'security', label: 'Security', group: 'public', kind: 'public', publicKey: 'security' },
  { path: '/privacy', name: 'privacy', label: 'Privacy', group: 'public', kind: 'public', publicKey: 'privacy' },
  { path: '/compliance', name: 'compliance', label: 'Compliance', group: 'public', kind: 'public', publicKey: 'compliance' },
  { path: '/access', name: 'access', label: 'Access', group: 'public', kind: 'public', publicKey: 'access' },
  { path: '/auth', name: 'auth', label: 'Sign in', group: 'public', kind: 'public', publicKey: 'auth' },
  { path: '/login', name: 'login', label: 'Sign in', group: 'public', kind: 'public', publicKey: 'auth' },
  { path: '/provider/portal', name: 'providerPortal', label: 'Provider portal', group: 'other', kind: 'unavailable', unavailableReason: 'Magic-link provider portal requires permalink-pages and JWT server-functions (mapped but not registered yet).', unmappableId: 'MagicLinkProviderPortal' },
  { path: '/supplier/quote', name: 'supplierQuote', label: 'Supplier quote', group: 'other', kind: 'unavailable', unavailableReason: 'Supplier RFQ magic links require permalink-pages + server-functions.', unmappableId: 'MagicLinkSupplierQuote' },
  { path: '/design-preview', name: 'designPreview', label: 'Design preview', group: 'other', kind: 'unavailable', unavailableReason: 'Design preview iframe route is a developer-only surface from the Vite app.', unmappableId: 'ReactRouterSPA' },
  { path: '/employee/dashboard', name: 'employeeDashboard', label: 'Employee dashboard', group: 'employee', kind: 'demo-move-roadmaps' },
  { path: '/employee/intake', name: 'employeeIntake', label: 'Intake wizard', group: 'employee', kind: 'unavailable', unavailableReason: 'Intake wizard uses react-hook-form, zod, and Leaflet commute maps — not on the Audos CDN.', unmappableId: 'LeafletMaps' },
  { path: '/employee/case/:caseId/intake', name: 'employeeCaseIntake', label: 'Case intake', group: 'employee', kind: 'unavailable', unavailableReason: 'Case-scoped intake requires react-hook-form/zod and backend case APIs.', unmappableId: 'react-hook-form' },
  { path: '/employee/case/:caseId/roadmap', name: 'employeeCaseRoadmap', label: 'Relocation roadmap', group: 'employee', kind: 'demo-move-roadmaps' },
  { path: '/employee/case/:caseId/summary', name: 'employeeCaseSummary', label: 'Case summary', group: 'employee', kind: 'unavailable', unavailableReason: 'Live case summary requires server-functions + WorkspaceDB case tables.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/employee/case/:caseId/immigration', name: 'employeeCaseImmigration', label: 'Immigration', group: 'employee', kind: 'unavailable', unavailableReason: 'Immigration flows require document-analysis OCR pipelines and backend routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/employee/case/:caseId/dossier', name: 'employeeCaseDossier', label: 'Dossier', group: 'employee', kind: 'unavailable', unavailableReason: 'Form dossier editing uses react-pdf in-browser rendering.', unmappableId: 'ReactPDF' },
  { path: '/employee/case/:caseId/documents', name: 'employeeCaseDocuments', label: 'Documents', group: 'employee', kind: 'unavailable', unavailableReason: 'Document vault requires file-storage integration and case API endpoints.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/employee/case/:caseId/forms/:formId/edit', name: 'employeeCaseFormEditor', label: 'Form editor', group: 'employee', kind: 'unavailable', unavailableReason: 'PDF form editor depends on react-pdf.', unmappableId: 'ReactPDF' },
  { path: '/employee/immigration-assistant', name: 'employeeImmigrationAssistant', label: 'Immigration assistant', group: 'employee', kind: 'unavailable', unavailableReason: 'Immigration Q&A requires OpenAI server-functions registered against case context.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/employee/benefits', name: 'employeeBenefitsComparison', label: 'Benefits comparison', group: 'employee', kind: 'unavailable', unavailableReason: 'Benefit optimizer uses Python ML stack (scikit-learn/conjoint).', unmappableId: 'PythonMLStack' },
  { path: '/employee/tasks', name: 'employeeTaskPage', label: 'Tasks', group: 'employee', kind: 'unavailable', unavailableReason: 'Employee task portal requires live case task APIs and Supabase realtime.', unmappableId: 'SupabaseRealtime' },
  { path: '/employee/profile', name: 'employeeRichProfile', label: 'Profile', group: 'employee', kind: 'unavailable', unavailableReason: 'Rich employee profile requires WorkspaceDB profile tables and HRIS sync.', unmappableId: 'HRISIntegrations' },
  { path: '/employee/case/:caseId/services/select', name: 'caseServices', label: 'Services selection', group: 'employee', kind: 'unavailable', unavailableReason: 'Services flow requires ML supplier recommendations API.', unmappableId: 'GET /api/recommendations/*' },
  { path: '/employee/case/:caseId/services/questions', name: 'caseServicesQuestions', label: 'Services questions', group: 'employee', kind: 'unavailable', unavailableReason: 'Services questionnaire requires backend services routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/employee/case/:caseId/services/recommendations', name: 'caseServicesRecommendations', label: 'Recommendations', group: 'employee', kind: 'unavailable', unavailableReason: 'Supplier recommendations ML is unmappable on Audos.', unmappableId: 'GET /api/recommendations/*' },
  { path: '/employee/case/:caseId/services/estimate', name: 'caseServicesEstimate', label: 'Estimate', group: 'employee', kind: 'unavailable', unavailableReason: 'Cost estimates require backend pricing models.', unmappableId: 'PythonMLStack' },
  { path: '/employee/case/:caseId/services/rfq/new', name: 'caseServicesRfqNew', label: 'New RFQ', group: 'employee', kind: 'unavailable', unavailableReason: 'RFQ creation requires server-functions + Resend email.', unmappableId: 'ResendEmail' },
  { path: '/employee/case/:caseId/services/conclusion', name: 'caseServicesConclusion', label: 'Services conclusion', group: 'employee', kind: 'unavailable', unavailableReason: 'Services conclusion step requires persisted RFQ state.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/dashboard', name: 'hrDashboard', label: 'HR dashboard', group: 'hr', kind: 'demo-case-command' },
  { path: '/hr/command-center', name: 'hrCommandCenter', label: 'Mobility control center', group: 'hr', kind: 'demo-case-command' },
  { path: '/hr/risk', name: 'hrRisk', label: 'Risk dashboard', group: 'hr', kind: 'unavailable', unavailableReason: 'Risk analytics requires Python survival models (lifelines).', unmappableId: 'PythonMLStack' },
  { path: '/hr/analytics', name: 'hrAnalytics', label: 'HR analytics', group: 'hr', kind: 'unavailable', unavailableReason: 'HR analytics dashboards require TanStack Query and backend aggregates.', unmappableId: '@tanstack/react-query' },
  { path: '/hr/assignments/:id', name: 'hrAssignmentReview', label: 'Assignment review', group: 'hr', kind: 'unavailable', unavailableReason: 'Assignment review requires HR API endpoints and WorkspaceDB.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/cases/:caseId', name: 'hrCaseSummary', label: 'Case summary', group: 'hr', kind: 'demo-case-command' },
  { path: '/hr/cases/:caseId/estimate', name: 'hrCaseEstimate', label: 'Estimate review', group: 'hr', kind: 'unavailable', unavailableReason: 'Estimate review requires backend pricing/ML stack.', unmappableId: 'PythonMLStack' },
  { path: '/hr/policy', name: 'hrPolicy', label: 'Policy workspace', group: 'hr', kind: 'unavailable', unavailableReason: 'Policy RAG assistant requires OpenAI + file-storage server-functions.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/requirements', name: 'hrRequirements', label: 'Requirements', group: 'hr', kind: 'unavailable', unavailableReason: 'Requirements catalog requires shared requirement_items WorkspaceDB seed.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/compliance', name: 'hrComplianceIndex', label: 'Compliance', group: 'hr', kind: 'unavailable', unavailableReason: 'Compliance index requires backend compliance routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/compliance/:id', name: 'hrCompliance', label: 'Compliance detail', group: 'hr', kind: 'unavailable', unavailableReason: 'Compliance detail requires backend compliance routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/vendor-curation', name: 'hrVendorCuration', label: 'Vendor curation', group: 'hr', kind: 'unavailable', unavailableReason: 'Vendor curation requires supplier ML and web-scraping integrations.', unmappableId: 'GET /api/recommendations/*' },
  { path: '/hr/service-providers', name: 'hrServiceProviders', label: 'Service providers', group: 'hr', kind: 'unavailable', unavailableReason: 'Service provider directory requires WorkspaceDB suppliers table + APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/immigration/new', name: 'hrImmigrationCreate', label: 'Create immigration case', group: 'hr', kind: 'unavailable', unavailableReason: 'Immigration case creation requires document-analysis + backend.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/immigration/:immigrationCaseId', name: 'hrImmigrationCase', label: 'Immigration timeline', group: 'hr', kind: 'unavailable', unavailableReason: 'Immigration timeline requires backend immigration routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/ai-decisions', name: 'hrAiDecisions', label: 'AI audit log', group: 'hr', kind: 'unavailable', unavailableReason: 'AI decision audit requires Langfuse/LangSmith tracing substrate.', unmappableId: 'Langfuse' },
  { path: '/hr/policy-vs-reality', name: 'hrPolicyReality', label: 'Policy vs reality', group: 'hr', kind: 'unavailable', unavailableReason: 'Policy vs reality analytics requires backend ML pipelines.', unmappableId: 'PythonMLStack' },
  { path: '/hr/policy-dashboard', name: 'hrPolicyDashboard', label: 'Policy dashboard', group: 'hr', kind: 'unavailable', unavailableReason: 'Policy dashboard requires policy knowledge snapshots in WorkspaceDB.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/hr/company-profile', name: 'hrCompanyProfile', label: 'Company profile', group: 'hr', kind: 'unavailable', unavailableReason: 'Company profile v2 requires WorkspaceDB companies + HRIS sync.', unmappableId: 'HRISIntegrations' },
  { path: '/hr/employees', name: 'hrEmployees', label: 'Employees', group: 'hr', kind: 'unavailable', unavailableReason: 'Employee directory requires BambooHR/Personio integrations or manual CRM import.', unmappableId: 'HRISIntegrations' },
  { path: '/hr/employees/:id', name: 'hrEmployeeDetail', label: 'Employee detail', group: 'hr', kind: 'unavailable', unavailableReason: 'Employee detail requires HRIS-linked profile data.', unmappableId: 'HRISIntegrations' },
  { path: '/hr/messages', name: 'hrMessages', label: 'HR inbox', group: 'hr', kind: 'unavailable', unavailableReason: 'Unified inbox uses Supabase Realtime and TanStack Query.', unmappableId: 'SupabaseRealtime' },
  { path: '/hr/backlog', name: 'hrBacklog', label: 'HR backlog', group: 'hr', kind: 'unavailable', unavailableReason: 'HR backlog requires backend task aggregation APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/messages', name: 'messages', label: 'Messages', group: 'other', kind: 'unavailable', unavailableReason: 'Unified inbox requires Supabase Realtime WebSocket client.', unmappableId: 'SupabaseRealtime' },
  { path: '/resources', name: 'resources', label: 'Resources', group: 'other', kind: 'unavailable', unavailableReason: 'Resources CMS reader requires admin content APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/cases/:caseId/resources', name: 'caseResources', label: 'Case resources', group: 'other', kind: 'unavailable', unavailableReason: 'Case-scoped resources require backend CMS endpoints.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/quotes', name: 'quotesInbox', label: 'Quotes inbox', group: 'other', kind: 'unavailable', unavailableReason: 'Quotes inbox requires RFQ/quote WorkspaceDB tables + APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/quotes/rfq/:rfqId', name: 'quoteRfqDetail', label: 'RFQ detail', group: 'other', kind: 'unavailable', unavailableReason: 'RFQ detail requires server-functions quote routers.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/vendor/inbox', name: 'vendorInbox', label: 'Vendor inbox', group: 'vendor', kind: 'unavailable', unavailableReason: 'Vendor inbox requires supplier portal APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/vendor/rfq/:id', name: 'vendorRfq', label: 'Vendor RFQ', group: 'vendor', kind: 'unavailable', unavailableReason: 'Vendor RFQ response flow requires magic-link auth + APIs.', unmappableId: 'MagicLinkSupplierQuote' },
  { path: '/settings/notifications', name: 'notificationSettings', label: 'Notification settings', group: 'other', kind: 'unavailable', unavailableReason: 'Notification preferences require Resend/task-scheduler email setup.', unmappableId: 'ResendEmail' },
  { path: '/admin', name: 'adminConsole', label: 'Admin overview', group: 'admin', kind: 'unavailable', unavailableReason: 'Admin console requires 40+ backend admin routers and WorkspaceDB tables.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/companies', name: 'adminCompanies', label: 'Companies', group: 'admin', kind: 'unavailable', unavailableReason: 'Companies admin requires WorkspaceDB + admin APIs.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/people', name: 'adminPeople', label: 'People', group: 'admin', kind: 'unavailable', unavailableReason: 'People admin requires Supabase auth stack.', unmappableId: 'SupabaseAuthStack' },
  { path: '/admin/assignments', name: 'adminAssignments', label: 'Assignments', group: 'admin', kind: 'unavailable', unavailableReason: 'Assignments admin requires backend CRUD.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/policies', name: 'adminPolicies', label: 'Policies', group: 'admin', kind: 'unavailable', unavailableReason: 'Policy admin requires document ingestion pipelines.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/suppliers', name: 'adminSuppliers', label: 'Suppliers', group: 'admin', kind: 'unavailable', unavailableReason: 'Supplier admin requires WorkspaceDB suppliers catalog.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/review-queue', name: 'adminReviewQueue', label: 'Review queue', group: 'admin', kind: 'unavailable', unavailableReason: 'Specialist review workflow is gated on Postgres tables and internal APIs.', unmappableId: 'SpecialistReviewWorkflow' },
  { path: '/admin/freshness', name: 'adminFreshness', label: 'Content freshness', group: 'admin', kind: 'unavailable', unavailableReason: 'Content freshness crawler requires pg_cron and crawl pipelines.', unmappableId: 'ContentFreshnessCrawler' },
  { path: '/admin/form-templates', name: 'adminFormTemplates', label: 'Form templates', group: 'admin', kind: 'unavailable', unavailableReason: 'Form templates admin requires react-pdf and backend template store.', unmappableId: 'ReactPDF' },
  { path: '/admin/test-drive', name: 'adminTestDrive', label: 'Test drive admin', group: 'admin', kind: 'unavailable', unavailableReason: 'Test drive admin requires provisioning server-functions.', unmappableId: 'TestDriveAnonymousSession' },
  { path: '/admin/outreach', name: 'adminOutreach', label: 'Outreach CRM', group: 'admin', kind: 'unavailable', unavailableReason: 'Outreach CRM requires backend lead pipelines.', unmappableId: 'FullPythonFastAPIBackend' },
  { path: '/admin/ops', name: 'adminOps', label: 'Ops analytics', group: 'admin', kind: 'unavailable', unavailableReason: 'Ops analytics requires PostHog/Sentry integrations.', unmappableId: 'Sentry' },
  { path: '/admin/specialist-review/:case_id', name: 'adminSpecialistReview', label: 'Specialist review', group: 'admin', kind: 'unavailable', unavailableReason: 'Specialist review gating requires human-in-the-loop backend.', unmappableId: 'SpecialistReviewWorkflow' },
  { path: '/admin/countries', name: 'adminCountries', label: 'Countries', group: 'admin', kind: 'unavailable', unavailableReason: 'Country admin CMS requires backend destination intelligence APIs.', unmappableId: 'ContentFreshnessCrawler' },
  { path: '/admin/countries/:countryCode', name: 'adminCountryDetail', label: 'Country detail', group: 'admin', kind: 'unavailable', unavailableReason: 'Country detail CMS requires crawl/review pipelines.', unmappableId: 'ContentFreshnessCrawler' },
];

export interface ParsedRoute {
  def: RouteDef;
  params: Record<string, string>;
}

function matchPattern(pattern: string, path: string): Record<string, string> | null {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = path.split('/').filter(Boolean);
  if (patternParts.length !== pathParts.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i++) {
    const pp = patternParts[i];
    const vp = pathParts[i];
    if (pp.startsWith(':')) params[pp.slice(1)] = decodeURIComponent(vp);
    else if (pp !== vp) return null;
  }
  return params;
}

export function parseHashRoute(hash: string): ParsedRoute {
  const raw = hash.replace(/^#\/?/, '') || '/';
  const path = raw.startsWith('/') ? raw : `/${raw}`;
  const exact = ROUTES.find((r) => r.path === path);
  if (exact) return { def: exact, params: {} };
  for (const def of ROUTES) {
    if (!def.path.includes(':')) continue;
    const params = matchPattern(def.path, path);
    if (params) return { def, params };
  }
  return {
    def: {
      path,
      name: 'unknown',
      label: 'Unknown route',
      group: 'other',
      kind: 'unavailable',
      unavailableReason: `No native handler for "${path}". Deep links from the imported SPA are restructured as hash routes inside Main.`,
      unmappableId: 'ReactRouterSPA',
    },
    params: {},
  };
}

export function navigateTo(path: string) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  window.location.hash = normalized;
}

export function getDefaultRoute(): string {
  return '/hr/command-center';
}

export const NAV_GROUPS: { id: RouteDef['group']; label: string }[] = [
  { id: 'public', label: 'Marketing' },
  { id: 'employee', label: 'Employee' },
  { id: 'hr', label: 'HR / Mobility' },
  { id: 'admin', label: 'Admin' },
  { id: 'vendor', label: 'Vendor' },
  { id: 'other', label: 'Other' },
];
