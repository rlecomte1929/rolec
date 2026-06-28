import type { AssignmentDetail, RelocationProfile } from '../../types';
import { getCountryName } from '../../utils/countries';

/**
 * Case Essentials: field resolution for HR case summary.
 *
 * Source precedence (same payload as GET /api/hr/assignments/{id}; no extra fetches):
 *
 * 1) Employee full name
 *    - profile.primaryApplicant.fullName (wizard / intake RelocationProfile)
 *    - assignment.linkedEmployeeFullName (profiles.full_name via linked employee_user_id)
 *    - assignment.employeeFirstName + employeeLastName (case_assignments columns)
 *    - else explicit “Not provided” (we do not use employeeIdentifier as a display name)
 *
 * 2) Email
 *    - assignment.employeeEmail (profiles.email for employee_user_id)
 *    - else if employeeIdentifier looks like an email, use it (invite/login identifier)
 *    - else “Not provided”
 *
 * 3) Family status
 *    - Derived only from RelocationProfile: maritalStatus, spouse.fullName, dependents[]
 *    - If profile missing or no signals → “To be completed”
 *
 * 4) Origin country / region
 *    - profile.movePlan.origin
 *    - assignment.caseOriginHint (relocation_cases: relocationBasics.originCountry || home_country)
 *
 * 5) Destination
 *    - profile.movePlan.destination
 *    - assignment.caseDestinationHint (relocationBasics.destCountry || host_country)
 */

const NOT_PROVIDED = 'Not provided';
const TO_COMPLETE = 'To be completed';

function nonEmpty(s: string | null | undefined): string | undefined {
  const t = (s ?? '').trim();
  return t.length ? t : undefined;
}

function looksLikeEmail(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}

export type CaseEssentialsVM = {
  fullName: string;
  email: string;
  familyStatus: string;
  origin: string;
  destination: string;
};

/**
 * [AIQ-1336] City-level location label: "City, Country" when a city is known,
 * else the country alone, else the city alone. Resolves ISO codes to full names
 * via getCountryName (same normalisation as the country-only path it replaces),
 * so the HR case detail reads "Paris, France" instead of just "France".
 */
function formatLocation(city?: string, country?: string): string | undefined {
  const c = country ? getCountryName(country) || country : undefined;
  if (city && c) return `${city}, ${c}`;
  return c ?? city;
}

export function deriveCaseEssentials(a: AssignmentDetail): CaseEssentialsVM {
  const p = a.profile ?? undefined;

  const fromProfileName = nonEmpty(p?.primaryApplicant?.fullName);
  const fromLinked = nonEmpty(a.linkedEmployeeFullName);
  const fn = nonEmpty(a.employeeFirstName);
  const ln = nonEmpty(a.employeeLastName);
  const fromAssignmentName =
    fn || ln ? [fn, ln].filter(Boolean).join(' ').trim() : undefined;

  const fullName = fromProfileName ?? fromLinked ?? fromAssignmentName ?? NOT_PROVIDED;

  const fromProfileEmail = nonEmpty(a.employeeEmail);
  const ident = nonEmpty(a.employeeIdentifier);
  const email =
    fromProfileEmail ?? (ident && looksLikeEmail(ident) ? ident : undefined) ?? NOT_PROVIDED;

  const familyStatus = formatFamilyStatus(p);

  // Normalize to display names — destination is often stored as an ISO code
  // ("NO") while origin is a full name ("France"), so a raw corridor reads
  // "France → NO". getCountryName passes through unknown/free-text values.
  const origin =
    formatLocation(
      nonEmpty(a.caseOriginCity),
      nonEmpty(p?.movePlan?.origin) ?? nonEmpty(a.caseOriginHint),
    ) || NOT_PROVIDED;

  const destination =
    formatLocation(
      nonEmpty(a.caseDestinationCity),
      nonEmpty(p?.movePlan?.destination) ?? nonEmpty(a.caseDestinationHint),
    ) || NOT_PROVIDED;

  return { fullName, email, familyStatus, origin, destination };
}

function formatFamilyStatus(profile: RelocationProfile | undefined): string {
  if (!profile) return TO_COMPLETE;

  const msRaw = profile.maritalStatus;
  const ms = typeof msRaw === 'string' ? msRaw.toLowerCase() : '';
  const spouseName = nonEmpty(profile.spouse?.fullName);
  const kids =
    profile.dependents?.filter((c) => nonEmpty(c.firstName) || nonEmpty(c.dateOfBirth)) ?? [];

  if (kids.length > 0) {
    return `Family relocation (${kids.length} dependant${kids.length === 1 ? '' : 's'} on file)`;
  }
  if (spouseName || ms === 'married') {
    return spouseName ? `Family (spouse: ${spouseName})` : 'Family (spouse on file)';
  }
  if (ms === 'single' || ms === 'divorced' || ms === 'widowed') {
    const label = ms === 'single' ? 'Single' : ms.charAt(0).toUpperCase() + ms.slice(1);
    return `${label} (no dependants on file)`;
  }
  if (ms) {
    return `Registered: ${msRaw}`;
  }
  if ((profile.familySize ?? 0) > 1) {
    return 'To be completed (household size suggests family: details not captured)';
  }
  return TO_COMPLETE;
}
