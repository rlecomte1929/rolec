import { generatePath } from 'react-router-dom';

export type RouteRole = 'PUBLIC' | 'HR' | 'EMPLOYEE' | 'ADMIN';

export const ROUTE_DEFS = {
  landing: { path: '/', roles: ['PUBLIC'] as RouteRole[] },
  platform: { path: '/platform', roles: ['PUBLIC'] as RouteRole[] },
  why: { path: '/why', roles: ['PUBLIC'] as RouteRole[] },
  howItWorks: { path: '/how-it-works', roles: ['PUBLIC'] as RouteRole[] },
  getStarted: { path: '/get-started', roles: ['PUBLIC'] as RouteRole[] },
  security: { path: '/security', roles: ['PUBLIC'] as RouteRole[] },
  privacy: { path: '/privacy', roles: ['PUBLIC'] as RouteRole[] },
  access: { path: '/access', roles: ['PUBLIC'] as RouteRole[] },
  auth: { path: '/auth', roles: ['PUBLIC'] as RouteRole[] },
  employeeJourney: { path: '/employee/journey', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeDashboard: { path: '/employee/dashboard', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeQuoteRequest: { path: '/employee/quote-request', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee document vault — categorised uploads with expiry & deadline tracking. */
  employeeDocuments: { path: '/employee/documents', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Relocation task checklist (per assignment). */
  employeeCasePlan: { path: '/employee/case/:caseId/plan', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Immigration intake flow (consent → OCR → interview). */
  employeeCaseImmigration: { path: '/employee/case/:caseId/immigration', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  // [P1-5] Dossier & Forms list view
  employeeCaseDossier: { path: '/employee/case/:caseId/dossier', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** [P3-4] Dossier Builder — 3-step wizard: select, arrange, download. */
  employeeCaseDossierBuild: { path: '/employee/case/:caseId/dossier/build', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  // [P1-6] Roadmap page with doc-count chips per step
  employeeCaseRoadmap: { path: '/employee/case/:caseId/roadmap', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  // [MVG-6B] Employee immigration document checklist (added by commit 2757862).
  // HR role added so HR users can view the checklist from the immigration timeline "View employee checklist" button.
  employeeCaseImmigrationChecklist: { path: '/employee/case/:caseId/immigration/checklist', roles: ['EMPLOYEE', 'HR', 'ADMIN'] as RouteRole[] },
  // [P2-3] Form Editor — per-form field editing
  employeeCaseFormEditor: { path: '/employee/case/:caseId/forms/:formId/edit', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrDashboard: { path: '/hr/dashboard', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrAnalytics: { path: '/hr/analytics', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCommandCenter: { path: '/hr/command-center', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCommandCenterCase: { path: '/hr/command-center/cases/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployeeDashboard: { path: '/hr/employee-dashboard', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCaseSummary: { path: '/hr/cases/:caseId', roles: ['HR', 'ADMIN'] as RouteRole[] },
  // [P4-2] HR Operations dossier panel — full form list with comments, flags, history
  hrCaseDossier: { path: '/hr/cases/:caseId/dossier', roles: ['HR', 'ADMIN'] as RouteRole[] },
  // [T1.5/AIQ-280] HR Estimate Review — per-category policy caps view
  hrCaseEstimate: { path: '/hr/cases/:caseId/estimate', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrReview: { path: '/hr/review', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrReviewCase: { path: '/hr/review/case/:caseId', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrAssignmentReview: { path: '/hr/assignments/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrComplianceIndex: { path: '/hr/compliance', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrErasureRequests: { path: '/hr/compliance/erasure-requests', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCompliance: { path: '/hr/compliance/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrPackage: { path: '/hr/package/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  // [MVG-6A] HR immigration case create form + timeline (added by commit 2757862;
  // route keys were missing from this registry, breaking the TS build).
  hrImmigrationCreate: { path: '/hr/immigration/new', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrImmigrationCase: { path: '/hr/immigration/:immigrationCaseId', roles: ['HR', 'ADMIN'] as RouteRole[] },
  auditNavigation: { path: '/audit/navigation', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  providers: { path: '/providers', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  services: { path: '/services', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  servicesQuestions: { path: '/services/questions', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  servicesRecommendations: { path: '/services/recommendations', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  servicesEstimate: { path: '/services/estimate', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  servicesRfqNew: { path: '/services/rfq/new', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  servicesConclusion: { path: '/services/conclusion', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  quotesInbox: { path: '/quotes', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  quoteRfqDetail: { path: '/quotes/rfq/:rfqId', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  vendorInbox: { path: '/vendor/inbox', roles: ['ADMIN', 'EMPLOYEE', 'HR'] as RouteRole[] },
  vendorRfq: { path: '/vendor/rfq/:id', roles: ['ADMIN', 'EMPLOYEE', 'HR'] as RouteRole[] },
  messages: { path: '/messages', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  resources: { path: '/resources', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseResources: { path: '/cases/:caseId/resources', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrMessages: { path: '/hr/messages', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrResources: { path: '/hr/resources', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrPreferredSuppliers: { path: '/hr/preferred-suppliers', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrVendorCuration: { path: '/hr/vendor-curation', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrProviderGrid: { path: '/hr/provider-grid', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Employee relocation task checklist portal (AIQ-34-B). */
  employeeTaskPage: { path: '/employee/tasks', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrPolicy: { path: '/hr/policy', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeHrPolicy: { path: '/employee/hr-policy', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrPolicyManagement: { path: '/hr/policy-management', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy Builder wizard (AIQ-37-B/C). */
  hrPolicyBuilder: { path: '/hr/settings/policy', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** [P2-6] HR validation gate — review extracted policy values before publishing */
  hrPolicyBuilderReview: { path: '/hr/policy-builder/review', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** [P2-8] HR document management — upload history, status badges, version diffs */
  hrPolicyBuilderDocuments: { path: '/hr/policy-builder/documents', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy exceptions inbox — HR review + approve/reject flow. */
  hrExceptions: { path: '/hr/exceptions', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** AI decisions audit (AI-002) — EU AI Act Art. 14(4)(c) human oversight log. */
  hrAiDecisions: { path: '/hr/ai-decisions', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy vs. Reality compliance heatmap + per-case analysis. */
  hrPolicyReality: { path: '/hr/policy-vs-reality', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** AI Requirements Discovery Engine — corridor requirement graph + timeline + source audit. */
  hrDiscovery: { path: '/hr/discovery', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Employee rich profile & preferences editor — housing, spouse, children, pets, financial. */
  employeeRichProfile: { path: '/employee/profile', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee detailed intake wizard — 6-step move context, household builder, commute map. */
  employeeIntake: { path: '/employee/intake', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeePolicy: { path: '/employee/policy', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  submissionCenter: { path: '/submission-center', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCompanyProfile: { path: '/hr/company-profile', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployees: { path: '/hr/employees', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployeeDetail: { path: '/hr/employees/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  notificationSettings: { path: '/settings/notifications', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  adminConsole: { path: '/admin', roles: ['ADMIN'] as RouteRole[] },
  adminOverview: { path: '/admin', roles: ['ADMIN'] as RouteRole[] },
  adminCatalogQueue: { path: '/admin/catalog-queue', roles: ['ADMIN'] as RouteRole[] },
  adminCompanies: { path: '/admin/companies', roles: ['ADMIN'] as RouteRole[] },
  adminPeople: { path: '/admin/people', roles: ['ADMIN'] as RouteRole[] },
  adminAssignments: { path: '/admin/assignments', roles: ['ADMIN'] as RouteRole[] },
  adminPolicies: { path: '/admin/policies', roles: ['ADMIN'] as RouteRole[] },
  adminSuppliers: { path: '/admin/suppliers', roles: ['ADMIN'] as RouteRole[] },
  adminPrompts: { path: '/admin/prompts', roles: ['ADMIN'] as RouteRole[] },
  adminProspects: { path: '/admin/prospects', roles: ['ADMIN'] as RouteRole[] },
  adminMessages: { path: '/admin/messages', roles: ['ADMIN'] as RouteRole[] },
  adminResources: { path: '/admin/resources', roles: ['ADMIN'] as RouteRole[] },
  adminResearch: { path: '/admin/research', roles: ['ADMIN'] as RouteRole[] },
  adminUsers: { path: '/admin/users', roles: ['ADMIN'] as RouteRole[] },
  adminRelocations: { path: '/admin/relocations', roles: ['ADMIN'] as RouteRole[] },
  adminSupport: { path: '/admin/support', roles: ['ADMIN'] as RouteRole[] },
  adminErrors: { path: '/admin/errors', roles: ['ADMIN'] as RouteRole[] },
  adminFeedback: { path: '/admin/feedback', roles: ['ADMIN'] as RouteRole[] },
  adminSuppliersNew: { path: '/admin/suppliers/new', roles: ['ADMIN'] as RouteRole[] },
  adminSuppliersDetail: { path: '/admin/suppliers/:id', roles: ['ADMIN'] as RouteRole[] },
  adminResourcesNew: { path: '/admin/resources/new', roles: ['ADMIN'] as RouteRole[] },
  adminResourcesEdit: { path: '/admin/resources/:id', roles: ['ADMIN'] as RouteRole[] },
  adminEvents: { path: '/admin/events', roles: ['ADMIN'] as RouteRole[] },
  adminEventsEdit: { path: '/admin/events/:id', roles: ['ADMIN'] as RouteRole[] },
  adminCategories: { path: '/admin/resources/categories', roles: ['ADMIN'] as RouteRole[] },
  adminTags: { path: '/admin/resources/tags', roles: ['ADMIN'] as RouteRole[] },
  adminSources: { path: '/admin/resources/sources', roles: ['ADMIN'] as RouteRole[] },
  adminStagingDashboard: { path: '/admin/staging', roles: ['ADMIN'] as RouteRole[] },
  adminStagingResources: { path: '/admin/staging/resources', roles: ['ADMIN'] as RouteRole[] },
  adminStagingResourceDetail: { path: '/admin/staging/resources/:id', roles: ['ADMIN'] as RouteRole[] },
  adminStagingEvents: { path: '/admin/staging/events', roles: ['ADMIN'] as RouteRole[] },
  adminStagingEventDetail: { path: '/admin/staging/events/:id', roles: ['ADMIN'] as RouteRole[] },
  adminFreshness: { path: '/admin/freshness', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessCountries: { path: '/admin/freshness/countries', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessCities: { path: '/admin/freshness/cities', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessSources: { path: '/admin/freshness/sources', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessChanges: { path: '/admin/freshness/changes', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessStaleContent: { path: '/admin/freshness/stale-content', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlSchedules: { path: '/admin/crawl/schedules', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlJobRuns: { path: '/admin/crawl/job-runs', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlJobRunDetail: { path: '/admin/crawl/job-runs/:id', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueue: { path: '/admin/review-queue', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueueDetail: { path: '/admin/review-queue/:id', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueueWorkload: { path: '/admin/review-queue/workload', roles: ['ADMIN'] as RouteRole[] },
  adminOps: { path: '/admin/ops', roles: ['ADMIN'] as RouteRole[] },
  adminOpsSla: { path: '/admin/ops/sla', roles: ['ADMIN'] as RouteRole[] },
  adminOpsQueue: { path: '/admin/ops/queue', roles: ['ADMIN'] as RouteRole[] },
  adminOpsReviewers: { path: '/admin/ops/reviewers', roles: ['ADMIN'] as RouteRole[] },
  adminOpsDestinations: { path: '/admin/ops/destinations', roles: ['ADMIN'] as RouteRole[] },
  adminOpsNotifications: { path: '/admin/ops/notifications', roles: ['ADMIN'] as RouteRole[] },
  adminMobilityCases: { path: '/admin/mobility/cases', roles: ['ADMIN'] as RouteRole[] },
  adminMobilityCaseInspect: { path: '/admin/mobility/cases/:caseId', roles: ['ADMIN'] as RouteRole[] },
  // [P1-2] Form Template Registry
  adminFormTemplates: { path: '/admin/form-templates', roles: ['ADMIN'] as RouteRole[] },
  adminFormTemplatesNew: { path: '/admin/form-templates/new', roles: ['ADMIN'] as RouteRole[] },
  adminFormTemplatesEdit: { path: '/admin/form-templates/:id', roles: ['ADMIN'] as RouteRole[] },
  // [P3-2] PDF coordinate mapper — must come before :id to avoid route ambiguity
  adminFormTemplatesMap: { path: '/admin/form-templates/:id/map', roles: ['ADMIN'] as RouteRole[] },
  // [PRODUCT-6E] A/B test experiment dashboard
  adminAbTests: { path: '/admin/ab-tests', roles: ['ADMIN'] as RouteRole[] },
  /** External provider portal — authenticated via magic-link JWT, no ReloPass account needed */
  providerPortal: { path: '/provider/portal', roles: ['PUBLIC'] as RouteRole[] },
  /** [AIQ-633] Specialist review — admin reviews AI-generated roadmap steps per case */
  adminSpecialistReview: { path: '/admin/specialist-review/:case_id', roles: ['ADMIN'] as RouteRole[] },
};

export type RouteKey = keyof typeof ROUTE_DEFS;

export const buildRoute = (key: RouteKey, params?: Record<string, string>) =>
  generatePath(ROUTE_DEFS[key].path, params);

/** In-app home for a stored role (used after login, logo link, and auth/landing redirects). */
export function homeRouteKeyForRole(role: string | null | undefined): RouteKey {
  const r = (role ?? '').trim().toUpperCase();
  if (r === 'EMPLOYEE') return 'employeeDashboard';
  if (r === 'ADMIN') return 'adminConsole';
  if (r === 'HR') return 'hrDashboard';
  return 'landing';
}

export const routeKeys = Object.keys(ROUTE_DEFS) as RouteKey[];
