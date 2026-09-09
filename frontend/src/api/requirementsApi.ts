import { api } from './client';

/**
 * [AIQ-1821] `GET /api/requirements/sufficiency` returns HTTP 200 for BOTH degraded states,
 * so callers must branch on `compute_status`, never on the HTTP status:
 *  - 'ok'                — the computation ran. Empty arrays mean "we hold no verified
 *                          requirements for this corridor", NOT "nothing is required of you".
 *  - 'insufficient_data' — the case lacks the inputs to compute.
 *  - 'unavailable'       — something upstream broke.
 */
export type RequirementsComputeStatus = 'ok' | 'insufficient_data' | 'unavailable';

/** One approved requirement fact, with the official source it was extracted from. */
export interface SupportingRequirement {
  fact_id: string;
  fact_text: string;
  source_url: string;
  /**
   * [AIQ-2132] Whether we confirmed the quoted wording appears on the cited page.
   * `'verified'` = checked verbatim; `'unverified'` = never checked (the serving guard in
   * PR #1851 already excludes citations we have DISPROVED). Optional because a payload
   * predating this field must fall to the weaker claim, never borrow the stronger one.
   */
  citation_status?: 'verified' | 'unverified';
  /**
   * Whether the source states this as a flat rule or only under a condition it does not itself
   * determine. Two ES→IE records assert an entry-visa SEQUENCE while the visa-required
   * determination lives in a separate ISD lookup; rendering them flat would tell a mover she
   * is visa-required when the cited page never says so. Optional, and absent falls to
   * `'assertion'` — the plain reading of a fact we hold no condition for.
   */
  assertion_mode?: 'assertion' | 'conditional' | null;
  /** The condition a `conditional` fact hangs on, in the batch's own words. */
  conditional_on?: string | null;
  /**
   * An easy-to-miss trap — the skattekort-before-first-pay class, where the cost of not
   * knowing is high and nothing prompts you. 16 of the 38 ES→IE records carry this.
   */
  non_obvious?: boolean;
  /** Profile fields this fact implies we need. Keys of the case profile snapshot. */
  required_fields: string[];
}

export interface RequirementsSufficiency {
  compute_status: RequirementsComputeStatus;
  /** Non-null only when compute_status !== 'ok'. */
  message: string | null;
  /** Raw as stored on the case — normalised server-side but not guaranteed ISO-2. */
  destination_country: string | null;
  /** Profile fields still unanswered. INTAKE completeness — not legal obligations. */
  missing_fields: string[];
  supporting_requirements: SupportingRequirement[];
}

export const requirementsAPI = {
  getSufficiency: async (caseId: string): Promise<RequirementsSufficiency> => {
    const response = await api.get<RequirementsSufficiency>('/api/requirements/sufficiency', {
      params: { case_id: caseId },
    });
    return response.data;
  },
};
