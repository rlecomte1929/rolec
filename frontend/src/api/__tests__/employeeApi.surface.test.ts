/**
 * Characterisation of the employeeAPI client surface before splitting client.ts (WS3 Task 3.8 slice 3).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import { employeeAPI as employeeAPIFromModule } from '../employeeApi';
import { employeeAPI } from '../client';

const EMPLOYEE_API_METHODS = [
  'getCurrentAssignment',
  'getAssignmentsOverview',
  'listMessages',
  'sendMessage',
  'claimAssignment',
  'claimByToken',
  'updateIntakeProgress',
  'getIntake',
  'updateIntakeDraft',
  'linkPendingAssignment',
  'getNextQuestion',
  'getFeedback',
  'submitAnswer',
  'submitAssignment',
  'updateProfilePhoto',
  'getRecommendations',
  'getPolicyCaps',
  'getAssignmentServices',
  'saveAssignmentServices',
  'getServicesPolicyContext',
  'getPolicyBudget',
  'getApplicablePolicy',
  'getResolvedPolicy',
  'getMyAssignmentPackagePolicy',
  'getPolicyEnvelope',
  'getPolicyServiceComparison',
  'postPolicyAssistantQuery',
  'listMyQuoteRequests',
  'exportPolicySessionPdf',
] as const;

describe('employeeAPI surface', () => {
  it('exposes the characterised method names', () => {
    expect(Object.keys(employeeAPI).sort()).toEqual([...EMPLOYEE_API_METHODS].sort());
  });

  it('re-exports the same object as employeeApi.ts', () => {
    expect(employeeAPI).toBe(employeeAPIFromModule);
  });
});
