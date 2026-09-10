import React from 'react';

interface RequirementsCoverageNoticeProps {
  /** CaseRequirementsDTO.covered — undefined (older backend) is treated as covered. */
  covered?: boolean;
  destCountry?: string;
  catalogReady?: boolean;
  catalogNotReadyReason?: string | null;
}

/**
 * AIQ-1473c/d: when the destination isn't in our requirements catalogue the API
 * returns `covered: false` with an empty list. Without this notice an empty list
 * reads as "nothing required" — the AIQ-1349 silent-miss. Render an honest
 * "no catalogue yet" message instead. Nothing is shown while covered (the common
 * case), so this is a no-op for catalogued destinations.
 */
export const RequirementsCoverageNotice: React.FC<RequirementsCoverageNoticeProps> = ({
  covered,
  destCountry,
  catalogReady,
  catalogNotReadyReason,
}) => {
  if (covered === false) {
    const where = destCountry ? ` for ${destCountry}` : '';
    return (
      <div
        role="status"
        data-testid="requirements-not-ready"
        className="mt-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]"
      >
        <div className="text-sm font-semibold text-[#0b2b43] mb-1">
          This corridor is not ready{where}
        </div>
        <div>
          We don&apos;t have a verified requirements catalogue{where} yet, so this list is
          empty — that means we can&apos;t confirm the requirements here, not that there are
          none. Please confirm with the local authority.
        </div>
      </div>
    );
  }
  if (catalogReady === false) {
    const where = destCountry ? ` for ${destCountry}` : '';
    return (
      <div
        role="status"
        data-testid="requirements-not-ready"
        className="mt-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]"
      >
        <div className="text-sm font-semibold text-[#0b2b43] mb-1">
          This corridor is not ready{where}
        </div>
        <div>
          {catalogNotReadyReason
            || 'Approved items are incomplete or uncited. Treat the list as a gap, not as a finding that nothing is required.'}
        </div>
      </div>
    );
  }
  return null;
};
