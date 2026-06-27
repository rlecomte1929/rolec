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
