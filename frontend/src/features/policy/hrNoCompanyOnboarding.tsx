/**
 * [T2.4] Shared "no company linked" onboarding state for HR policy surfaces.
 *
 * A brand-new HR user who hasn't been linked to a company yet (no hr_profiles
 * row) gets a 403 from every policy endpoint:
 *
 *   GET /api/hr/policy-config      → 403
 *   GET /api/company-policies      → 403
 *   GET /api/hr/policy-documents   → 403
 *   { "detail": "No company linked to this profile — policy management
 *                requires a tenant." }
 *
 * That 403 is correct backend behaviour (hr_policies.py). The frontend must
 * detect it specifically and render a friendly onboarding state instead of a
 * red error banner, a blank screen, or the (misleading) "upload your policy"
 * starter flow — the new-customer-mid-onboarding persona. Other errors
 * (500 / network) must still surface as real errors.
 */
import React from 'react';

import { Card } from '../../components/antigravity';

/** Extract an HTTP status from an axios-style or fetch-style rejection. */
export function httpStatusOf(err: unknown): number | undefined {
  const e = err as { response?: { status?: number }; status?: number } | null | undefined;
  return e?.response?.status ?? e?.status;
}

/**
 * True when the error is the backend's "no company linked to this profile" 403.
 * For an HR user hitting their own policy endpoints, a 403 always means the
 * account isn't linked to a tenant yet (the only 403 these endpoints emit).
 */
export function isNoCompanyError(err: unknown): boolean {
  return httpStatusOf(err) === 403;
}

/**
 * Graceful onboarding empty state for an HR account that isn't linked to a
 * company yet. Tone mirrors the employee-side "No company linked yet" card.
 * Deliberately does NOT offer a setup CTA — the company-link flow is admin-side
 * and doesn't exist as a self-serve path yet.
 */
export function HrNoCompanyOnboarding(): React.ReactElement {
  return (
    <Card padding="lg" className="border-[#e2e8f0]">
      <div data-testid="hr-no-company-onboarding">
        <p className="text-sm font-medium text-[#0b2b43] mb-1">Complete your account setup</p>
        <p className="text-sm text-[#64748b]">
          Your account isn&apos;t linked to a company yet. Policy management becomes available once
          your company is set up — contact your ReloPass admin to complete setup.
        </p>
      </div>
    </Card>
  );
}
