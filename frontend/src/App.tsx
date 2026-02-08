import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
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
import { CaseWizardPage } from './pages/employee/CaseWizardPage';
import { CountriesPage } from './pages/admin/CountriesPage';
import { CountryDetailPage } from './pages/admin/CountryDetailPage';
import { ROUTES as WIZARD_ROUTES } from './routes';
import { NavigationAudit } from './pages/NavigationAudit';
import { PlaceholderPage } from './pages/PlaceholderPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path={ROUTE_DEFS.landing.path} element={<Landing />} />
        <Route path={ROUTE_DEFS.auth.path} element={<Auth />} />
        <Route path="/journey" element={<Journey />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path={ROUTE_DEFS.employeeJourney.path} element={<EmployeeJourney />} />
        <Route path={WIZARD_ROUTES.EMP_DASH} element={<EmployeeJourney />} />
        <Route path={ROUTE_DEFS.hrDashboard.path} element={<HrDashboard />} />
        <Route path={ROUTE_DEFS.hrEmployeeDashboard.path} element={<HrAssignmentReview />} />
        <Route path={ROUTE_DEFS.hrCaseSummary.path} element={<HrCaseSummary />} />
        <Route path={ROUTE_DEFS.hrAssignmentReview.path} element={<HrAssignmentReview />} />
        <Route path={ROUTE_DEFS.hrComplianceIndex.path} element={<HrComplianceCheck />} />
        <Route path={ROUTE_DEFS.hrCompliance.path} element={<HrComplianceCheck />} />
        <Route path={ROUTE_DEFS.hrPackage.path} element={<HrAssignmentPackageReview />} />
        <Route path={ROUTE_DEFS.auditNavigation.path} element={<NavigationAudit />} />
        <Route
          path={ROUTE_DEFS.providers.path}
          element={<PlaceholderPage title="Providers" description="Browse relocation providers and service partners." />}
        />
        <Route
          path={ROUTE_DEFS.hrPolicy.path}
          element={<HrPolicy />}
        />
        <Route path={WIZARD_ROUTES.CASE_WIZARD} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_WIZARD_STEP} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.CASE_REVIEW} element={<CaseWizardPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRIES} element={<CountriesPage />} />
        <Route path={WIZARD_ROUTES.ADMIN_COUNTRY_DETAIL} element={<CountryDetailPage />} />
        <Route
          path={ROUTE_DEFS.messages.path}
          element={<PlaceholderPage title="Messages" description="Review case communications and updates." />}
        />
        <Route
          path={ROUTE_DEFS.resources.path}
          element={<PlaceholderPage title="Resources" description="Access relocation resources and guides." />}
        />
        <Route
          path={ROUTE_DEFS.hrMessages.path}
          element={<PlaceholderPage title="Messages" description="Review HR case communications and updates." />}
        />
        <Route
          path={ROUTE_DEFS.hrResources.path}
          element={<PlaceholderPage title="Resources" description="Access HR relocation resources and guides." />}
        />
        <Route
          path={ROUTE_DEFS.submissionCenter.path}
          element={<PlaceholderPage title="Submission Center" description="Finalize and submit case documentation." />}
        />
        <Route path="*" element={<Navigate to={ROUTE_DEFS.landing.path} replace />} />
      </Routes>
    </Router>
  );
}

export default App;
