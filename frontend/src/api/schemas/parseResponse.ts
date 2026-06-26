import type { z } from 'zod';
import { logger } from '../../lib/logger';

/**
 * Validate an API response at the boundary WITHOUT ever throwing.
 *
 * On a schema mismatch (backend shape drift, an unexpected null) it logs the
 * issue (dev only) and returns the RAW data — so a page never crashes on a
 * boundary mismatch, but the drift is visible for detection. The happy path
 * returns the parsed, fully-typed value.
 *
 * This deliberately uses safeParse + fallback rather than `.parse()`: a strict
 * throw on live backend data would turn a minor field drift into a white screen.
 */
export function parseResponse<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const result = schema.safeParse(data);
  if (result.success) return result.data;
  if (import.meta.env.DEV) {
    logger.warn(`[api-boundary] ${label}: response failed validation`, result.error.issues);
  }
  return data as T;
}
