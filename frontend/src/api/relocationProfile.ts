/**
 * GAP 1: Rich relocation preference profile — GET/PUT /api/employee/cases/{id}/relocation-profile
 *
 * Stores 40+ fields across 7 sections:
 *   origin_housing | housing_preferences | household | temp_housing | financial
 *
 * This is SEPARATE from the PII immigration profile at /api/employee/cases/{id}/profile.
 */
import { apiGet, apiPut } from './client';

export interface NeighbourhoodPriorities {
  commute?: number;      // 0–10
  intl_school?: number;
  parks?: number;
  expat_community?: number;
  nightlife?: number;
  safety?: number;
  transit?: number;
}

export interface HousingPreferences {
  type?: 'apartment' | 'house' | 'studio' | 'flexible';
  min_bedrooms?: number;
  max_budget_monthly_eur?: number;
  furnished?: boolean;
  pet_friendly_required?: boolean;
  neighbourhood_priorities?: NeighbourhoodPriorities;
  specific_areas?: string[];
  notes?: string;
}

export interface OriginHousing {
  owned?: boolean;
  rented?: boolean;
  notice_period_weeks?: number;
  storage_needed?: boolean;
  shipping_volume_m3?: number;
}

export interface SpouseProfile {
  full_name?: string;
  nationality?: string;
  date_of_birth?: string;
  occupation?: string;
  employer?: string;
  right_to_work_status?: 'confirmed' | 'pending' | 'unknown';
  career_support_needed?: boolean;
}

export interface ChildProfile {
  full_name?: string;
  date_of_birth?: string;
  nationality?: string;
  current_school_name?: string;
  school_year?: string;
  special_needs?: string;
  language_of_instruction?: string;
  school_type_preference?: 'international' | 'local' | 'bilingual';
}

export interface PetProfileDetail {
  name?: string;
  species?: string;
  breed?: string;
  weight_kg?: number;
  origin_country?: string;
  microchipped?: boolean;
  vaccinations_up_to_date?: boolean;
  rabies_titre_test_done?: boolean;
  health_certificate_obtained?: boolean;
}

export interface HouseholdMembers {
  marital_status?: 'solo' | 'partner' | 'partner_kids' | 'kids_only';
  spouse?: SpouseProfile;
  children?: ChildProfile[];
  pets?: PetProfileDetail[];
}

export interface TempHousing {
  needed?: boolean;
  duration_weeks?: number;
  max_budget_per_night_eur?: number;
  serviced_apartment_preferred?: boolean;
  arrival_date?: string;
}

export interface FinancialProfile {
  has_fx_transfer_needs?: boolean;
  estimated_monthly_transfer_eur?: number;
  home_sale_proceeds?: boolean;
  investment_accounts_abroad?: boolean;
  tax_equalisation_applicable?: boolean;
  home_country_tax_filing_needed?: boolean;
}

export interface RelocationProfileData {
  origin_housing?: OriginHousing;
  housing_preferences?: HousingPreferences;
  household?: HouseholdMembers;
  temp_housing?: TempHousing;
  financial?: FinancialProfile;
  additional_notes?: string;
}

export interface RelocationProfileResponse {
  case_id: string;
  profile: RelocationProfileData;
  completion_pct: number;
  last_updated_at: string | null;
}

/** GAP 1: Fetch the rich relocation preference profile for a case. */
export async function getRelocationProfile(caseId: string): Promise<RelocationProfileResponse> {
  return apiGet<RelocationProfileResponse>(`/api/employee/cases/${caseId}/relocation-profile`);
}

/** GAP 1: Save / replace the rich relocation preference profile for a case. */
export async function putRelocationProfile(
  caseId: string,
  data: RelocationProfileData,
): Promise<RelocationProfileResponse> {
  return apiPut<RelocationProfileResponse>(`/api/employee/cases/${caseId}/relocation-profile`, data);
}
