/**
 * Case details loaded via case_assignments only (Option A access model).
 * Never query cases directly by URL param; always gate through assignment.
 */

import api from './client';
import type { CaseDTO, CaseDraftDTO } from '../types';

export interface CaseAssignment {
  id: string;
  case_id: string;
  employee_user_id: string | null;
  hr_user_id: string;
  status: string;
  employee_identifier?: string;
  /** Set by HR/Admin; used to pre-fill employee name in wizard */
  employee_full_name?: string | null;
  /** Durable graph lane id from assignment_mobility_links (not wizard flags). */
  mobility_case_id?: string | null;
}

export interface CaseDetailsResult {
  assignment: CaseAssignment;
  case: CaseDTO;
}

export interface CaseDetailsError {
  assignmentError?: string;
  caseError?: string;
  assignmentId?: string;
  caseId?: string;
}

type CaseDetailsResponse = {
  data: CaseDetailsResult | null;
  error: string | null;
  debug?: CaseDetailsError;
};

/** In-flight dedupe: wizard + summary often mount together and share the same assignment gate. */
const caseDetailsInflight = new Map<string, Promise<CaseDetailsResponse>>();

async function fetchCaseDetailsByAssignment(assignmentIdTrimmed: string): Promise<CaseDetailsResponse> {
  try {
    const res = await api.get<{ assignment: CaseAssignment; case: Record<string, unknown> }>(
      `/api/case-details-by-assignment?assignment_id=${encodeURIComponent(assignmentIdTrimmed)}`
    );
    const { assignment, case: caseData } = res.data;
    const caseDto: CaseDTO = {
      id: caseData.id as string,
      status: (caseData.status as string) || 'DRAFT',
      draft: (caseData.draft as CaseDraftDTO) || {
        relocationBasics: {},
        employeeProfile: {},
        familyMembers: {},
        assignmentContext: {},
      },
      createdAt: caseData.createdAt as string,
      updatedAt: caseData.updatedAt as string,
      originCountry: caseData.originCountry as string | undefined,
      originCity: caseData.originCity as string | undefined,
      destCountry: caseData.destCountry as string | undefined,
      destCity: caseData.destCity as string | undefined,
      purpose: caseData.purpose as string | undefined,
      targetMoveDate: caseData.targetMoveDate as string | undefined,
      flags: (caseData.flags as Record<string, unknown>) || {},
      requirementsSnapshotId: caseData.requirementsSnapshotId as string | undefined,
    };
    return {
      data: { assignment, case: caseDto },
      error: null,
    };
  } catch (err: unknown) {
    const ax = err as { response?: { status?: number; data?: { detail?: string } } };
    const status = ax?.response?.status;
    const detail = typeof ax?.response?.data?.detail === 'string'
      ? ax.response.data.detail
      : ax?.response?.data?.detail;
    let error = 'Assignment not found or not visible under RLS';
    if (status === 404) {
      const msg = String(detail || '');
      if (msg.includes('Case row missing')) {
        error = msg;
      } else {
        error = 'Assignment not found or not visible under RLS';
      }
    } else if (status === 403) {
      error = 'Assignment not found or not visible under RLS';
    } else if (detail) {
      error = typeof detail === 'string' ? detail : JSON.stringify(detail);
    }
    return {
      data: null,
      error,
      debug:
        import.meta.env.DEV
          ? {
              assignmentError: error,
              assignmentId: assignmentIdTrimmed,
              caseId: undefined,
            }
          : undefined,
    };
  }
}

/** Load case details by assignment id. Gates access via case_assignments. */
export async function getCaseDetailsByAssignmentId(
  assignmentId: string
): Promise<CaseDetailsResponse> {
  const assignmentIdTrimmed = assignmentId?.trim();
  if (!assignmentIdTrimmed) {
    return {
      data: null,
      error: 'Assignment ID is required',
      debug: import.meta.env.DEV ? { assignmentId: assignmentIdTrimmed || undefined } : undefined,
    };
  }
  const existing = caseDetailsInflight.get(assignmentIdTrimmed);
  if (existing) {
    return existing;
  }
  const promise = fetchCaseDetailsByAssignment(assignmentIdTrimmed);
  caseDetailsInflight.set(assignmentIdTrimmed, promise);
  try {
    return await promise;
  } finally {
    caseDetailsInflight.delete(assignmentIdTrimmed);
  }
}
