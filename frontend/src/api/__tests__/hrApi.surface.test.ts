/**
 * Characterisation of the hrAPI client surface before splitting client.ts (WS3 Task 3.8 slice 2).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import { hrAPI as hrAPIFromModule } from '../hrApi';
import { hrAPI } from '../client';

const HR_API_METHODS = [
  'getBacklog',
  'optimizeBenefitMix',
  'createCase',
  'assignCase',
  'listAssignments',
  'getCaseHealth',
  'getAssignment',
  'getReadinessSummary',
  'getReadinessDetail',
  'patchReadinessChecklistItem',
  'patchReadinessMilestone',
  'getResolvedPolicy',
  'recomputeResolvedPolicy',
  'getPolicyServiceComparison',
  'getAssignmentServices',
  'getPolicy',
  'requestPolicyException',
  'getCompanyProfile',
  'getInferredOnboardingConfig',
  'listCompanyEmployees',
  'getEmployee',
  'updateEmployee',
  'deleteEmployee',
  'saveCompanyProfile',
  'uploadCompanyLogo',
  'removeCompanyLogo',
  'listMessages',
  'sendMessage',
  'listMessageConversations',
  'getMessageThread',
  'archiveMessageConversations',
  'deleteHrMessage',
  'getCaseCompliance',
  'runCaseCompliance',
  'recordComplianceAction',
  'runCompliance',
  'decide',
  'updateIdentifier',
  'deleteAssignment',
  'postFeedback',
  'getFeedback',
  'getCommandCenterKPIs',
  'listCommandCenterCases',
  'getCommandCenterCaseDetail',
  'getCasePredictedDuration',
  'getProviderStatusGrid',
  'postPolicyAssistantQuery',
  'getServiceCategories',
  'getVendorPerformance',
  'assignVendorToCase',
  'getCaseVendors',
  'updateCaseVendorStatus',
  'unassignVendorFromCase',
  'getVendors',
  'getVendorCorridors',
  'getImmigrationRequirements',
  'getImmigrationInterviewStatus',
  'listImmigrationMilestones',
  'createImmigrationMilestone',
  'updateImmigrationMilestone',
  'listErasureRequests',
  'processErasureRequest',
  'getCaseTasks',
  'reviewTask',
  'addCaseTask',
  'getAnalytics',
  'getDraftCase',
  'listCalibrationAlerts',
  'dismissCalibrationAlert',
] as const;

describe('hrAPI surface', () => {
  it('exposes the characterised method names', () => {
    expect(Object.keys(hrAPI).sort()).toEqual([...HR_API_METHODS].sort());
  });

  it('re-exports the same object as hrApi.ts', () => {
    expect(hrAPI).toBe(hrAPIFromModule);
  });
});
