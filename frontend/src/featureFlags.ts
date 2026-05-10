/**
 * Frontend feature flags. Reads from VITE_ env vars so the value is fixed at
 * build time. Add new flags here so the rest of the app has one place to look.
 *
 * Convention: a flag is enabled only when the env var equals the literal
 * string `'true'`. Anything else (undefined, '', '1', 'yes') is OFF — keeps
 * production safe by default when ops forget to set the var.
 */

const isOn = (raw: unknown): boolean =>
  typeof raw === 'string' && raw.trim().toLowerCase() === 'true';

/**
 * Quotes / RFQ surface. OFF by default — the workflow is incomplete and is
 * deferred behind ExceptionRequest (T1.3) per the Sprint 1 execution plan.
 * Set `VITE_ENABLE_RFQ=true` in `.env.local` to bring it back for dev.
 */
export const isRfqEnabled = (): boolean => isOn(import.meta.env.VITE_ENABLE_RFQ);

/**
 * Section C of HR Policy: per-(jurisdiction × employee_level × assignment_type)
 * overrides on benefit rows. The editor renders inside the benefit-edit drawer
 * so HR can author region-specific caps. Backend stack (resolver, endpoints,
 * persistence) ships in PRs #66 / #68; this flag gates the editor UI.
 *
 * Set `VITE_FEATURE_SECTION_C_OVERRIDES=true` in `.env.local` to enable for dev.
 */
export const isSectionCOverridesEnabled = (): boolean =>
  isOn(import.meta.env.VITE_FEATURE_SECTION_C_OVERRIDES);
