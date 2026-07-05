import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppErrorBoundary } from './components/AppErrorBoundary';
import { ResilientRoute } from './components/ResilientRoute';
import { NavigationLogger } from './components/NavigationLogger';
import { ScrollToTop } from './components/ScrollToTop';
import { SelectedCaseProvider } from './contexts/SelectedCaseContext';
import { EmployeeAssignmentProvider } from './contexts/EmployeeAssignmentContext';
import { HrCompanyContextProvider } from './contexts/HrCompanyContext';
import { ServicesFlowProvider } from './features/services/ServicesFlowContext';
import { DemoBookingProvider } from './hooks/useDemoBooking';
import { BookDemoModal } from './components/marketing/BookDemoModal';
import { ROUTE_DEFS } from './navigation/routes';
import { Landing } from './pages/Landing';
import { PlatformPage } from './pages/public/PlatformPage';
import { HowItWorksPage } from './pages/public/HowItWorksPage';
import { GetStartedPage } from './pages/public/GetStartedPage';
import { TestDrivePage } from './pages/public/TestDrivePage';
import { TestDriveSurveyPage } from './pages/public/TestDriveSurveyPage';
import { CompliancePage } from './pages/public/CompliancePage';
import { WhyReloPassPage } from './pages/public/WhyReloPassPage';
import { AccessPage } from './pages/public/AccessPage';
import { SecurityPage } from './pages/public/SecurityPage';
import { PrivacyPage } from './pages/public/PrivacyPage';
import { Auth } from './pages/Auth';
import { RequireAdminRoute } from './features/admin/RequireAdminRoute';
import { AdminViewingCompanyProvider } from './features/admin/AdminViewingCompanyContext';
// V2Gate removed — all promoted flags now render V2 unconditionally
import { RequireEmployeeRoute } from './features/employee/RequireEmployeeRoute';
import { RequireHrRoute } from './features/hr/RequireHrRoute';
import { NotFoundRedirect } from './components/NotFoundRedirect';
import { ROUTES as WIZARD_ROUTES } from './routes';
import { NavigationAudit } from './pages/NavigationAudit';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { DebugAuth } from './pages/DebugAuth';
import { AssignmentDebugPage } from './pages/AssignmentDebugPage';
import { PerfPanel } from './components/PerfPanel';
import { FeatureFlagProvider } from './lib/feature-flags.tsx';

const Journey = lazy(() => import('./pages/Journey').then((module) => ({ default: module.Journey })));
const Dashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })));
const EmployeeJourney = lazy(() => import('./pages/EmployeeJourney').then((module) => ({ default: module.EmployeeJourney })));
const HrDashboard = lazy(() => import('./pages/HrDashboard').then((module) => ({ default: module.HrDashboard })));
const HrCaseSummary = lazy(() => import('./pages/HrCaseSummary').then((module) => ({ default: module.HrCaseSummary })));
const HrCaseEstimatePage = lazy(() => import('./pages/hr/HrCaseEstimatePage').then((module) => ({ default: module.HrCaseEstimatePage })));
const HrAssignmentReview = lazy(() => import('./pages/HrAssignmentReview').then((module) => ({ default: module.HrAssignmentReview })));
const HrComplianceCheck = lazy(() => import('./pages/HrComplianceCheck').then((module) => ({ default: module.HrComplianceCheck })));
const HrAssignmentPackageReview = lazy(() => import('./pages/HrAssignmentPackageReview').then((module) => ({ default: module.HrAssignmentPackageReview })));
const HrPreferredSuppliers = lazy(() => import('./pages/HrPreferredSuppliers').then((module) => ({ default: module.HrPreferredSuppliers })));
const HrVendorCuration = lazy(() => import('./pages/HrVendorCuration').then((module) => ({ default: module.HrVendorCuration })));
const HrServiceProvidersPage = lazy(() => import('./pages/HrServiceProvidersPage').then((module) => ({ default: module.HrServiceProvidersPage })));
const HrPolicy = lazy(() => import('./pages/HrPolicy').then((module) => ({ default: module.HrPolicy })));
const EmployeePolicyPage = lazy(() => import('./pages/employee/EmployeePolicyPage').then((module) => ({ default: module.EmployeePolicyPage })));
const ImmigrationAssistantPage = lazy(() => import('./pages/employee/ImmigrationAssistantPage').then((module) => ({ default: module.ImmigrationAssistantPage })));
const EmployeeBenefitComparisonPage = lazy(() => import('./pages/employee/EmployeeBenefitComparisonPage').then((module) => ({ default: module.EmployeeBenefitComparisonPage })));
// Legacy CaseWizardPage is no longer routed (staged unification C1) — its routes
// redirect to the canonical v2 intake. The component file stays dormant.
const LegacyWizardRedirect = lazy(() => import('./pages/employee/LegacyWizardRedirect').then((module) => ({ default: module.LegacyWizardRedirect })));
const CasePlanToRoadmapRedirect = lazy(() => import('./pages/employee/CasePlanToRoadmapRedirect').then((module) => ({ default: module.CasePlanToRoadmapRedirect })));
const EmployeeCaseSummary = lazy(() => import('./pages/employee/EmployeeCaseSummary').then((module) => ({ default: module.EmployeeCaseSummary })));
// [P1-5] Dossier & Forms list view
const EmployeeDossierPage = lazy(() => import('./pages/employee/EmployeeDossierPage').then((module) => ({ default: module.EmployeeDossierPage })));
// Employee document vault (case-scoped + assignment fallback)
const EmployeeDocumentsPage = lazy(() => import('./pages/employee/EmployeeDocumentsPage').then((module) => ({ default: module.EmployeeDocumentsPage })));
// [P1-6] Case roadmap page
const EmployeeCaseRoadmapPage = lazy(() => import('./pages/employee/EmployeeCaseRoadmapPage').then((module) => ({ default: module.EmployeeCaseRoadmapPage })));
const ImmigrationPage = lazy(() => import('./pages/employee/ImmigrationPage').then((module) => ({ default: module.ImmigrationPage })));
const MyImmigrationData = lazy(() => import('./components/immigration/MyImmigrationData').then((module) => ({ default: module.MyImmigrationData })));
// [MVG-6] Immigration workflow screens
const ImmigrationCaseCreatePage = lazy(() => import('./pages/hr/ImmigrationCaseCreatePage').then((module) => ({ default: module.ImmigrationCaseCreatePage })));
const ImmigrationCasePage = lazy(() => import('./pages/hr/ImmigrationCasePage').then((module) => ({ default: module.ImmigrationCasePage })));
const ErasureRequestsPage = lazy(() => import('./pages/hr/ErasureRequestsPage').then((module) => ({ default: module.ErasureRequestsPage })));
const ImmigrationChecklistPage = lazy(() => import('./pages/employee/ImmigrationChecklistPage').then((module) => ({ default: module.ImmigrationChecklistPage })));
const QuoteRequestPage = lazy(() => import('./pages/employee/QuoteRequestPage').then((module) => ({ default: module.QuoteRequestPage })));
const ProvidersPage = lazy(() => import('./pages/ProvidersPage').then((module) => ({ default: module.ProvidersPage })));
const LegacyServicesRedirect = lazy(() => import('./features/services/LegacyServicesRedirect').then((module) => ({ default: module.LegacyServicesRedirect })));
const Messages = lazy(() => import('./pages/Messages').then((module) => ({ default: module.Messages })));
const InboxV2Page = lazy(() => import('./features/platform-v2/inbox/InboxV2Page').then((module) => ({ default: module.InboxV2Page })));
const Resources = lazy(() => import('./pages/Resources').then((module) => ({ default: module.Resources })));
const ServicesQuestions = lazy(() => import('./pages/services/ServicesQuestions').then((module) => ({ default: module.ServicesQuestions })));
const ServicesRecommendations = lazy(() => import('./pages/services/ServicesRecommendations').then((module) => ({ default: module.ServicesRecommendations })));
const ServicesEstimate = lazy(() => import('./pages/services/ServicesEstimate').then((module) => ({ default: module.ServicesEstimate })));
const ServicesRfqNew = lazy(() => import('./pages/services/ServicesRfqNew').then((module) => ({ default: module.ServicesRfqNew })));
const ServicesConclusion = lazy(() => import('./pages/services/ServicesConclusion').then((module) => ({ default: module.ServicesConclusion })));
const QuotesInbox = lazy(() => import('./pages/services/QuotesInbox').then((module) => ({ default: module.QuotesInbox })));
const QuoteRfqDetail = lazy(() => import('./pages/services/QuoteRfqDetail').then((module) => ({ default: module.QuoteRfqDetail })));
const VendorInbox = lazy(() => import('./pages/vendor/VendorInbox').then((module) => ({ default: module.VendorInbox })));
const VendorRfq = lazy(() => import('./pages/vendor/VendorRfq').then((module) => ({ default: module.VendorRfq })));
const HrCompanyProfile = lazy(() => import('./pages/HrCompanyProfile').then((module) => ({ default: module.HrCompanyProfile })));
const HrCompanyProfileV2 = lazy(() => import('./features/platform-v2/company-profile/CompanyProfileV2Page').then((module) => ({ default: module.CompanyProfileV2Page })));
const HrResourcesPreview = lazy(() => import('./pages/HrResourcesPreview').then((module) => ({ default: module.HrResourcesPreview })));
const HrEmployees = lazy(() => import('./pages/HrEmployees').then((module) => ({ default: module.HrEmployees })));
const HrEmployeeDetail = lazy(() => import('./pages/HrEmployeeDetail').then((module) => ({ default: module.HrEmployeeDetail })));
// HrCommandCenter: legacy, kept for /hr/command-center-legacy rollback route only
const HrCommandCenter = lazy(() => import('./pages/HrCommandCenter').then((module) => ({ default: module.HrCommandCenter })));
const HrCommandCenterCaseDetail = lazy(() => import('./pages/HrCommandCenterCaseDetail').then((module) => ({ default: module.HrCommandCenterCaseDetail })));
const HrAnalytics = lazy(() => import('./pages/HrAnalytics').then((module) => ({ default: module.HrAnalytics })));
// HrProviderGrid: legacy, kept for /hr/provider-grid-legacy rollback route only
const HrProviderGrid = lazy(() => import('./pages/HrProviderGrid').then((module) => ({ default: module.HrProviderGrid })));
const HrProviderGridV2 = lazy(() => import('./features/platform-v2/provider-grid/ProviderGridV2Page').then((module) => ({ default: module.ProviderGridV2Page })));
const HrBacklogPage = lazy(() => import('./features/platform-v2/hr-backlog/HrBacklogPage').then((module) => ({ default: module.HrBacklogPage })));
const MobilityControlCenterV2Page = lazy(() => import('./features/platform-v2/mobility-control/MobilityControlCenterV2Page').then((module) => ({ default: module.MobilityControlCenterV2Page })));
const HrRiskDashboardPage = lazy(() => import('./features/platform-v2/mobility-control/HrRiskDashboardPage').then((module) => ({ default: module.HrRiskDashboardPage })));
// HrPolicyBuilder lazy import removed — /hr/settings/policy now redirects to
// /hr/policy?tab=builder via <Navigate> below. HrPolicyBuilderV2Page is
// imported directly by HrPolicy.tsx for the embedded tab.
// HrExceptionsPage lazy import removed (AIQ-1112) — /hr/exceptions now redirects
// to /hr/policy?tab=exceptions; the page is imported directly by HrPolicy.tsx
// for the embedded Exceptions tab.
const HrRequirementsPage = lazy(() => import('./features/requirements/HrRequirementsPage').then((module) => ({ default: module.HrRequirementsPage })));
const AIDecisionsAuditPage = lazy(() => import('./features/ai-oversight/AIDecisionsAuditPage').then((module) => ({ default: module.AIDecisionsAuditPage })));
const HrPolicyRealityPage = lazy(() => import('./features/platform-v2/policy-reality/HrPolicyRealityPage').then((module) => ({ default: module.HrPolicyRealityPage })));
const HrPolicyDashboardPage = lazy(() => import('./features/platform-v2/policy-dashboard/HrPolicyDashboardPage').then((module) => ({ default: module.HrPolicyDashboardPage })));
const EmployeeRichProfilePage = lazy(() => import('./features/platform-v2/employee-profile/EmployeeRichProfilePage').then((module) => ({ default: module.EmployeeRichProfilePage })));
const EmployeeIntakePage = lazy(() => import('./features/platform-v2/intake/EmployeeIntakePage').then((module) => ({ default: module.EmployeeIntakePage })));
const ProviderPortal = lazy(() => import('./pages/ProviderPortal').then((module) => ({ default: module.ProviderPortal })));
const EmployeeTaskPage = lazy(() => import('./pages/employee/EmployeeTaskPage').then((module) => ({ default: module.EmployeeTaskPage })));
const NotificationSettings = lazy(() => import('./pages/NotificationSettings').then((module) => ({ default: module.NotificationSettings })));
const DesignPreview = lazy(() => import('./pages/DesignPreview').then((module) => ({ default: module.DesignPreview })));

const CountriesPage = lazy(() => import('./pages/admin/CountriesPage').then((module) => ({ default: module.CountriesPage })));
const CountryDetailPage = lazy(() => import('./pages/admin/CountryDetailPage').then((module) => ({ default: module.CountryDetailPage })));
const AdminOverviewPage = lazy(() => import('./pages/admin/AdminOverviewPage').then((module) => ({ default: module.AdminOverviewPage })));
const AdminRagQualityPage = lazy(() => import('./pages/admin/AdminRagQualityPage').then((module) => ({ default: module.AdminRagQualityPage })));
const AdminAiUnitEconomicsPage = lazy(() => import('./pages/admin/AdminAiUnitEconomicsPage').then((module) => ({ default: module.AdminAiUnitEconomicsPage })));
const AdminDsarPage = lazy(() => import('./pages/admin/AdminDsarPage').then((module) => ({ default: module.AdminDsarPage })));
const AdminPolicyVersionsPage = lazy(() => import('./pages/admin/AdminPolicyVersionsPage').then((module) => ({ default: module.AdminPolicyVersionsPage })));
const AdminFeatureFlagsPage = lazy(() => import('./pages/admin/AdminFeatureFlagsPage').then((module) => ({ default: module.AdminFeatureFlagsPage })));
const AdminPermissionsPage = lazy(() => import('./pages/admin/AdminPermissionsPage').then((module) => ({ default: module.AdminPermissionsPage })));
const ExecutiveDashboardPage = lazy(() => import('./pages/admin/executive/ExecutiveDashboardPage').then((module) => ({ default: module.ExecutiveDashboardPage })));
const MissionControlPage = lazy(() => import('./pages/admin/mission-control/MissionControlPage').then((module) => ({ default: module.MissionControlPage })));
const AdminAiControlsPage = lazy(() => import('./pages/admin/AdminAiControlsPage').then((module) => ({ default: module.AdminAiControlsPage })));
const AdminMobilityCaseInspectPage = lazy(() => import('./pages/admin/AdminMobilityCaseInspectPage').then((module) => ({ default: module.AdminMobilityCaseInspectPage })));
const AdminPoliciesPage = lazy(() => import('./pages/admin/AdminPoliciesPage').then((module) => ({ default: module.AdminPoliciesPage })));
const AdminCatalogQueuePage = lazy(() => import('./pages/admin/AdminCatalogQueuePage').then((module) => ({ default: module.AdminCatalogQueuePage })));
const AdminRequirementFactsPage = lazy(() => import('./pages/admin/AdminRequirementFactsPage').then((module) => ({ default: module.AdminRequirementFactsPage })));
const AdminResearchRequestsPage = lazy(() => import('./pages/admin/AdminResearchRequestsPage').then((module) => ({ default: module.AdminResearchRequestsPage })));
// AdminPolicyConfigPage (/admin/policy-config) was retired: it duplicated the
// row-by-row editor already living in the Policy Workspace ("Edit structured
// baseline" bulk editor). Per product direction one editor is the source of
// truth — the Policy Workspace row drawers. Route + page removed accordingly.
// AdminCompanies: legacy, kept for /admin/companies-legacy rollback route only
const AdminCompanies = lazy(() => import('./pages/admin/AdminCompanies').then((module) => ({ default: module.AdminCompanies })));
const AdminCompaniesV2 = lazy(() => import('./features/platform-v2/companies/CompaniesV2Page').then((module) => ({ default: module.CompaniesV2Page })));
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers').then((module) => ({ default: module.AdminUsers })));
const AdminAssignments = lazy(() => import('./pages/admin/AdminAssignments').then((module) => ({ default: module.AdminAssignments })));
const AdminMessages = lazy(() => import('./pages/admin/AdminMessages').then((module) => ({ default: module.AdminMessages })));
const AdminErrors = lazy(() => import('./pages/admin/AdminErrors').then((module) => ({ default: module.AdminErrors })));
const AdminCorrectionsTrends = lazy(() => import('./pages/admin/AdminCorrectionsTrends').then((module) => ({ default: module.AdminCorrectionsTrends })));
const AdminFeedback = lazy(() => import('./pages/admin/AdminFeedback'));
const AdminAdminsPage = lazy(() => import('./pages/admin/AdminAdminsPage'));
const AdminAuditLogPage = lazy(() => import('./pages/admin/AdminAuditLogPage'));
const AdminSuppliers = lazy(() => import('./pages/admin/AdminSuppliers').then((module) => ({ default: module.AdminSuppliers })));
const AdminVettingQueue = lazy(() => import('./pages/admin/AdminVettingQueue').then((module) => ({ default: module.AdminVettingQueue })));
const AdminPrompts = lazy(() => import('./pages/admin/AdminPrompts').then((module) => ({ default: module.AdminPrompts })));
const AdminProspects = lazy(() => import('./pages/admin/AdminProspects').then((module) => ({ default: module.AdminProspects })));
const AdminMarketingAnalyticsPage = lazy(() => import('./pages/admin/AdminMarketingAnalyticsPage').then((module) => ({ default: module.AdminMarketingAnalyticsPage })));
const AdminLeads = lazy(() => import('./pages/admin/AdminLeads').then((module) => ({ default: module.AdminLeads })));
const AdminSupplierNew = lazy(() => import('./pages/admin/AdminSupplierNew').then((module) => ({ default: module.AdminSupplierNew })));
const AdminSupplierDetail = lazy(() => import('./pages/admin/AdminSupplierDetail').then((module) => ({ default: module.AdminSupplierDetail })));
const AdminCompanyDetail = lazy(() => import('./pages/admin/AdminCompanyDetail').then((module) => ({ default: module.AdminCompanyDetail })));
const AdminCompanyProfilePage = lazy(() => import('./features/platform-v2/admin-company-profile/AdminCompanyProfilePage').then((module) => ({ default: module.AdminCompanyProfilePage })));
const DataTableDemo = lazy(() => import('./features/platform-v2/data-table/DataTableDemo').then((module) => ({ default: module.DataTableDemo })));
const AdminResources = lazy(() => import('./pages/admin/AdminResources').then((module) => ({ default: module.AdminResources })));
const AdminResourceEditor = lazy(() => import('./pages/admin/AdminResourceEditor').then((module) => ({ default: module.AdminResourceEditor })));
// [P1-2] Form Template Registry
const AdminFormTemplates = lazy(() => import('./pages/admin/AdminFormTemplates').then((module) => ({ default: module.AdminFormTemplates })));
const AdminFormTemplateEditor = lazy(() => import('./pages/admin/AdminFormTemplateEditor').then((module) => ({ default: module.AdminFormTemplateEditor })));
const AdminFormTemplateMap = lazy(() => import('./pages/admin/AdminFormTemplateMap').then((module) => ({ default: module.AdminFormTemplateMap })));
const AdminEvents = lazy(() => import('./pages/admin/AdminEvents').then((module) => ({ default: module.AdminEvents })));
const AdminEventEditor = lazy(() => import('./pages/admin/AdminEventEditor').then((module) => ({ default: module.AdminEventEditor })));
const AdminCategories = lazy(() => import('./pages/admin/AdminCategories').then((module) => ({ default: module.AdminCategories })));
const AdminTags = lazy(() => import('./pages/admin/AdminTags').then((module) => ({ default: module.AdminTags })));
const AdminSources = lazy(() => import('./pages/admin/AdminSources').then((module) => ({ default: module.AdminSources })));
const AdminAbTestsPage = lazy(() => import('./pages/admin/AdminAbTestsPage').then((module) => ({ default: module.AdminAbTestsPage })));
const AdminStagingDashboard = lazy(() => import('./pages/admin/staging/AdminStagingDashboard').then((module) => ({ default: module.AdminStagingDashboard })));
const AdminStagingResources = lazy(() => import('./pages/admin/staging/AdminStagingResources').then((module) => ({ default: module.AdminStagingResources })));
const AdminStagingResourceDetail = lazy(() => import('./pages/admin/staging/AdminStagingResourceDetail').then((module) => ({ default: module.AdminStagingResourceDetail })));
const AdminStagingEvents = lazy(() => import('./pages/admin/staging/AdminStagingEvents').then((module) => ({ default: module.AdminStagingEvents })));
const AdminStagingEventDetail = lazy(() => import('./pages/admin/staging/AdminStagingEventDetail').then((module) => ({ default: module.AdminStagingEventDetail })));
const AdminFreshnessOverview = lazy(() => import('./pages/admin/freshness/AdminFreshnessOverview').then((module) => ({ default: module.AdminFreshnessOverview })));
const AdminFreshnessCountries = lazy(() => import('./pages/admin/freshness/AdminFreshnessCountries').then((module) => ({ default: module.AdminFreshnessCountries })));
const AdminFreshnessCities = lazy(() => import('./pages/admin/freshness/AdminFreshnessCities').then((module) => ({ default: module.AdminFreshnessCities })));
const AdminFreshnessSources = lazy(() => import('./pages/admin/freshness/AdminFreshnessSources').then((module) => ({ default: module.AdminFreshnessSources })));
const AdminSourceMonitor = lazy(() => import('./pages/admin/AdminSourceMonitor').then((module) => ({ default: module.AdminSourceMonitor })));
const AdminFreshnessChanges = lazy(() => import('./pages/admin/freshness/AdminFreshnessChanges').then((module) => ({ default: module.AdminFreshnessChanges })));
const AdminFreshnessStaleContent = lazy(() => import('./pages/admin/freshness/AdminFreshnessStaleContent').then((module) => ({ default: module.AdminFreshnessStaleContent })));
const AdminSourceChangeReviewsPage = lazy(() => import('./pages/admin/source-change-reviews/AdminSourceChangeReviewsPage').then((module) => ({ default: module.AdminSourceChangeReviewsPage })));
const AdminCrawlSchedules = lazy(() => import('./pages/admin/freshness/AdminCrawlSchedules').then((module) => ({ default: module.AdminCrawlSchedules })));
const AdminCrawlJobRuns = lazy(() => import('./pages/admin/freshness/AdminCrawlJobRuns').then((module) => ({ default: module.AdminCrawlJobRuns })));
const AdminCrawlJobRunDetail = lazy(() => import('./pages/admin/freshness/AdminCrawlJobRunDetail').then((module) => ({ default: module.AdminCrawlJobRunDetail })));
// AdminReviewQueuePage: legacy, kept for /admin/review-queue-legacy rollback route only
const AdminReviewQueuePage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueuePage').then((module) => ({ default: module.AdminReviewQueuePage })));
const AdminReviewQueueV2Page = lazy(() => import('./features/platform-v2/review-queue/AdminReviewQueueV2Page').then((module) => ({ default: module.AdminReviewQueueV2Page })));
const AdminReviewQueueDetailPage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueueDetailPage').then((module) => ({ default: module.AdminReviewQueueDetailPage })));
const AdminReviewQueueWorkloadPage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueueWorkloadPage').then((module) => ({ default: module.AdminReviewQueueWorkloadPage })));
const OpsAnalyticsV2Page = lazy(() => import('./features/platform-v2/ops-analytics/OpsAnalyticsV2Page').then((module) => ({ default: module.OpsAnalyticsV2Page })));
const AdminOpsSlaPage = lazy(() => import('./pages/admin/ops/AdminOpsSlaPage').then((module) => ({ default: module.AdminOpsSlaPage })));
const AdminOpsQueuePage = lazy(() => import('./pages/admin/ops/AdminOpsQueuePage').then((module) => ({ default: module.AdminOpsQueuePage })));
const AdminOpsReviewersPage = lazy(() => import('./pages/admin/ops/AdminOpsReviewersPage').then((module) => ({ default: module.AdminOpsReviewersPage })));
const AdminOpsDestinationsPage = lazy(() => import('./pages/admin/ops/AdminOpsDestinationsPage').then((module) => ({ default: module.AdminOpsDestinationsPage })));
const AdminOpsNotificationsPage = lazy(() => import('./pages/admin/ops/AdminOpsNotificationsPage').then((module) => ({ default: module.AdminOpsNotificationsPage })));
const AdminSpecialistReviewPage = lazy(() => import('./pages/admin/AdminSpecialistReviewPage').then((module) => ({ default: module.AdminSpecialistReviewPage })));
const AdminAuthPageDesign = lazy(() => import('./pages/admin/AdminAuthPageDesign').then((module) => ({ default: module.AdminAuthPageDesign })));

function RouteFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f7fa] px-6">
      <div className="rounded-2xl border border-[#e2e8f0] bg-white px-6 py-4 text-sm text-[#4b5563] shadow-sm">
        Loading page...
      </div>
    </div>
  );
}

function ReviewToEmployeeDashboardRedirect() {
  const { caseId } = useParams<{ caseId: string }>();
  const to = caseId
    ? `${ROUTE_DEFS.hrEmployeeDashboard.path}?caseId=${encodeURIComponent(caseId)}`
    : ROUTE_DEFS.hrEmployeeDashboard.path;
  return <Navigate to={to} replace />;
}

function QueryRedirect() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('__redirect');
    if (!redirect || !redirect.startsWith('/')) return;

    params.delete('__redirect');
    const remaining = params.toString();
    const target = remaining
      ? `${redirect}${redirect.includes('?') ? '&' : '?'}${remaining}`
      : redirect;
    navigate(target, { replace: true });
  }, [navigate]);

  return null;
}

function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
    <Router>
      <FeatureFlagProvider>
      <ScrollToTop />
      <NavigationLogger />
      <DemoBookingProvider>
      <SelectedCaseProvider>
      <EmployeeAssignmentProvider>
      <HrCompanyContextProvider>
      <AdminViewingCompanyProvider>
      <ServicesFlowProvider>
      <QueryRedirect />
      <Suspense fallback={<RouteFallback />}>
      <AppErrorBoundary componentName="AppRouter">
      <ResilientRoute>
      <Routes>
        <Route path={ROUTE_DEFS.landing.path} element={<Landing />} />
        <Route path={ROUTE_DEFS.platform.path} element={<PlatformPage />} />
        <Route path={ROUTE_DEFS.why.path} element={<WhyReloPassPage />} />
        {/* Alias: /why-relopass (used in marketing/audit links) renders the same page
            instead of falling through to the homepage redirect. */}
        <Route path="/why-relopass" element={<WhyReloPassPage />} />
        <Route path={ROUTE_DEFS.howItWorks.path} element={<HowItWorksPage />} />
        <Route path={ROUTE_DEFS.getStarted.path} element={<GetStartedPage />} />
        <Route path={ROUTE_DEFS.testDrive.path} element={<TestDrivePage />} />
        <Route path={ROUTE_DEFS.testDriveSurvey.path} element={<TestDriveSurveyPage />} />
        <Route path={ROUTE_DEFS.security.path} element={<SecurityPage />} />
        <Route path={ROUTE_DEFS.privacy.path} element={<PrivacyPage />} />
        <Route path={ROUTE_DEFS.compliance.path} element={<CompliancePage />} />
        <Route path={ROUTE_DEFS.access.path} element={<AccessPage />} />
        <Route path={ROUTE_DEFS.auth.path} element={<Auth />} />
        {/* AIQ-920: /login alias renders the same Auth screen (defaults to login mode). */}
        <Route path={ROUTE_DEFS.login.path} element={<Auth />} />
        {/* Design preview — sandboxed Claude Design handoff bundle in iframe. Static, no auth, mock data only. */}
        <Route path="/design-preview" element={<DesignPreview />} />
        {/* Provider portal — public, magic-link JWT auth */}
        <Route path={ROUTE_DEFS.providerPortal.path} element={<ProviderPortal />} />
        <Route path="/journey" element={<RequireEmployeeRoute><Journey /></RequireEmployeeRoute>} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path={ROUTE_DEFS.employeeJourney.path} element={<RequireEmployeeRoute><Navigate to={ROUTE_DEFS.employeeDashboard.path} replace /></RequireEmployeeRoute>} />
        {/* Bare /employee/roadmap has no caseId — keep logged-in employees in-app
            (they'd otherwise hit the catch-all → public marketing landing). The
            dashboard is the case hub where the case-scoped roadmap is reachable. */}
        <Route path="/employee/roadmap" element={<RequireEmployeeRoute><Navigate to={ROUTE_DEFS.employeeDashboard.path} replace /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeDashboard.path} element={<RequireEmployeeRoute><EmployeeJourney /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeQuoteRequest.path} element={<RequireEmployeeRoute><QuoteRequestPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeTaskPage.path} element={<RequireEmployeeRoute><EmployeeTaskPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeRichProfile.path} element={<RequireEmployeeRoute><EmployeeRichProfilePage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeIntake.path} element={<RequireEmployeeRoute><EmployeeIntakePage /></RequireEmployeeRoute>} />
        {/* AIQ-976: case-scoped intake — same page, but opens the case from the URL. */}
        <Route path={ROUTE_DEFS.employeeCaseIntake.path} element={<RequireEmployeeRoute><EmployeeIntakePage /></RequireEmployeeRoute>} />
        <Route path={WIZARD_ROUTES.EMP_DASH} element={<RequireEmployeeRoute><Navigate to={ROUTE_DEFS.employeeDashboard.path} replace /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.hrDashboard.path} element={<RequireHrRoute><HrDashboard /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrAnalytics.path} element={<RequireHrRoute><HrAnalytics /></RequireHrRoute>} />
        {/* /hr/command-center: gated by mobility_control flag. ON → new
            MobilityControlCenterV2Page (mock-aligned). OFF → legacy
            HrCommandCenter "Dashboard". Sibling /hr/command-center-v2
            always renders V2 for side-by-side comparison. */}
        {/* platform-v2: mobility_control promoted to default-on (2026-05-20).
            Legacy kept at /hr/command-center-legacy for emergency rollback. */}
        <Route
          path={ROUTE_DEFS.hrCommandCenter.path}
          element={<RequireHrRoute><MobilityControlCenterV2Page /></RequireHrRoute>}
        />
        <Route path="/hr/command-center-v2" element={<RequireHrRoute><MobilityControlCenterV2Page /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrRisk.path} element={<RequireHrRoute><HrRiskDashboardPage /></RequireHrRoute>} />
        <Route path="/hr/command-center-legacy" element={<RequireHrRoute><HrCommandCenter /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrCommandCenterCase.path} element={<RequireHrRoute><HrCommandCenterCaseDetail /></RequireHrRoute>} />
        {/* [MVG-6A] HR — create immigration case */}
        <Route path={ROUTE_DEFS.hrImmigrationCreate.path} element={<RequireHrRoute><ImmigrationCaseCreatePage /></RequireHrRoute>} />
        {/* [MVG-6A/6C] HR — immigration case status timeline */}
        <Route path={ROUTE_DEFS.hrImmigrationCase.path} element={<RequireHrRoute><ImmigrationCasePage /></RequireHrRoute>} />
        {/* platform-v2: flag-gated. Default OFF → legacy HrProviderGrid renders.
            Enable per-session: localStorage.setItem('platform_v2_mobility_control', 'on').
            Sibling /hr/provider-grid-v2 always renders V2 for side-by-side comparison. */}
        {/* platform-v2: provider grid promoted to default-on (2026-05-20).
            Legacy kept at /hr/provider-grid-legacy for emergency rollback. */}
        <Route
          path={ROUTE_DEFS.hrProviderGrid.path}
          element={<RequireHrRoute><HrProviderGridV2 /></RequireHrRoute>}
        />
        <Route path="/hr/provider-grid-v2" element={<RequireHrRoute><HrProviderGridV2 /></RequireHrRoute>} />
        <Route path="/hr/provider-grid-legacy" element={<RequireHrRoute><HrProviderGrid /></RequireHrRoute>} />
        {/* HR Backlog (V2): pending employee tasks across the HR's company.
            HR + ADMIN access — server-side filtering by company_id. */}
        <Route path="/hr/backlog" element={<RequireHrRoute><HrBacklogPage /></RequireHrRoute>} />
        {/* /hr/settings/policy → /hr/policy?tab=builder — policy builder is now
            a tab on the Policy page rather than a standalone route. */}
        <Route path={ROUTE_DEFS.hrPolicyBuilder.path} element={<RequireHrRoute><Navigate to={`${ROUTE_DEFS.hrPolicy.path}?tab=builder`} replace /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrExceptions.path} element={<RequireHrRoute><Navigate to={`${ROUTE_DEFS.hrPolicy.path}?tab=exceptions`} replace /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrRequirements.path} element={<RequireHrRoute><HrRequirementsPage /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrAiDecisions.path} element={<RequireHrRoute><AIDecisionsAuditPage /></RequireHrRoute>} />
                <Route path={ROUTE_DEFS.hrPolicyReality.path} element={<RequireHrRoute><HrPolicyRealityPage /></RequireHrRoute>} />
                <Route path={ROUTE_DEFS.hrPolicyDashboard.path} element={<RequireHrRoute><HrPolicyDashboardPage /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrEmployeeDashboard.path} element={<RequireHrRoute><HrAssignmentReview /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrCaseSummary.path} element={<RequireHrRoute><HrCaseSummary /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrCaseEstimate.path} element={<RequireHrRoute><HrCaseEstimatePage /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrReview.path} element={<RequireHrRoute><Navigate to={ROUTE_DEFS.hrEmployeeDashboard.path} replace /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrReviewCase.path} element={<RequireHrRoute><ReviewToEmployeeDashboardRedirect /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrAssignmentReview.path} element={<RequireHrRoute><HrAssignmentReview /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrComplianceIndex.path} element={<RequireHrRoute><HrComplianceCheck /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrErasureRequests.path} element={<RequireHrRoute><ErasureRequestsPage /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrCompliance.path} element={<RequireHrRoute><HrComplianceCheck /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrPackage.path} element={<RequireHrRoute><HrAssignmentPackageReview /></RequireHrRoute>} />
        {import.meta.env.DEV && (
          <Route path={ROUTE_DEFS.auditNavigation.path} element={<NavigationAudit />} />
        )}
        <Route
          path={ROUTE_DEFS.providers.path}
          element={<Navigate to={ROUTE_DEFS.services.path} replace />}
        />
        {/* [AIQ-1285/H-05] Case-scoped services flow — canonical routes. */}
        <Route path={ROUTE_DEFS.caseServices.path} element={<ProvidersPage />} />
        <Route path={ROUTE_DEFS.caseServicesQuestions.path} element={<ServicesQuestions />} />
        <Route path={ROUTE_DEFS.caseServicesRecommendations.path} element={<ServicesRecommendations />} />
        <Route path={ROUTE_DEFS.caseServicesEstimate.path} element={<ServicesEstimate />} />
        <Route path={ROUTE_DEFS.caseServicesRfqNew.path} element={<ServicesRfqNew />} />
        <Route path={ROUTE_DEFS.caseServicesConclusion.path} element={<ServicesConclusion />} />
        {/* Legacy /services/* → redirect to the case-scoped equivalents (back-compat
            for deep links + last-visited entries). */}
        <Route path={ROUTE_DEFS.services.path} element={<LegacyServicesRedirect to="caseServices" />} />
        <Route path={ROUTE_DEFS.servicesQuestions.path} element={<LegacyServicesRedirect to="caseServicesQuestions" />} />
        <Route path={ROUTE_DEFS.servicesRecommendations.path} element={<LegacyServicesRedirect to="caseServicesRecommendations" />} />
        <Route path={ROUTE_DEFS.servicesEstimate.path} element={<LegacyServicesRedirect to="caseServicesEstimate" />} />
        <Route path={ROUTE_DEFS.servicesRfqNew.path} element={<LegacyServicesRedirect to="caseServicesRfqNew" />} />
        <Route path={ROUTE_DEFS.servicesConclusion.path} element={<LegacyServicesRedirect to="caseServicesConclusion" />} />
        <Route path={ROUTE_DEFS.quotesInbox.path} element={<QuotesInbox />} />
        <Route path={ROUTE_DEFS.quoteRfqDetail.path} element={<QuoteRfqDetail />} />
        <Route path={ROUTE_DEFS.vendorInbox.path} element={<VendorInbox />} />
        <Route path={ROUTE_DEFS.vendorRfq.path} element={<VendorRfq />} />
        <Route path={ROUTE_DEFS.hrPreferredSuppliers.path} element={<RequireHrRoute><HrPreferredSuppliers /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrVendorCuration.path} element={<RequireHrRoute><HrVendorCuration /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrServiceProviders.path} element={<RequireHrRoute><HrServiceProvidersPage /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrPolicy.path} element={<RequireHrRoute allowEmployee><HrPolicy /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.employeePolicy.path} element={<RequireEmployeeRoute><EmployeePolicyPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeBenefitsComparison.path} element={<RequireEmployeeRoute><EmployeeBenefitComparisonPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeHrPolicy.path} element={<Navigate to={ROUTE_DEFS.hrPolicy.path} replace />} />
        <Route path={ROUTE_DEFS.hrPolicyManagement.path} element={<RequireHrRoute><Navigate to={ROUTE_DEFS.hrPolicy.path} replace /></RequireHrRoute>} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD} element={<RequireEmployeeRoute><LegacyWizardRedirect /></RequireEmployeeRoute>} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD_STEP} element={<RequireEmployeeRoute><LegacyWizardRedirect /></RequireEmployeeRoute>} />
        <Route path={WIZARD_ROUTES.CASE_REVIEW} element={<RequireEmployeeRoute><LegacyWizardRedirect /></RequireEmployeeRoute>} />
        <Route path={WIZARD_ROUTES.CASE_SUMMARY} element={<RequireEmployeeRoute><EmployeeCaseSummary /></RequireEmployeeRoute>} />
        {/* [AIQ-1259b] /plan consolidated into /roadmap — redirect, preserving caseId. */}
        <Route path={WIZARD_ROUTES.CASE_PLAN} element={<RequireEmployeeRoute><CasePlanToRoadmapRedirect /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeCaseImmigration.path} element={<RequireEmployeeRoute><ImmigrationPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeImmigrationAssistant.path} element={<RequireEmployeeRoute><ImmigrationAssistantPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeCaseMyData.path} element={<RequireEmployeeRoute><MyImmigrationData /></RequireEmployeeRoute>} />
        {/* [P1-5] Dossier & Forms list view */}
        <Route path={ROUTE_DEFS.employeeCaseDossier.path} element={<RequireEmployeeRoute><EmployeeDossierPage /></RequireEmployeeRoute>} />
        {/* Employee document vault — case-scoped + bare /employee/documents (assignment fallback) */}
        <Route path={ROUTE_DEFS.employeeCaseDocuments.path} element={<RequireEmployeeRoute><EmployeeDocumentsPage /></RequireEmployeeRoute>} />
        <Route path={ROUTE_DEFS.employeeDocuments.path} element={<RequireEmployeeRoute><EmployeeDocumentsPage /></RequireEmployeeRoute>} />
        {/* [P1-6] Case roadmap */}
        <Route path={ROUTE_DEFS.employeeCaseRoadmap.path} element={<RequireEmployeeRoute><EmployeeCaseRoadmapPage /></RequireEmployeeRoute>} />
        {/* [MVG-6B] Employee — immigration document checklist; allowHR so HR can view via timeline link */}
        <Route path={ROUTE_DEFS.employeeCaseImmigrationChecklist.path} element={<RequireEmployeeRoute allowHR><ImmigrationChecklistPage /></RequireEmployeeRoute>} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRIES} element={<RequireAdminRoute><CountriesPage /></RequireAdminRoute>} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRY_DETAIL} element={<RequireAdminRoute><CountryDetailPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminConsole.path} element={<RequireAdminRoute><AdminOverviewPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminRagQuality.path} element={<RequireAdminRoute><AdminRagQualityPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAiUnitEconomics.path} element={<RequireAdminRoute><AdminAiUnitEconomicsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminDsar.path} element={<RequireAdminRoute><AdminDsarPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPolicyVersions.path} element={<RequireAdminRoute><AdminPolicyVersionsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFeatureFlags.path} element={<RequireAdminRoute><AdminFeatureFlagsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPermissions.path} element={<RequireAdminRoute><AdminPermissionsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminExecutive.path} element={<RequireAdminRoute><ExecutiveDashboardPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMissionControl.path} element={<RequireAdminRoute><MissionControlPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAiControls.path} element={<RequireAdminRoute><AdminAiControlsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCatalogQueue.path} element={<RequireAdminRoute><AdminCatalogQueuePage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminRequirementFacts.path} element={<RequireAdminRoute><AdminRequirementFactsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResearchRequests.path} element={<RequireAdminRoute><AdminResearchRequestsPage /></RequireAdminRoute>} />
        {/* platform-v2: companies promoted to default-on (2026-05-20).
            Legacy kept at /admin/companies-legacy for emergency rollback. */}
        <Route
          path={ROUTE_DEFS.adminCompanies.path}
          element={
            <RequireAdminRoute>
              <AdminCompaniesV2 />
            </RequireAdminRoute>
          }
        />
        <Route path="/admin/companies-v2" element={<RequireAdminRoute><AdminCompaniesV2 /></RequireAdminRoute>} />
        <Route path="/admin/companies-legacy" element={<RequireAdminRoute><AdminCompanies /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPeople.path} element={<RequireAdminRoute><AdminUsers /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAssignments.path} element={<RequireAdminRoute><AdminAssignments /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMobilityCases.path} element={<RequireAdminRoute><AdminMobilityCaseInspectPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMobilityCaseInspect.path} element={<RequireAdminRoute><AdminMobilityCaseInspectPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPolicies.path} element={<RequireAdminRoute><AdminPoliciesPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMessages.path} element={<RequireAdminRoute><AdminMessages /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResearch.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminOverview.path} replace /></RequireAdminRoute>} />
        <Route path="/admin/companies/:companyId" element={<RequireAdminRoute><AdminCompanyDetail /></RequireAdminRoute>} />
        {/* Tenant-scoped sub-route: URL param is the scope, no global state. */}
        <Route path="/admin/companies/:companyId/profile" element={<RequireAdminRoute><AdminCompanyProfilePage /></RequireAdminRoute>} />
        {/* Dev-only demo for the <DataTable> primitive. Admin-gated. No real data. */}
        <Route path="/dev/data-table-demo" element={<RequireAdminRoute><DataTableDemo /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminUsers.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminPeople.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminRelocations.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminAssignments.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSupport.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminMessages.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminErrors.path} element={<RequireAdminRoute><AdminErrors /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFeedback.path} element={<RequireAdminRoute><AdminFeedback /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAdmins.path} element={<RequireAdminRoute><AdminAdminsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAuditLog.path} element={<RequireAdminRoute><AdminAuditLogPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliers.path} element={<RequireAdminRoute><AdminSuppliers /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminVettingQueue.path} element={<RequireAdminRoute><AdminVettingQueue /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPrompts.path} element={<RequireAdminRoute><AdminPrompts /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminProspects.path} element={<RequireAdminRoute><AdminProspects /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMarketingAnalytics.path} element={<RequireAdminRoute><AdminMarketingAnalyticsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminLeads.path} element={<RequireAdminRoute><AdminLeads /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliersNew.path} element={<RequireAdminRoute><AdminSupplierNew /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliersDetail.path} element={<RequireAdminRoute><AdminSupplierDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResources.path} element={<RequireAdminRoute><AdminResources /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResourcesNew.path} element={<RequireAdminRoute><AdminResourceEditor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResourcesEdit.path} element={<RequireAdminRoute><AdminResourceEditor /></RequireAdminRoute>} />
        {/* [PRODUCT-6E] A/B test experiment dashboard */}
        <Route path={ROUTE_DEFS.adminAbTests.path} element={<RequireAdminRoute><AdminAbTestsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCorrectionsTrends.path} element={<RequireAdminRoute><AdminCorrectionsTrends /></RequireAdminRoute>} />
        {/* [P1-2] Form Template Registry */}
        <Route path={ROUTE_DEFS.adminFormTemplates.path} element={<RequireAdminRoute><AdminFormTemplates /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFormTemplatesNew.path} element={<RequireAdminRoute><AdminFormTemplateEditor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFormTemplatesEdit.path} element={<RequireAdminRoute><AdminFormTemplateEditor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFormTemplatesMap.path} element={<RequireAdminRoute><AdminFormTemplateMap /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminEvents.path} element={<RequireAdminRoute><AdminEvents /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminEventsEdit.path} element={<RequireAdminRoute><AdminEventEditor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCategories.path} element={<RequireAdminRoute><AdminCategories /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminTags.path} element={<RequireAdminRoute><AdminTags /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSources.path} element={<RequireAdminRoute><AdminSources /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminStagingDashboard.path} element={<RequireAdminRoute><AdminStagingDashboard /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminStagingResources.path} element={<RequireAdminRoute><AdminStagingResources /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminStagingResourceDetail.path} element={<RequireAdminRoute><AdminStagingResourceDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminStagingEvents.path} element={<RequireAdminRoute><AdminStagingEvents /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminStagingEventDetail.path} element={<RequireAdminRoute><AdminStagingEventDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshness.path} element={<RequireAdminRoute><AdminFreshnessOverview /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessCountries.path} element={<RequireAdminRoute><AdminFreshnessCountries /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessCities.path} element={<RequireAdminRoute><AdminFreshnessCities /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessSources.path} element={<RequireAdminRoute><AdminFreshnessSources /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSourceMonitor.path} element={<RequireAdminRoute><AdminSourceMonitor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessChanges.path} element={<RequireAdminRoute><AdminFreshnessChanges /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessStaleContent.path} element={<RequireAdminRoute><AdminFreshnessStaleContent /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSourceChangeReviews.path} element={<RequireAdminRoute><AdminSourceChangeReviewsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlSchedules.path} element={<RequireAdminRoute><AdminCrawlSchedules /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlJobRuns.path} element={<RequireAdminRoute><AdminCrawlJobRuns /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlJobRunDetail.path} element={<RequireAdminRoute><AdminCrawlJobRunDetail /></RequireAdminRoute>} />
        {/* platform-v2: review_queue promoted to default-on (2026-05-20).
            Legacy kept at /admin/review-queue-legacy for emergency rollback. */}
        <Route
          path={ROUTE_DEFS.adminReviewQueue.path}
          element={
            <RequireAdminRoute>
              <AdminReviewQueueV2Page />
            </RequireAdminRoute>
          }
        />
        <Route path="/admin/review-queue-v2" element={<RequireAdminRoute><AdminReviewQueueV2Page /></RequireAdminRoute>} />
        <Route path="/admin/review-queue-legacy" element={<RequireAdminRoute><AdminReviewQueuePage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminReviewQueueWorkload.path} element={<RequireAdminRoute><AdminReviewQueueWorkloadPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminReviewQueueDetail.path} element={<RequireAdminRoute><AdminReviewQueueDetailPage /></RequireAdminRoute>} />
        {/* Ops analytics — Dashboard is the default landing; SLA / Queue /
            Reviewers / Destinations / Alerts are sibling tabs rendered by
            AdminOpsLayout. All six pages share the same tab strip. */}
        <Route path={ROUTE_DEFS.adminOps.path} element={<RequireAdminRoute><OpsAnalyticsV2Page /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsSla.path} element={<RequireAdminRoute><AdminOpsSlaPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsQueue.path} element={<RequireAdminRoute><AdminOpsQueuePage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsReviewers.path} element={<RequireAdminRoute><AdminOpsReviewersPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsDestinations.path} element={<RequireAdminRoute><AdminOpsDestinationsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsNotifications.path} element={<RequireAdminRoute><AdminOpsNotificationsPage /></RequireAdminRoute>} />
        {/* [AIQ-633] Specialist review — admin reviews AI-generated roadmap steps */}
        <Route path={ROUTE_DEFS.adminSpecialistReview.path} element={<RequireAdminRoute><AdminSpecialistReviewPage /></RequireAdminRoute>} />
        {/* Auth Page Design — live-tune the /auth page's GlobeNetwork canvas */}
        <Route path={ROUTE_DEFS.adminAuthPageDesign.path} element={<RequireAdminRoute><AdminAuthPageDesign /></RequireAdminRoute>} />
        {/* platform-v2: V2 inbox renders by default. Legacy Messages remains
            mounted at /messages-legacy + /hr/messages-legacy for emergency
            rollback. Sibling /messages-v2 always renders V2 for side-by-side
            QA against the legacy paths. */}
        <Route path={ROUTE_DEFS.messages.path} element={<InboxV2Page />} />
        <Route path={ROUTE_DEFS.hrMessages.path} element={<RequireHrRoute><InboxV2Page /></RequireHrRoute>} />
        <Route path="/messages-v2" element={<InboxV2Page />} />
        <Route path="/messages-legacy" element={<Messages />} />
        <Route path="/hr/messages-legacy" element={<RequireHrRoute><Messages /></RequireHrRoute>} />
        <Route
          path={ROUTE_DEFS.resources.path}
          element={<Resources />}
        />
        <Route
          path={ROUTE_DEFS.caseResources.path}
          element={<Resources />}
        />
        {/*
          Placeholder routes kept as dev-only. In prod they fall through to
          the catch-all (redirect to landing) — better than shipping a visible
          "coming soon" card during demos. Remove these entirely once the
          feature ships or the nav entry is retired.
        */}
        <Route
          path={ROUTE_DEFS.hrResources.path}
          element={<RequireHrRoute><HrResourcesPreview /></RequireHrRoute>}
        />
        {/* platform-v2: V2 is now the default. Legacy HrCompanyProfile remains
            mounted at /hr/company-profile-legacy for emergency rollback. */}
        <Route path={ROUTE_DEFS.hrCompanyProfile.path} element={<RequireHrRoute><HrCompanyProfileV2 /></RequireHrRoute>} />
        <Route path="/hr/company-profile-legacy" element={<RequireHrRoute><HrCompanyProfile /></RequireHrRoute>} />
        <Route path="/hr/company-profile-v2" element={<RequireHrRoute><HrCompanyProfileV2 /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrEmployees.path} element={<RequireHrRoute><HrEmployees /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.hrEmployeeDetail.path} element={<RequireHrRoute><HrEmployeeDetail /></RequireHrRoute>} />
        <Route path={ROUTE_DEFS.notificationSettings.path} element={<NotificationSettings />} />
        {import.meta.env.DEV && (
          <Route
            path={ROUTE_DEFS.submissionCenter.path}
            element={<PlaceholderPage title="Submission Center" description="Finalize and submit case documentation." />}
          />
        )}
        {import.meta.env.DEV && (
          <>
            <Route path="/debug/auth" element={<DebugAuth />} />
            <Route path="/debug/assignment" element={<AssignmentDebugPage />} />
          </>
        )}
        {/* AIQ-980: keep authenticated users in-app on their role dashboard for
            unmatched URLs (e.g. employee → /hr/assignments) instead of dumping
            them on the public marketing homepage. Anonymous → landing. */}
        <Route path="*" element={<NotFoundRedirect />} />
      </Routes>
      </ResilientRoute>
      </AppErrorBoundary>
      </Suspense>
      </ServicesFlowProvider>
      </AdminViewingCompanyProvider>
      </HrCompanyContextProvider>
      </EmployeeAssignmentProvider>
      </SelectedCaseProvider>
      <BookDemoModal />
      </DemoBookingProvider>
      <PerfPanel />
      </FeatureFlagProvider>
    </Router>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;


/* import TestRpc from "./dev/TestRpc";

function App() {
  return <TestRpc />;
}

export default App; */
