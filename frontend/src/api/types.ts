/**
 * Shared response/payload types for the API client (`api/client.ts`, `api/rpc.ts`).
 *
 * Convention (Epic B / client.ts typing): prefer an existing domain type in
 * `features/<domain>/types.ts` or `types/relopass-api-contracts.ts` when one matches.
 * Add a type here only when the shape is shared across multiple client methods and
 * has no existing home. One domain per slice; keep it minimal.
 */

/**
 * Error body returned by the FastAPI backend (`{ detail }`) and Supabase REST
 * (`{ message }` / `{ error }`). All fields optional — error bodies vary by source.
 */
export type ApiErrorBody = {
  detail?: string;
  message?: string;
  error?: string;
};

/**
 * Raw company-policy record + its benefit rules, as returned by the company-policy
 * CRUD endpoints (getLatest/getById/extract/saveBenefits). The entities are opaque to
 * the client — consumers cast `policy`/`benefits` to their own view types. Returned
 * shape is shared across those methods, so it lives here (Epic B decision 3).
 */
export type CompanyPolicyResult = {
  policy: unknown;
  benefits: unknown[];
  company_name?: string;
};
