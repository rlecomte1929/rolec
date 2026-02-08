import { apiGet, apiPost } from './client';
import type { CountryListDTO, CountryProfileDTO } from '../types';

const adminHeaders = () => ({
  'X-Role': localStorage.getItem('demo_role') || 'user',
});

export async function listCountries(): Promise<CountryListDTO> {
  return apiGet('/api/admin/countries', { headers: adminHeaders() });
}

export async function getCountryProfile(countryCode: string): Promise<CountryProfileDTO> {
  return apiGet(`/api/admin/countries/${countryCode}`, { headers: adminHeaders() });
}

export async function rerunCountryResearch(
  countryCode: string,
  opts?: { purpose?: string }
): Promise<{ jobId: string }> {
  return apiPost(`/api/admin/countries/${countryCode}/research/rerun`, opts, { headers: adminHeaders() });
}
