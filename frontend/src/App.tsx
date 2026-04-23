import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
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
import { TrustPage } from './pages/public/TrustPage';
import { WhyReloPassPage } from './pages/public/WhyReloPassPage';
import { AccessPage } from './pages/public/AccessPage';
import { Auth } from './pages/Auth';
import { RequireAdminRoute } from './features/admin/RequireAdminRoute';
import { ROUTES as WIZARD_ROUTES } from './routes';
import { NavigationAudit } from './pages/NavigationAudit';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { DebugAuth } from './pages/DebugAuth';
import { AssignmentDebugPage } from './pages/AssignmentDebugPage';
import { PerfPanel } from './components/PerfPanel';

const Journey = lazy(() => import('./pages/Journey').then((module) => ({ default: module.Journey })));
const Dashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })));
const EmployeeJourney = lazy(() => import('./pages/EmployeeJourney').then((module) => ({ default: module.EmployeeJourney })));
const HrDashboard = lazy(() => import('./pages/HrDashboard').then((module) => ({ default: module.HrDashboard })));
const HrCaseSummary = lazy(() => import('./pages/HrCaseSummary').then((module) => ({ default: module.HrCaseSummary })));
const HrAssignmentReview = lazy(() => import('./pages/HrAssignmentReview').then((module) => ({ default: module.HrAssignmentReview })));
const HrComplianceCheck = lazy(() => import('./pages/HrComplianceCheck').then((module) => ({ default: module.HrComplianceCheck })));
const HrAssignmentPackageReview = lazy(() => import('./pages/HrAssignmentPackageReview').then((module) => ({ default: module.HrAssignmentPackageReview })));
const HrPreferredSuppliers = lazy(() => import('./pages/HrPreferredSuppliers').then((module) => ({ default: module.HrPreferredSuppliers })));
const HrPolicy = lazy(() => import('./pages/HrPolicy').then((module) => ({ default: module.HrPolicy })));
const EmployeePolicyPage = lazy(() => import('./pages/employee/EmployeePolicyPage').then((module) => ({ default: module.EmployeePolicyPage })));
const CaseWizardPage = lazy(() => import('./pages/employee/CaseWizardPage').then((module) => ({ default: module.CaseWizardPage })));
const EmployeeCaseSummary = lazy(() => import('./pages/employee/EmployeeCaseSummary').then((module) => ({ default: module.EmployeeCaseSummary })));
const EmployeeRelocationPlanPage = lazy(() => import('./pages/employee/EmployeeRelocationPlanPage').then((module) => ({ default: module.EmployeeRelocationPlanPage })));
const ProvidersPage = lazy(() => import('./pages/ProvidersPage').then((module) => ({ default: module.ProvidersPage })));
const Messages = lazy(() => import('./pages/Messages').then((module) => ({ default: module.Messages })));
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
const HrEmployees = lazy(() => import('./pages/HrEmployees').then((module) => ({ default: module.HrEmployees })));
const HrEmployeeDetail = lazy(() => import('./pages/HrEmployeeDetail').then((module) => ({ default: module.HrEmployeeDetail })));
const HrCommandCenter = lazy(() => import('./pages/HrCommandCenter').then((module) => ({ default: module.HrCommandCenter })));
const HrCommandCenterCaseDetail = lazy(() => import('./pages/HrCommandCenterCaseDetail').then((module) => ({ default: module.HrCommandCenterCaseDetail })));
const NotificationSettings = lazy(() => import('./pages/NotificationSettings').then((module) => ({ default: module.NotificationSettings })));

const CountriesPage = lazy(() => import('./pages/admin/CountriesPage').then((module) => ({ default: module.CountriesPage })));
const CountryDetailPage = lazy(() => import('./pages/admin/CountryDetailPage').then((module) => ({ default: module.CountryDetailPage })));
const AdminOverviewPage = lazy(() => import('./pages/admin/AdminOverviewPage').then((module) => ({ default: module.AdminOverviewPage })));
const AdminMobilityCaseInspectPage = lazy(() => import('./pages/admin/AdminMobilityCaseInspectPage').then((module) => ({ default: module.AdminMobilityCaseInspectPage })));
const AdminPoliciesPage = lazy(() => import('./pages/admin/AdminPoliciesPage').then((module) => ({ default: module.AdminPoliciesPage })));
// AdminPolicyConfigPage (/admin/policy-config) was retired: it duplicated the
// row-by-row editor already living in the Policy Workspace ("Edit structured
// baseline" bulk editor). Per product direction one editor is the source of
// truth — the Policy Workspace row drawers. Route + page removed accordingly.
const AdminCompanies = lazy(() => import('./pages/admin/AdminCompanies').then((module) => ({ default: module.AdminCompanies })));
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers').then((module) => ({ default: module.AdminUsers })));
const AdminAssignments = lazy(() => import('./pages/admin/AdminAssignments').then((module) => ({ default: module.AdminAssignments })));
const AdminMessages = lazy(() => import('./pages/admin/AdminMessages').then((module) => ({ default: module.AdminMessages })));
const AdminSuppliers = lazy(() => import('./pages/admin/AdminSuppliers').then((module) => ({ default: module.AdminSuppliers })));
const AdminSupplierNew = lazy(() => import('./pages/admin/AdminSupplierNew').then((module) => ({ default: module.AdminSupplierNew })));
const AdminSupplierDetail = lazy(() => import('./pages/admin/AdminSupplierDetail').then((module) => ({ default: module.AdminSupplierDetail })));
const AdminCompanyDetail = lazy(() => import('./pages/admin/AdminCompanyDetail').then((module) => ({ default: module.AdminCompanyDetail })));
const AdminResources = lazy(() => import('./pages/admin/AdminResources').then((module) => ({ default: module.AdminResources })));
const AdminResourceEditor = lazy(() => import('./pages/admin/AdminResourceEditor').then((module) => ({ default: module.AdminResourceEditor })));
const AdminEvents = lazy(() => import('./pages/admin/AdminEvents').then((module) => ({ default: module.AdminEvents })));
const AdminEventEditor = lazy(() => import('./pages/admin/AdminEventEditor').then((module) => ({ default: module.AdminEventEditor })));
const AdminCategories = lazy(() => import('./pages/admin/AdminCategories').then((module) => ({ default: module.AdminCategories })));
const AdminTags = lazy(() => import('./pages/admin/AdminTags').then((module) => ({ default: module.AdminTags })));
const AdminSources = lazy(() => import('./pages/admin/AdminSources').then((module) => ({ default: module.AdminSources })));
const AdminStagingDashboard = lazy(() => import('./pages/admin/staging/AdminStagingDashboard').then((module) => ({ default: module.AdminStagingDashboard })));
const AdminStagingResources = lazy(() => import('./pages/admin/staging/AdminStagingResources').then((module) => ({ default: module.AdminStagingResources })));
const AdminStagingResourceDetail = lazy(() => import('./pages/admin/staging/AdminStagingResourceDetail').then((module) => ({ default: module.AdminStagingResourceDetail })));
const AdminStagingEvents = lazy(() => import('./pages/admin/staging/AdminStagingEvents').then((module) => ({ default: module.AdminStagingEvents })));
const AdminStagingEventDetail = lazy(() => import('./pages/admin/staging/AdminStagingEventDetail').then((module) => ({ default: module.AdminStagingEventDetail })));
const AdminFreshnessOverview = lazy(() => import('./pages/admin/freshness/AdminFreshnessOverview').then((module) => ({ default: module.AdminFreshnessOverview })));
const AdminFreshnessCountries = lazy(() => import('./pages/admin/freshness/AdminFreshnessCountries').then((module) => ({ default: module.AdminFreshnessCountries })));
const AdminFreshnessCities = lazy(() => import('./pages/admin/freshness/AdminFreshnessCities').then((module) => ({ default: module.AdminFreshnessCities })));
const AdminFreshnessSources = lazy(() => import('./pages/admin/freshness/AdminFreshnessSources').then((module) => ({ default: module.AdminFreshnessSources })));
const AdminFreshnessChanges = lazy(() => import('./pages/admin/freshness/AdminFreshnessChanges').then((module) => ({ default: module.AdminFreshnessChanges })));
const AdminFreshnessStaleContent = lazy(() => import('./pages/admin/freshness/AdminFreshnessStaleContent').then((module) => ({ default: module.AdminFreshnessStaleContent })));
const AdminCrawlSchedules = lazy(() => import('./pages/admin/freshness/AdminCrawlSchedules').then((module) => ({ default: module.AdminCrawlSchedules })));
const AdminCrawlJobRuns = lazy(() => import('./pages/admin/freshness/AdminCrawlJobRuns').then((module) => ({ default: module.AdminCrawlJobRuns })));
const AdminCrawlJobRunDetail = lazy(() => import('./pages/admin/freshness/AdminCrawlJobRunDetail').then((module) => ({ default: module.AdminCrawlJobRunDetail })));
const AdminReviewQueuePage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueuePage').then((module) => ({ default: module.AdminReviewQueuePage })));
const AdminReviewQueueDetailPage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueueDetailPage').then((module) => ({ default: module.AdminReviewQueueDetailPage })));
const AdminReviewQueueWorkloadPage = lazy(() => import('./pages/admin/review-queue/AdminReviewQueueWorkloadPage').then((module) => ({ default: module.AdminReviewQueueWorkloadPage })));
const AdminOpsSlaPage = lazy(() => import('./pages/admin/ops/AdminOpsSlaPage').then((module) => ({ default: module.AdminOpsSlaPage })));
const AdminOpsQueuePage = lazy(() => import('./pages/admin/ops/AdminOpsQueuePage').then((module) => ({ default: module.AdminOpsQueuePage })));
const AdminOpsReviewersPage = lazy(() => import('./pages/admin/ops/AdminOpsReviewersPage').then((module) => ({ default: module.AdminOpsReviewersPage })));
const AdminOpsDestinationsPage = lazy(() => import('./pages/admin/ops/AdminOpsDestinationsPage').then((module) => ({ default: module.AdminOpsDestinationsPage })));
const AdminOpsNotificationsPage = lazy(() => import('./pages/admin/ops/AdminOpsNotificationsPage').then((module) => ({ default: module.AdminOpsNotificationsPage })));

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
    <Router>
      <ScrollToTop />
      <DemoBookingProvider>
      <SelectedCaseProvider>
      <EmployeeAssignmentProvider>
      <HrCompanyContextProvider>
      <ServicesFlowProvider>
      <QueryRedirect />
      <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path={ROUTE_DEFS.landing.path} element={<Landing />} />
        <Route path={ROUTE_DEFS.platform.path} element={<PlatformPage />} />
        <Route path={ROUTE_DEFS.why.path} element={<WhyReloPassPage />} />
        <Route path={ROUTE_DEFS.trust.path} element={<TrustPage />} />
        <Route path={ROUTE_DEFS.access.path} element={<AccessPage />} />
        <Route path={ROUTE_DEFS.auth.path} element={<Auth />} />
        <Route path="/journey" element={<Journey />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path={ROUTE_DEFS.employeeJourney.path} element={<Navigate to={ROUTE_DEFS.employeeDashboard.path} replace />} />
        <Route path={ROUTE_DEFS.employeeDashboard.path} element={<EmployeeJourney />} />
        <Route path={WIZARD_ROUTES.EMP_DASH} element={<Navigate to={ROUTE_DEFS.employeeDashboard.path} replace />} />
        <Route path={ROUTE_DEFS.hrDashboard.path} element={<HrDashboard />} />
        <Route path={ROUTE_DEFS.hrCommandCenter.path} element={<HrCommandCenter />} />
        <Route path={ROUTE_DEFS.hrCommandCenterCase.path} element={<HrCommandCenterCaseDetail />} />
        <Route path={ROUTE_DEFS.hrEmployeeDashboard.path} element={<HrAssignmentReview />} />
        <Route path={ROUTE_DEFS.hrCaseSummary.path} element={<HrCaseSummary />} />
        <Route path={ROUTE_DEFS.hrReview.path} element={<Navigate to={ROUTE_DEFS.hrEmployeeDashboard.path} replace />} />
        <Route path={ROUTE_DEFS.hrReviewCase.path} element={<ReviewToEmployeeDashboardRedirect />} />
        <Route path={ROUTE_DEFS.hrAssignmentReview.path} element={<HrAssignmentReview />} />
        <Route path={ROUTE_DEFS.hrComplianceIndex.path} element={<HrComplianceCheck />} />
        <Route path={ROUTE_DEFS.hrCompliance.path} element={<HrComplianceCheck />} />
        <Route path={ROUTE_DEFS.hrPackage.path} element={<HrAssignmentPackageReview />} />
        {import.meta.env.DEV && (
          <Route path={ROUTE_DEFS.auditNavigation.path} element={<NavigationAudit />} />
        )}
        <Route
          path={ROUTE_DEFS.providers.path}
          element={<Navigate to={ROUTE_DEFS.services.path} replace />}
        />
        <Route
          path={ROUTE_DEFS.services.path}
          element={<ProvidersPage />}
        />
        <Route path={ROUTE_DEFS.servicesQuestions.path} element={<ServicesQuestions />} />
        <Route path={ROUTE_DEFS.servicesRecommendations.path} element={<ServicesRecommendations />} />
        <Route path={ROUTE_DEFS.servicesEstimate.path} element={<ServicesEstimate />} />
        <Route path={ROUTE_DEFS.servicesRfqNew.path} element={<ServicesRfqNew />} />
        <Route path={ROUTE_DEFS.servicesConclusion.path} element={<ServicesConclusion />} />
        <Route path={ROUTE_DEFS.quotesInbox.path} element={<QuotesInbox />} />
        <Route path={ROUTE_DEFS.quoteRfqDetail.path} element={<QuoteRfqDetail />} />
        <Route path={ROUTE_DEFS.vendorInbox.path} element={<VendorInbox />} />
        <Route path={ROUTE_DEFS.vendorRfq.path} element={<VendorRfq />} />
        <Route path={ROUTE_DEFS.hrPreferredSuppliers.path} element={<HrPreferredSuppliers />} />
        <Route path={ROUTE_DEFS.hrPolicy.path} element={<HrPolicy />} />
        <Route path={ROUTE_DEFS.employeePolicy.path} element={<EmployeePolicyPage />} />
        <Route path={ROUTE_DEFS.employeeHrPolicy.path} element={<Navigate to={ROUTE_DEFS.hrPolicy.path} replace />} />
        <Route path={ROUTE_DEFS.hrPolicyManagement.path} element={<Navigate to={ROUTE_DEFS.hrPolicy.path} replace />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD_STEP} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_REVIEW} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_SUMMARY} element={<EmployeeCaseSummary />} />
        <Route path={WIZARD_ROUTES.CASE_PLAN} element={<EmployeeRelocationPlanPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRIES} element={<CountriesPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRY_DETAIL} element={<CountryDetailPage />} />
        <Route path={ROUTE_DEFS.adminConsole.path} element={<RequireAdminRoute><AdminOverviewPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCompanies.path} element={<RequireAdminRoute><AdminCompanies /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPeople.path} element={<RequireAdminRoute><AdminUsers /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAssignments.path} element={<RequireAdminRoute><AdminAssignments /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMobilityCases.path} element={<RequireAdminRoute><AdminMobilityCaseInspectPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMobilityCaseInspect.path} element={<RequireAdminRoute><AdminMobilityCaseInspectPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPolicies.path} element={<RequireAdminRoute><AdminPoliciesPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminMessages.path} element={<RequireAdminRoute><AdminMessages /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResearch.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminOverview.path} replace /></RequireAdminRoute>} />
        <Route path="/admin/companies/:companyId" element={<RequireAdminRoute><AdminCompanyDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminUsers.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminPeople.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminRelocations.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminAssignments.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSupport.path} element={<RequireAdminRoute><Navigate to={ROUTE_DEFS.adminMessages.path} replace /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliers.path} element={<RequireAdminRoute><AdminSuppliers /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliersNew.path} element={<RequireAdminRoute><AdminSupplierNew /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminSuppliersDetail.path} element={<RequireAdminRoute><AdminSupplierDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResources.path} element={<RequireAdminRoute><AdminResources /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResourcesNew.path} element={<RequireAdminRoute><AdminResourceEditor /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminResourcesEdit.path} element={<RequireAdminRoute><AdminResourceEditor /></RequireAdminRoute>} />
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
        <Route path={ROUTE_DEFS.adminFreshnessChanges.path} element={<RequireAdminRoute><AdminFreshnessChanges /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminFreshnessStaleContent.path} element={<RequireAdminRoute><AdminFreshnessStaleContent /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlSchedules.path} element={<RequireAdminRoute><AdminCrawlSchedules /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlJobRuns.path} element={<RequireAdminRoute><AdminCrawlJobRuns /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCrawlJobRunDetail.path} element={<RequireAdminRoute><AdminCrawlJobRunDetail /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminReviewQueue.path} element={<RequireAdminRoute><AdminReviewQueuePage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminReviewQueueWorkload.path} element={<RequireAdminRoute><AdminReviewQueueWorkloadPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminReviewQueueDetail.path} element={<RequireAdminRoute><AdminReviewQueueDetailPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsSla.path} element={<RequireAdminRoute><AdminOpsSlaPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsQueue.path} element={<RequireAdminRoute><AdminOpsQueuePage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsReviewers.path} element={<RequireAdminRoute><AdminOpsReviewersPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsDestinations.path} element={<RequireAdminRoute><AdminOpsDestinationsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminOpsNotifications.path} element={<RequireAdminRoute><AdminOpsNotificationsPage /></RequireAdminRoute>} />
        <Route
          path={ROUTE_DEFS.messages.path}
          element={<Messages />}
        />
        <Route
          path={ROUTE_DEFS.resources.path}
          element={<Resources />}
        />
        <Route
          path={ROUTE_DEFS.caseResources.path}
          element={<Resources />}
        />
        <Route
          path={ROUTE_DEFS.hrMessages.path}
          element={<Messages />}
        />
        {/*
          Placeholder routes kept as dev-only. In prod they fall through to
          the catch-all (redirect to landing) — better than shipping a visible
          "coming soon" card during demos. Remove these entirely once the
          feature ships or the nav entry is retired.
        */}
        {import.meta.env.DEV && (
          <Route
            path={ROUTE_DEFS.hrResources.path}
            element={<PlaceholderPage title="Resources" description="Access HR relocation resources and guides." />}
          />
        )}
        <Route path={ROUTE_DEFS.hrCompanyProfile.path} element={<HrCompanyProfile />} />
        <Route path={ROUTE_DEFS.hrEmployees.path} element={<HrEmployees />} />
        <Route path={ROUTE_DEFS.hrEmployeeDetail.path} element={<HrEmployeeDetail />} />
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
        <Route path="*" element={<Navigate to={ROUTE_DEFS.landing.path} replace />} />
      </Routes>
      </Suspense>
      </ServicesFlowProvider>
      </HrCompanyContextProvider>
      </EmployeeAssignmentProvider>
      </SelectedCaseProvider>
      <BookDemoModal />
      </DemoBookingProvider>
      <PerfPanel />
    </Router>
    </ErrorBoundary>
  );
}

export default App;


/* import TestRpc from "./dev/TestRpc";

function App() {
  return <TestRpc />;
}

export default App; */
