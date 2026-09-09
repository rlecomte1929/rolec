/**
 * Characterisation of the policy API cluster before splitting client.ts (WS3 Task 3.8 slice 6).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import {
  companyPolicyAPI as companyPolicyAPIFromModule,
  hrPolicyReviewAPI as hrPolicyReviewAPIFromModule,
  policyConfigMatrixAPI as policyConfigMatrixAPIFromModule,
  policyDocumentsAPI as policyDocumentsAPIFromModule,
} from '../policyApi';
import {
  companyPolicyAPI,
  hrPolicyReviewAPI,
  policyConfigMatrixAPI,
  policyDocumentsAPI,
} from '../client';

const POLICY_CONFIG_MATRIX_API_METHODS = [
  'hrGet',
  'hrPostDraft',
  'hrPutDraft',
  'hrGenerate',
  'hrPublish',
  'hrHistory',
  'hrPublished',
  'hrGetVersion',
  'hrListTemplates',
  'hrApplyTemplate',
  'hrDiff',
  'hrRevertRow',
  'hrImportExtraction',
  'adminGet',
  'adminPostDraft',
  'adminPutDraft',
  'adminPublish',
  'adminHistory',
  'adminPublished',
  'adminGetVersion',
  'employeeGet',
  'hrCompareProviderEstimates',
] as const;

const COMPANY_POLICY_API_METHODS = [
  'list',
  'getLatest',
  'getById',
  'getDownloadUrl',
  'upload',
  'extract',
  'saveBenefits',
  'getNormalized',
  'patchBenefitRule',
  'patchHrBenefitOverride',
  'deleteHrBenefitOverride',
  'patchVersionStatus',
  'patchLatestVersionStatus',
  'publishVersion',
  'unpublishVersion',
  'hrCanonicalDiffForCompany',
  'publishLatestVersion',
  'patchExclusion',
  'patchCondition',
  'initializeFromTemplate',
] as const;

const HR_POLICY_REVIEW_API_METHODS = ['get'] as const;

const POLICY_DOCUMENTS_API_METHODS = [
  'health',
  'list',
  'get',
  'upload',
  'reprocess',
  'listClauses',
  'getClause',
  'patchClause',
  'normalize',
  'bulkDelete',
] as const;

describe('policy API cluster surface', () => {
  it('exposes the characterised policyConfigMatrixAPI method names', () => {
    expect(Object.keys(policyConfigMatrixAPI).sort()).toEqual([...POLICY_CONFIG_MATRIX_API_METHODS].sort());
  });

  it('re-exports the same policyConfigMatrixAPI object as policyApi.ts', () => {
    expect(policyConfigMatrixAPI).toBe(policyConfigMatrixAPIFromModule);
  });

  it('exposes the characterised companyPolicyAPI method names', () => {
    expect(Object.keys(companyPolicyAPI).sort()).toEqual([...COMPANY_POLICY_API_METHODS].sort());
  });

  it('re-exports the same companyPolicyAPI object as policyApi.ts', () => {
    expect(companyPolicyAPI).toBe(companyPolicyAPIFromModule);
  });

  it('exposes the characterised hrPolicyReviewAPI method names', () => {
    expect(Object.keys(hrPolicyReviewAPI).sort()).toEqual([...HR_POLICY_REVIEW_API_METHODS].sort());
  });

  it('re-exports the same hrPolicyReviewAPI object as policyApi.ts', () => {
    expect(hrPolicyReviewAPI).toBe(hrPolicyReviewAPIFromModule);
  });

  it('exposes the characterised policyDocumentsAPI method names', () => {
    expect(Object.keys(policyDocumentsAPI).sort()).toEqual([...POLICY_DOCUMENTS_API_METHODS].sort());
  });

  it('re-exports the same policyDocumentsAPI object as policyApi.ts', () => {
    expect(policyDocumentsAPI).toBe(policyDocumentsAPIFromModule);
  });
});
