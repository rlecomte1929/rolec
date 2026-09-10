import { generatePath } from 'react-router-dom';

export type RouteRole = 'PUBLIC' | 'HR' | 'EMPLOYEE' | 'ADMIN';

export const ROUTE_DEFS = {
  landing: { path: '/', roles: ['PUBLIC'] as RouteRole[] },
  platform: { path: '/platform', roles: ['PUBLIC'] as RouteRole[] },
  why: { path: '/why', roles: ['PUBLIC'] as RouteRole[] },
  howItWorks: { path: '/how-it-works', roles: ['PUBLIC'] as RouteRole[] },
  getStarted: { path: '/get-started', roles: ['PUBLIC'] as RouteRole[] },
  // [AIQ-1783] Paid-ad landing pages (ADS-3). Prerendered to static HTML at build
  // time — see frontend/scripts/prerender.mjs and PRERENDER_ROUTES there.
  mobilityTeams: { path: '/mobility-teams', roles: ['PUBLIC'] as RouteRole[] },
  relocationChecklist: { path: '/relocation-checklist', roles: ['PUBLIC'] as RouteRole[] },
  testDrive: { path: '/test-drive', roles: ['PUBLIC'] as RouteRole[] },
  testDriveSurvey: { path: '/test-drive/survey', roles: ['PUBLIC'] as RouteRole[] },
  security: { path: '/security', roles: ['PUBLIC'] as RouteRole[] },
  privacy: { path: '/privacy', roles: ['PUBLIC'] as RouteRole[] },
  compliance: { path: '/compliance', roles: ['PUBLIC'] as RouteRole[] },
  access: { path: '/access', roles: ['PUBLIC'] as RouteRole[] },
  auth: { path: '/auth', roles: ['PUBLIC'] as RouteRole[] },
  /** AIQ-920: /login alias for password managers, bookmarks, and email links —
   *  renders the same Auth screen (defaults to login mode) so a direct hit
   *  shows the form instead of bouncing to the marketing homepage. */
  login: { path: '/login', roles: ['PUBLIC'] as RouteRole[] },
  /** [AIQ-2189] Landing for a colleague-invite accept link. Public so a logged-out
   *  invitee sees the "create your account first" step instead of bouncing to a bare
   *  login screen; the redemption call itself is authenticated + email-matched. */
  inviteAccept: { path: '/invite/:token', roles: ['PUBLIC'] as RouteRole[] },
  employeeJourney: { path: '/employee/journey', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeDashboard: { path: '/employee/dashboard', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** First-login orientation, shown once per user (welcomeSeen). */
  employeeWelcome: { path: '/employee/welcome', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeQuoteRequest: { path: '/employee/quote-request', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee document vault — categorised uploads with expiry & deadline tracking. */
  employeeDocuments: { path: '/employee/documents', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Case-scoped document vault — same surface, opened for a specific case via :caseId. */
  employeeCaseDocuments: { path: '/employee/case/:caseId/documents', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Relocation task checklist (per assignment). */
  employeeCasePlan: { path: '/employee/case/:caseId/plan', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** [AIQ-976] Case-scoped intake wizard — opens the clicked case (vs the bare
   *  /employee/intake which resolves the primary case from context). */
  employeeCaseIntake: { path: '/employee/case/:caseId/intake', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Immigration intake flow (consent → OCR → interview). */
  employeeCaseImmigration: { path: '/employee/case/:caseId/immigration', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** [IMM-19] GDPR data-management screen (view / export / delete). */
  employeeCaseMyData: { path: '/employee/case/:caseId/my-data', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
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
  /** First-login orientation, shown once per user (welcomeSeen). */
  hrWelcome: { path: '/hr/welcome', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrAnalytics: { path: '/hr/analytics', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCommandCenter: { path: '/hr/command-center', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrRisk: { path: '/hr/risk', roles: ['HR', 'ADMIN'] as RouteRole[] },
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
  /** NAV-001: HR corridor immigration compliance (document checklist, risk flags,
   *  milestones, intake progress). Replaces the old 'Requirements'→/resources tab. */
  hrRequirements: { path: '/hr/requirements', roles: ['HR', 'ADMIN'] as RouteRole[] },
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
  // [AIQ-1285/H-05] Case-scoped services flow — the canonical paths. The legacy
  // /services/* paths above are kept as redirect routes (App.tsx) for back-compat
  // with deep links + last-visited entries. caseId === the assignment id.
  caseServices: { path: '/employee/case/:caseId/services/select', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseServicesQuestions: { path: '/employee/case/:caseId/services/questions', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseServicesRecommendations: { path: '/employee/case/:caseId/services/recommendations', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseServicesEstimate: { path: '/employee/case/:caseId/services/estimate', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseServicesRfqNew: { path: '/employee/case/:caseId/services/rfq/new', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseServicesConclusion: { path: '/employee/case/:caseId/services/conclusion', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  quotesInbox: { path: '/quotes', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  quoteRfqDetail: { path: '/quotes/rfq/:rfqId', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  vendorInbox: { path: '/vendor/inbox', roles: ['ADMIN', 'EMPLOYEE', 'HR'] as RouteRole[] },
  vendorRfq: { path: '/vendor/rfq/:id', roles: ['ADMIN', 'EMPLOYEE', 'HR'] as RouteRole[] },
  messages: { path: '/messages', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  resources: { path: '/resources', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  caseResources: { path: '/cases/:caseId/resources', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrMessages: { path: '/hr/messages', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrResources: { path: '/hr/resources', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrVendorCuration: { path: '/hr/vendor-curation', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrProviderGrid: { path: '/hr/provider-grid', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** [NAV-SP-1] Service Providers — grouped surface with Dashboard / Vendor
   *  Management / Provider Status sub-tabs (?tab=). */
  hrServiceProviders: { path: '/hr/service-providers', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Employee relocation task checklist portal (AIQ-34-B). */
  employeeTaskPage: { path: '/employee/tasks', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrPolicy: { path: '/hr/policy', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeeHrPolicy: { path: '/employee/hr-policy', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  hrPolicyManagement: { path: '/hr/policy-management', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy Builder wizard (AIQ-37-B/C). */
  hrPolicyBuilder: { path: '/hr/settings/policy', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy exceptions inbox — HR review + approve/reject flow. */
  hrExceptions: { path: '/hr/exceptions', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** AI decisions audit (AI-002) — EU AI Act Art. 14(4)(c) human oversight log. */
  hrAiDecisions: { path: '/hr/ai-decisions', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Policy vs. Reality compliance heatmap + per-case analysis. */
  /** Aggregate policy utilisation: active-policy tile, compliance table, exception queue, category heatmap (P3-4). */
  hrPolicyDashboard: { path: '/hr/policy-dashboard', roles: ['HR', 'ADMIN'] as RouteRole[] },
  /** Employee rich profile & preferences editor — housing, spouse, children, pets, financial. */
  employeeRichProfile: { path: '/employee/profile', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee detailed intake wizard — 6-step move context, household builder, commute map. */
  employeeIntake: { path: '/employee/intake', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  employeePolicy: { path: '/employee/policy', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee grounded immigration Q&A (AIQ-843 answer engine + AIQ-856 verdict capture). */
  employeeImmigrationAssistant: { path: '/employee/immigration-assistant', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  /** Employee Benefit Comparison dashboard — KPI tiles + per-category coverage table (P3-2). */
  employeeBenefitsComparison: { path: '/employee/benefits', roles: ['EMPLOYEE', 'ADMIN'] as RouteRole[] },
  submissionCenter: { path: '/submission-center', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrCompanyProfile: { path: '/hr/company-profile', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployees: { path: '/hr/employees', roles: ['HR', 'ADMIN'] as RouteRole[] },
  hrEmployeeDetail: { path: '/hr/employees/:id', roles: ['HR', 'ADMIN'] as RouteRole[] },
  notificationSettings: { path: '/settings/notifications', roles: ['HR', 'EMPLOYEE', 'ADMIN'] as RouteRole[] },
  adminConsole: { path: '/admin', roles: ['ADMIN'] as RouteRole[] },
  adminCatalogQueue: { path: '/admin/catalog-queue', roles: ['ADMIN'] as RouteRole[] },
  // Country requirement catalog — the review surface for what employees, HR and the public
  // corridor endpoint are served. Declared here (rather than only in the legacy src/routes.ts)
  // so it carries the ADMIN guard like its siblings and can be linked from the sidebar; it was
  // reachable only by typing the URL, which is why content shipped unreviewed.
  adminCountries: { path: '/admin/countries', roles: ['ADMIN'] as RouteRole[] },
  adminCountryDetail: { path: '/admin/countries/:countryCode', roles: ['ADMIN'] as RouteRole[] },
  adminCoverage: { path: '/admin/coverage', roles: ['ADMIN'] as RouteRole[] },
  adminRequirementFacts: { path: '/admin/requirement-facts', roles: ['ADMIN'] as RouteRole[] },
  adminResearchRequests: { path: '/admin/research-requests', roles: ['ADMIN'] as RouteRole[] },
  adminCompanies: { path: '/admin/companies', roles: ['ADMIN'] as RouteRole[] },
  adminPeople: { path: '/admin/people', roles: ['ADMIN'] as RouteRole[] },
  adminAssignments: { path: '/admin/assignments', roles: ['ADMIN'] as RouteRole[] },
  adminPolicies: { path: '/admin/policies', roles: ['ADMIN'] as RouteRole[] },
  adminSuppliers: { path: '/admin/suppliers', roles: ['ADMIN'] as RouteRole[] },
  adminSuppliersRegistry: { path: '/admin/suppliers/registry', roles: ['ADMIN'] as RouteRole[] },
  adminVettingQueue: { path: '/admin/vetting-queue', roles: ['ADMIN'] as RouteRole[] },
  adminContentReview: { path: '/admin/content-review', roles: ['ADMIN'] as RouteRole[] },
  adminCandidateBeam: { path: '/admin/candidate-beam', roles: ['ADMIN'] as RouteRole[] },
  adminSupplierSubmissions: { path: '/admin/supplier-submissions', roles: ['ADMIN'] as RouteRole[] },
  adminPrompts: { path: '/admin/prompts', roles: ['ADMIN'] as RouteRole[] },
  adminRagQuality: { path: '/admin/rag-quality', roles: ['ADMIN'] as RouteRole[] },
  adminAiUnitEconomics: { path: '/admin/ai-unit-economics', roles: ['ADMIN'] as RouteRole[] },
  adminAutopilotMetrics: { path: '/admin/autopilot-metrics', roles: ['ADMIN'] as RouteRole[] },
  adminDsar: { path: '/admin/data-rights', roles: ['ADMIN'] as RouteRole[] },
  adminPolicyVersions: { path: '/admin/policy-versions', roles: ['ADMIN'] as RouteRole[] },
  adminFeatureFlags: { path: '/admin/feature-flags', roles: ['ADMIN'] as RouteRole[] },
  adminPermissions: { path: '/admin/permissions', roles: ['ADMIN'] as RouteRole[] },
  adminExecutive: { path: '/admin/executive', roles: ['ADMIN'] as RouteRole[] },
  adminMissionControl: { path: '/admin/mission-control', roles: ['ADMIN'] as RouteRole[] },
  adminAiControls: { path: '/admin/ai-controls', roles: ['ADMIN'] as RouteRole[] },
  adminProspects: { path: '/admin/prospects', roles: ['ADMIN'] as RouteRole[] },
  adminMarketingAnalytics: { path: '/admin/marketing-analytics', roles: ['ADMIN'] as RouteRole[] },
  adminLeads: { path: '/admin/leads', roles: ['ADMIN'] as RouteRole[] },
  adminMessages: { path: '/admin/messages', roles: ['ADMIN'] as RouteRole[] },
  adminResources: { path: '/admin/resources', roles: ['ADMIN'] as RouteRole[] },
  adminResearch: { path: '/admin/research', roles: ['ADMIN'] as RouteRole[] },
  adminUsers: { path: '/admin/users', roles: ['ADMIN'] as RouteRole[] },
  adminRelocations: { path: '/admin/relocations', roles: ['ADMIN'] as RouteRole[] },
  adminSupport: { path: '/admin/support', roles: ['ADMIN'] as RouteRole[] },
  adminErrors: { path: '/admin/errors', roles: ['ADMIN'] as RouteRole[] },
  // AIQ-1437: ops alias for the existing error dashboard (same AdminErrors page).
  adminOpsErrors: { path: '/admin/ops/errors', roles: ['ADMIN'] as RouteRole[] },
  adminFeedback: { path: '/admin/feedback', roles: ['ADMIN'] as RouteRole[] },
  adminTestDrive: { path: '/admin/test-drive', roles: ['ADMIN'] as RouteRole[] },
  adminAdmins: { path: '/admin/admins', roles: ['ADMIN'] as RouteRole[] },
  adminAuditLog: { path: '/admin/audit-log', roles: ['ADMIN'] as RouteRole[] },
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
  adminSourceMonitor: { path: '/admin/source-monitor', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessChanges: { path: '/admin/freshness/changes', roles: ['ADMIN'] as RouteRole[] },
  adminFreshnessStaleContent: { path: '/admin/freshness/stale-content', roles: ['ADMIN'] as RouteRole[] },
  adminSourceChangeReviews: { path: '/admin/source-change-reviews', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlSchedules: { path: '/admin/crawl/schedules', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlJobRuns: { path: '/admin/crawl/job-runs', roles: ['ADMIN'] as RouteRole[] },
  adminCrawlJobRunDetail: { path: '/admin/crawl/job-runs/:id', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueue: { path: '/admin/review-queue', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueueDetail: { path: '/admin/review-queue/:id', roles: ['ADMIN'] as RouteRole[] },
  adminReviewQueueWorkload: { path: '/admin/review-queue/workload', roles: ['ADMIN'] as RouteRole[] },
  adminOps: { path: '/admin/ops', roles: ['ADMIN'] as RouteRole[] },
  adminOpsSla: { path: '/admin/ops/sla', roles: ['ADMIN'] as RouteRole[] },
  adminOpsQueue: { path: '/admin/ops/queue', roles: ['ADMIN'] as RouteRole[] },
  adminWorkflowFunnel: { path: '/admin/workflow/funnel', roles: ['ADMIN'] as RouteRole[] },
  adminAiQuestions: { path: '/admin/ai/questions', roles: ['ADMIN'] as RouteRole[] },
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
  // [AIQ-598] Corrections trend dashboard (per week, per reason / per agent)
  adminCorrectionsTrends: { path: '/admin/corrections/trends', roles: ['ADMIN'] as RouteRole[] },
  /** External provider portal — authenticated via magic-link JWT, no ReloPass account needed */
  providerPortal: { path: '/provider/portal', roles: ['PUBLIC'] as RouteRole[] },
  // AIQ-1521 — supplier answers an RFQ by magic link. PUBLIC by design: a moving company will
  // not create an account to give us a price.
  supplierQuote: { path: '/supplier/quote', roles: ['PUBLIC'] as RouteRole[] },
  // Counsel attestation reviewer view. PUBLIC by design and intentionally OUTSIDE the auth
  // guard: the reader is a lawyer at another firm with no ReloPass account, and the token in
  // the URL is the only credential. The backend returns an identical 404 for unknown,
  // expired and not-yet-sent tokens, so the route itself leaks nothing.
  attestationReview: { path: '/attest/:token', roles: ['PUBLIC'] as RouteRole[] },
  /** Admin → counsel attestations: request a corridor review, track it, promote the result. */
  adminAttestations: { path: '/admin/attestations', roles: ['ADMIN'] as RouteRole[] },
  /** [AIQ-633] Specialist review — admin reviews AI-generated roadmap steps per case */
  adminSpecialistReview: { path: '/admin/specialist-review/:case_id', roles: ['ADMIN'] as RouteRole[] },
  /** Auth Page Design — live-tune the /auth page's GlobeNetwork canvas (platform-wide, admin-only). */
  adminAuthPageDesign: { path: '/admin/auth-page-design', roles: ['ADMIN'] as RouteRole[] },
  /** LinkedIn Outreach CRM — admin-only prospect management and message drafting. */
  adminOutreach: { path: '/admin/outreach', roles: ['ADMIN'] as RouteRole[] },
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
