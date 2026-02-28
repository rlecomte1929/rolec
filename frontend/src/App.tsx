import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { SelectedCaseProvider } from './contexts/SelectedCaseContext';
import { EmployeeAssignmentProvider } from './contexts/EmployeeAssignmentContext';
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
import { HrPolicy } from './pages/HrPolicy';
import { HrPolicyManagement } from './pages/HrPolicyManagement';
import { CaseWizardPage } from './pages/employee/CaseWizardPage';
import { EmployeeCaseSummary } from './pages/employee/EmployeeCaseSummary';
import { CountriesPage } from './pages/admin/CountriesPage';
import { CountryDetailPage } from './pages/admin/CountryDetailPage';
import { AdminDashboard } from './pages/admin/AdminDashboard';
import { AdminCompanies } from './pages/admin/AdminCompanies';
import { AdminUsers } from './pages/admin/AdminUsers';
import { AdminRelocations } from './pages/admin/AdminRelocations';
import { AdminSupport } from './pages/admin/AdminSupport';
import { AdminCompanyDetail } from './pages/admin/AdminCompanyDetail';
import { AdminResearch } from './pages/admin/AdminResearch';
import { ROUTES as WIZARD_ROUTES } from './routes';
import { NavigationAudit } from './pages/NavigationAudit';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { ProvidersPage } from './pages/ProvidersPage';
import { DebugAuth } from './pages/DebugAuth';
import { AssignmentDebugPage } from './pages/AssignmentDebugPage';
import { Messages } from './pages/Messages';
import { Resources } from './pages/Resources';
import { HrCompanyProfile } from './pages/HrCompanyProfile';
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

function App() {
  return (
    <ErrorBoundary>
    <Router>
      <SelectedCaseProvider>
      <EmployeeAssignmentProvider>
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
          element={<ProvidersPage />}
        />
        <Route path={ROUTE_DEFS.hrPolicy.path} element={<HrPolicy />} />
        <Route path={ROUTE_DEFS.hrPolicyManagement.path} element={<HrPolicyManagement />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD_STEP} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_REVIEW} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_SUMMARY} element={<EmployeeCaseSummary />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRIES} element={<CountriesPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRY_DETAIL} element={<CountryDetailPage />} />
        <Route path={ROUTE_DEFS.adminConsole.path} element={<AdminDashboard />} />
        <Route path={ROUTE_DEFS.adminCompanies.path} element={<AdminCompanies />} />
        <Route path={ROUTE_DEFS.adminResearch.path} element={<AdminResearch />} />
        <Route path="/admin/companies/:companyId" element={<AdminCompanyDetail />} />
        <Route path={ROUTE_DEFS.adminUsers.path} element={<AdminUsers />} />
        <Route path={ROUTE_DEFS.adminRelocations.path} element={<AdminRelocations />} />
        <Route path={ROUTE_DEFS.adminSupport.path} element={<AdminSupport />} />
        <Route
          path={ROUTE_DEFS.messages.path}
          element={<Messages />}
        />
        <Route
          path={ROUTE_DEFS.resources.path}
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