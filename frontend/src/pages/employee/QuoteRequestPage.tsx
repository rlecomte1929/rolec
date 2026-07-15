/**
 * QuoteRequestPage — RETIRED redirect ([AIQ-1525]).
 *
 * This page was the category-only "tell HR which services you need, they'll coordinate
 * with vendors" flow that wrote the duplicate `quote_requests` table. That path is
 * retired in favour of the canonical employee-led RFQ flow (ServicesRfqNew → POST
 * /api/rfqs, a vendor shortlist). The route stays registered so a stray bookmark to
 * `/employee/quote-request` lands on the live flow instead of 404-ing.
 *
 * Route: /employee/quote-request  (see routes.ts → employeeQuoteRequest)
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { buildRoute } from '../../navigation/routes';

export const QuoteRequestPage: React.FC = () => {
  const { linkedSummaries, isLoading } = useEmployeeAssignment();

  // Wait for the assignment context before deciding where to send the employee.
  if (isLoading) return null;

  const caseId = linkedSummaries[0]?.case_id ?? null;
  const target = caseId
    ? buildRoute('caseServicesRfqNew', { caseId })
    : buildRoute('employeeJourney');

  return <Navigate to={target} replace />;
};
