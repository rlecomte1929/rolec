import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { SelectedCaseProvider } from './contexts/SelectedCaseContext';
import { EmployeeAssignmentProvider } from './contexts/EmployeeAssignmentContext';
import { ServicesFlowProvider } from './features/services/ServicesFlowContext';
import { ROUTE_DEFS } from './navigation/routes';
import { Landing } from './pages/Landing';
import { Auth } from './pages/Auth';
import { Journey } from './pages/Journey';
import { Dashboard } from './pages/Dashboard';
import { EmployeeJourney } from './pages/EmployeeJourney';
import { HrDashboard } from './pages/HrDashboard';
import { HrCaseSummary } from './pages/HrCaseSummary';
import { HrAssignmentReview } from './pages/HrAssignmentReview';
import { HrComplianceCheck } from './pages/HrComplianceCheck';
import { HrAssignmentPackageReview } from './pages/HrAssignmentPackageReview';
import { HrPreferredSuppliers } from './pages/HrPreferredSuppliers';
import { HrPolicy } from './pages/HrPolicy';
import { HrPolicyManagement } from './pages/HrPolicyManagement';
import { CaseWizardPage } from './pages/employee/CaseWizardPage';
import { EmployeeCaseSummary } from './pages/employee/EmployeeCaseSummary';
import { CountriesPage } from './pages/admin/CountriesPage';
import { CountryDetailPage } from './pages/admin/CountryDetailPage';
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage';
import { AdminPoliciesPage } from './pages/admin/AdminPoliciesPage';
import { AdminCompanies } from './pages/admin/AdminCompanies';
import { AdminUsers } from './pages/admin/AdminUsers';
import { AdminAssignments } from './pages/admin/AdminAssignments';
import { AdminMessages } from './pages/admin/AdminMessages';
import { AdminSuppliers } from './pages/admin/AdminSuppliers';
import { AdminSupplierNew } from './pages/admin/AdminSupplierNew';
import { AdminSupplierDetail } from './pages/admin/AdminSupplierDetail';
import { AdminCompanyDetail } from './pages/admin/AdminCompanyDetail';
import { RequireAdminRoute } from './features/admin/RequireAdminRoute';
import { AdminResources } from './pages/admin/AdminResources';
import { AdminResourceEditor } from './pages/admin/AdminResourceEditor';
import { AdminEvents } from './pages/admin/AdminEvents';
import { AdminEventEditor } from './pages/admin/AdminEventEditor';
import { AdminCategories } from './pages/admin/AdminCategories';
import { AdminTags } from './pages/admin/AdminTags';
import { AdminSources } from './pages/admin/AdminSources';
import { AdminStagingDashboard } from './pages/admin/staging/AdminStagingDashboard';
import { AdminStagingResources } from './pages/admin/staging/AdminStagingResources';
import { AdminStagingResourceDetail } from './pages/admin/staging/AdminStagingResourceDetail';
import { AdminStagingEvents } from './pages/admin/staging/AdminStagingEvents';
import { AdminStagingEventDetail } from './pages/admin/staging/AdminStagingEventDetail';
import { AdminFreshnessOverview } from './pages/admin/freshness/AdminFreshnessOverview';
import { AdminFreshnessCountries } from './pages/admin/freshness/AdminFreshnessCountries';
import { AdminFreshnessCities } from './pages/admin/freshness/AdminFreshnessCities';
import { AdminFreshnessSources } from './pages/admin/freshness/AdminFreshnessSources';
import { AdminFreshnessChanges } from './pages/admin/freshness/AdminFreshnessChanges';
import { AdminFreshnessStaleContent } from './pages/admin/freshness/AdminFreshnessStaleContent';
import { AdminCrawlSchedules } from './pages/admin/freshness/AdminCrawlSchedules';
import { AdminCrawlJobRuns } from './pages/admin/freshness/AdminCrawlJobRuns';
import { AdminCrawlJobRunDetail } from './pages/admin/freshness/AdminCrawlJobRunDetail';
import { AdminReviewQueuePage } from './pages/admin/review-queue/AdminReviewQueuePage';
import { AdminReviewQueueDetailPage } from './pages/admin/review-queue/AdminReviewQueueDetailPage';
import { AdminReviewQueueWorkloadPage } from './pages/admin/review-queue/AdminReviewQueueWorkloadPage';
import { AdminNotificationsPage } from './pages/admin/AdminNotificationsPage';
import { AdminNotificationDetailPage } from './pages/admin/AdminNotificationDetailPage';
import { AdminOpsSlaPage } from './pages/admin/ops/AdminOpsSlaPage';
import { AdminOpsQueuePage } from './pages/admin/ops/AdminOpsQueuePage';
import { AdminOpsReviewersPage } from './pages/admin/ops/AdminOpsReviewersPage';
import { AdminOpsDestinationsPage } from './pages/admin/ops/AdminOpsDestinationsPage';
import { AdminOpsNotificationsPage } from './pages/admin/ops/AdminOpsNotificationsPage';
import { ROUTES as WIZARD_ROUTES } from './routes';
import { NavigationAudit } from './pages/NavigationAudit';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { ProvidersPage } from './pages/ProvidersPage';
import { DebugAuth } from './pages/DebugAuth';
import { AssignmentDebugPage } from './pages/AssignmentDebugPage';
import { Messages } from './pages/Messages';
import { Resources } from './pages/Resources';
import { ServicesQuestions } from './pages/services/ServicesQuestions';
import { ServicesRecommendations } from './pages/services/ServicesRecommendations';
import { ServicesEstimate } from './pages/services/ServicesEstimate';
import { ServicesRfqNew } from './pages/services/ServicesRfqNew';
import { ServicesConclusion } from './pages/services/ServicesConclusion';
import { QuotesInbox } from './pages/services/QuotesInbox';
import { QuoteRfqDetail } from './pages/services/QuoteRfqDetail';
import { VendorInbox } from './pages/vendor/VendorInbox';
import { VendorRfq } from './pages/vendor/VendorRfq';
import { HrCompanyProfile } from './pages/HrCompanyProfile';
import { HrEmployees } from './pages/HrEmployees';
import { HrEmployeeDetail } from './pages/HrEmployeeDetail';
import { HrCommandCenter } from './pages/HrCommandCenter';
import { HrCommandCenterCaseDetail } from './pages/HrCommandCenterCaseDetail';
import { NotificationSettings } from './pages/NotificationSettings';
import { PerfPanel } from './components/PerfPanel';

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
      <SelectedCaseProvider>
      <EmployeeAssignmentProvider>
      <ServicesFlowProvider>
      <QueryRedirect />
      <Routes>
        <Route path={ROUTE_DEFS.landing.path} element={<Landing />} />
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
        <Route path={ROUTE_DEFS.auditNavigation.path} element={<NavigationAudit />} />
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
        <Route path={ROUTE_DEFS.employeeHrPolicy.path} element={<Navigate to={ROUTE_DEFS.hrPolicy.path} replace />} />
        <Route path={ROUTE_DEFS.hrPolicyManagement.path} element={<HrPolicyManagement />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD_STEP} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_REVIEW} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_SUMMARY} element={<EmployeeCaseSummary />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRIES} element={<CountriesPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRY_DETAIL} element={<CountryDetailPage />} />
        <Route path={ROUTE_DEFS.adminConsole.path} element={<RequireAdminRoute><AdminOverviewPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminCompanies.path} element={<RequireAdminRoute><AdminCompanies /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminPeople.path} element={<RequireAdminRoute><AdminUsers /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminAssignments.path} element={<RequireAdminRoute><AdminAssignments /></RequireAdminRoute>} />
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
        <Route path={ROUTE_DEFS.adminNotifications.path} element={<RequireAdminRoute><AdminNotificationsPage /></RequireAdminRoute>} />
        <Route path={ROUTE_DEFS.adminNotificationDetail.path} element={<RequireAdminRoute><AdminNotificationDetailPage /></RequireAdminRoute>} />
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
        <Route
          path={ROUTE_DEFS.hrResources.path}
          element={<PlaceholderPage title="Resources" description="Access HR relocation resources and guides." />}
        />
        <Route path={ROUTE_DEFS.hrCompanyProfile.path} element={<HrCompanyProfile />} />
        <Route path={ROUTE_DEFS.hrEmployees.path} element={<HrEmployees />} />
        <Route path={ROUTE_DEFS.hrEmployeeDetail.path} element={<HrEmployeeDetail />} />
        <Route path={ROUTE_DEFS.notificationSettings.path} element={<NotificationSettings />} />
        <Route
          path={ROUTE_DEFS.submissionCenter.path}
          element={<PlaceholderPage title="Submission Center" description="Finalize and submit case documentation." />}
        />
        {import.meta.env.DEV && (
          <>
            <Route path="/debug/auth" element={<DebugAuth />} />
            <Route path="/debug/assignment" element={<AssignmentDebugPage />} />
          </>
        )}
        <Route path="*" element={<Navigate to={ROUTE_DEFS.landing.path} replace />} />
      </Routes>
      </ServicesFlowProvider>
      </EmployeeAssignmentProvider>
      </SelectedCaseProvider>
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