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
 * Quotes / RFQ surface. Controls the RFQ tab in the Services nav ribbon.
 * The core workflow (ServicesRfqNew + rfqAPI) is shipped; set this to `true`
 * to surface the ribbon tab.  Step 4 in EmployeeJourney is always shown once
 * the employee has shortlisted services (independent of this flag).
 * Set `VITE_ENABLE_RFQ=true` in `.env.local` to enable the ribbon tab.
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
