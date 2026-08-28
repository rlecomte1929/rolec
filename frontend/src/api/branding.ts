/**
 * GAP 10: Company branding config — GET /api/company/branding-config
 *                                    PUT /api/company/branding-config
 *
 * Returns company-level branding for white-labelling the employee portal.
 * Used by AppShell, the employee dashboard header, and the onboarding screens.
 *
 * Always returns 200 — null fields mean "use ReloPass defaults".
 */
import { apiGet, apiPut } from './client';

export interface BrandingConfig {
  /**
   * UNUSED. The endpoint returns these on every page load and nothing reads them:
   * applyBrandingCssVars only applies the colour vars. The company logo that DOES render
   * (CompanyBrand in the sidebar) comes from a different source — the HR company profile's
   * `company.logo_url`. Either wire these up or stop returning them; do not assume they
   * are live.
   */
  logo_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
  primary_colour: string | null;
  secondary_colour: string | null;
  accent_colour: string | null;
  company_name_override: string | null;
  welcome_message: string | null;
  footer_text: string | null;
  custom_support_email: string | null;
  custom_support_url: string | null;
  hide_relopass_branding: boolean;
}

export interface BrandingConfigResponse {
  company_id: string;
  company_name: string | null;
  branding: BrandingConfig;
}

/**
 * GAP 10: Fetch the company's portal branding config.
 * Available to all authenticated users (employee + HR).
 */
export async function getBrandingConfig(): Promise<BrandingConfigResponse> {
  return apiGet<BrandingConfigResponse>('/api/company/branding-config');
}

/**
 * GAP 10: Save the company's portal branding config. HR/admin only.
 */
export async function updateBrandingConfig(
  config: Partial<BrandingConfig>,
): Promise<BrandingConfigResponse> {
  return apiPut<BrandingConfigResponse>('/api/company/branding-config', config);
}
