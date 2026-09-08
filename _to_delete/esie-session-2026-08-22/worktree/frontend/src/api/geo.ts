/**
 * AIQ-1607: address autocomplete via the ReloPass backend proxy (Geoapify).
 * The provider key stays server-side; `disabled:true` when unkeyed → the UI
 * degrades to a plain input.
 */
import { apiGet } from './client';

export interface AddressSuggestion {
  formatted: string;
}

export interface AddressAutocompleteResponse {
  disabled: boolean;
  suggestions: AddressSuggestion[];
}

export const getAddressAutocomplete = (
  q: string,
  signal?: AbortSignal,
): Promise<AddressAutocompleteResponse> =>
  apiGet(`/api/employee/geocode/autocomplete?q=${encodeURIComponent(q)}`, { signal });
