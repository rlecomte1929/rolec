/**
 * Characterisation of the adminAPI client surface before splitting client.ts (WS3 Task 3.8 slice 1).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import { adminAPI as adminAPIFromModule } from '../adminApi';
import { adminAPI } from '../client';

const ADMIN_API_METHODS = [
  'getContext',
  'startImpersonation',
  'stopImpersonation',
  'listCompanies',
  'getCompanyDetail',
  'createCompany',
  'updateCompany',
  'deactivateCompany',
  'archiveCompany',
  'deleteCompany',
  'runReconciliationBackfillTestCompany',
  'rebuildTestCompanyGraph',
  'listProfiles',
  'listPeople',
  'createPerson',
  'updatePerson',
  'assignPersonCompany',
  'setPersonRole',
  'deactivatePerson',
  'listEmployees',
  'listHrUsers',
  'listRelocations',
  'listAssignments',
  'getAssignmentDetail',
  'reassignEmployeeCompany',
  'reassignHrOwner',
  'fixAssignmentCompanyLinkage',
  'updateAssignmentStatus',
  'overrideEligibility',
  'unlockCase',
  'createAssignment',
  'listPolicyOverview',
  'listAdminPolicies',
  'getAdminPolicyDetail',
  'getAdminPolicyVersions',
  'patchAdminPolicy',
  'listAdminPolicyTemplates',
  'applyDefaultTemplateToCompany',
  'getPolicyAssistantCompanyHistory',
  'getPolicyAssistantSnapshotDiff',
  'listPolicyAssistantAnswerAudits',
  'listSupportCases',
  'patchSupportCase',
  'listMessageThreads',
  'getHrThreadDetail',
  'listSupportNotes',
  'addSupportNote',
  'adminAction',
  'getReconciliationReport',
  'reconciliationLinkPersonCompany',
  'reconciliationLinkAssignmentCompany',
  'reconciliationLinkAssignmentPerson',
  'reconciliationLinkPolicyCompany',
  'listResearchCandidates',
  'researchHealth',
  'approveResearchCandidate',
  'ingestUrl',
  'ingestBatch',
  'listIngestJobs',
  'listKnowledgeDocs',
  'listRequirementEntities',
  'listRequirementFacts',
  'listRequirementCriteria',
  'approveRequirementFacts',
  'rejectRequirementFacts',
  'inspectMobilityCase',
  'evaluateMobilityAssignmentRequirements',
  'analyzePolicy',
] as const;

describe('adminAPI surface', () => {
  it('exposes the characterised method names', () => {
    expect(Object.keys(adminAPI).sort()).toEqual([...ADMIN_API_METHODS].sort());
  });

  it('re-exports the same object as adminApi.ts', () => {
    expect(adminAPI).toBe(adminAPIFromModule);
  });
});
