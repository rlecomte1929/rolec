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

/**
 * AIQ-1415 — Natural-Language Policy Builder. Gates the "Describe" tab on the HR
 * Policy page where HR types a plain-English description and Claude generates a
 * config-matrix draft for confirm-before-save. The backend also gates per-account
 * (the `nl_policy_builder` feature flag), so both must be on to use it.
 *
 * Set `VITE_ENABLE_NL_POLICY_BUILDER=true` to surface the tab.
 */
export const isNlPolicyBuilderEnabled = (): boolean =>
  isOn(import.meta.env.VITE_ENABLE_NL_POLICY_BUILDER);

/**
 * AIQ-1414 — persistent Mobility Coordinator chat panel on the case pages (HR +
 * employee). The backend also gates it (`RELOPASS_AI_COORDINATOR_ENABLED`), so both
 * must be on; the panel also self-hides if the API 404s (defense in depth). Kept OFF
 * until the coordinator's UI is ready to surface.
 *
 * Set `VITE_FEATURE_COORDINATOR=true` to render the panel.
 */
export const isCoordinatorEnabled = (): boolean =>
  isOn(import.meta.env.VITE_FEATURE_COORDINATOR);

/**
 * Feedback "Trigger fix" / "Auto-attempt" actions on a dispatched feedback row
 * (admin Feedback console). Once a row is dispatched to the Notion AI Work Queue,
 * these let an admin manually flip it to "Ready for AI" (with the /relopass-dev-queue
 * command) or fire the autofix pipeline. The backend also gates it
 * (`FEEDBACK_FIX_TRIGGER_ENABLED`), so both must be on.
 *
 * Set `VITE_FEATURE_FEEDBACK_FIX=true` to surface the buttons.
 */
export const isTriggerFixEnabled = (): boolean =>
  isOn(import.meta.env.VITE_FEATURE_FEEDBACK_FIX);

/**
 * Employee AcroForm auto-fill page (form-fill Phase 1). Surfaces
 * `/employee/case/:caseId/immigration/forms`, where the employee generates a pre-filled copy of
 * the real government visa form (e.g. the France-Visas CERFA) from their case data and downloads
 * it. Kept OFF until the official form PDFs are uploaded to the `form-templates` bucket — until
 * then generate-form 404s per form (no template), which the page reports honestly.
 *
 * Set `VITE_ENABLE_IMMIGRATION_FORMS=true` to surface the page + its entry link.
 */
export const isImmigrationFormsEnabled = (): boolean =>
  isOn(import.meta.env.VITE_ENABLE_IMMIGRATION_FORMS);

// [AIQ-2142] The roadmap paywall is no longer a client build flag. Whether a case's roadmap
// is gated is served as data by GET /api/payment/status/:caseId (`entitlement`), decided by
// the server behind its own RELOPASS_ROADMAP_PAYWALL_ENABLED switch. The client reads that
// served state, never a client-side build constant — one switch, server-side, not two.
