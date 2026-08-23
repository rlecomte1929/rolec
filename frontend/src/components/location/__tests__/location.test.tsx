/**
 * Country and city pickers — the components that replaced 21 free-text location inputs.
 *
 * Free text is how `catalog_destination_allowlist` grew three Dublins ('dublin/ireland',
 * 'Dublin/IE', 'Dublin/Ireland'), which hid 29 curated vendors from HR: the picker offered
 * all three, and choosing the lower-cased one made the backend's city filter match nothing.
 *
 * The two rules these pin:
 *   • country is a CLOSED set — a <select>, so a typo cannot enter the data;
 *   • city is an OPEN set — suggested from the catalogue but never a hard block, because a
 *     genuinely new destination must not stop someone mid-intake.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

const listEmployeeDestinations = vi.fn();
vi.mock('../../../api/destinations', () => ({
  listEmployeeDestinations: () => listEmployeeDestinations(),
}));

import { CityPicker, CountryPicker, canonPlace, resetDestinationCatalog } from '../index';

expect.extend(matchers);

const CATALOGUE = [
  { city: 'Dublin', country: 'Ireland', approved_by: null, approved_at: '', notes: null },
  { city: 'dublin', country: 'ireland', approved_by: null, approved_at: '', notes: null },
  { city: 'Cork', country: 'Ireland', approved_by: null, approved_at: '', notes: null },
  { city: 'Oslo', country: 'Norway', approved_by: null, approved_at: '', notes: null },
];

beforeEach(() => {
  // The catalogue is cached at module level, so without this the first test's fetch
  // satisfies every later one and the mocks below never take effect.
  resetDestinationCatalog();
  listEmployeeDestinations.mockReset();
  listEmployeeDestinations.mockResolvedValue(CATALOGUE);
});
afterEach(() => cleanup());

describe('canonPlace', () => {
  it('treats the spellings that caused the incident as one place', () => {
    expect(canonPlace('Dublin')).toBe(canonPlace('dublin'));
    expect(canonPlace('  DUBLIN ')).toBe(canonPlace('Dublin'));
    expect(canonPlace('Zürich')).toBe(canonPlace('Zurich'));
  });
  it('still separates genuinely different places', () => {
    expect(canonPlace('Dublin')).not.toBe(canonPlace('Cork'));
  });
});

describe('CountryPicker — a closed list', () => {
  it('renders a select, not a text box, so a country cannot be typed', () => {
    render(<CountryPicker value="" onChange={() => {}} label="Country" />);
    const el = screen.getByLabelText('Country');
    expect(el.tagName).toBe('SELECT');
  });

  it('offers real ISO-3166 countries', () => {
    render(<CountryPicker value="" onChange={() => {}} label="Country" />);
    expect(screen.getByRole('option', { name: 'Ireland' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Norway' })).toBeInTheDocument();
  });

  it('stores the ISO code when the caller keys on country_code', () => {
    /** Admin filters query by country_code; storing a NAME would match nothing —
     *  a dropdown that silently returns zero rows is no better than free text. */
    const onChange = vi.fn();
    render(<CountryPicker value="" onChange={onChange} label="Country" valueMode="code" />);
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'IE' } });
    expect(onChange).toHaveBeenCalledWith('IE');
  });

  it('keeps a legacy value that is not on the list rather than blanking it', () => {
    /** Losing what someone previously saved would be a worse bug than the one this fixes. */
    render(<CountryPicker value="Kosovo" onChange={() => {}} label="Country" />);
    expect(screen.getByRole('option', { name: 'Kosovo' })).toBeInTheDocument();
  });
});

describe('CityPicker — catalogue-backed, never a hard block', () => {
  it('suggests only the cities of the chosen country, de-duped by spelling', async () => {
    render(<CityPicker value="" onChange={() => {}} country="Ireland" label="City" />);
    const input = screen.getByLabelText('City');
    await waitFor(() => expect(listEmployeeDestinations).toHaveBeenCalled());
    fireEvent.focus(input);
    // 'Dublin' and 'dublin' are ONE destination — the duplicate that caused the incident
    // must not come back as two options.
    await waitFor(() => expect(screen.getAllByText('Dublin')).toHaveLength(1));
    expect(screen.getByText('Cork')).toBeInTheDocument();
    expect(screen.queryByText('Oslo')).not.toBeInTheDocument();
  });

  it('matches the country canonically, so a lower-cased catalogue row still answers', async () => {
    render(<CityPicker value="" onChange={() => {}} country="IRELAND" label="City" />);
    await waitFor(() => expect(listEmployeeDestinations).toHaveBeenCalled());
    fireEvent.focus(screen.getByLabelText('City'));
    await waitFor(() => expect(screen.getByText('Cork')).toBeInTheDocument());
  });

  it('still accepts a city that is not in the catalogue', async () => {
    /** The catalogue is deliberately small (AIQ-1656). A new destination must not stop
     *  someone mid-intake — it routes through the admin request flow instead. */
    const onChange = vi.fn();
    render(<CityPicker value="" onChange={onChange} country="Ireland" label="City" />);
    await waitFor(() => expect(listEmployeeDestinations).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Kilkenny' } });
    expect(onChange).toHaveBeenCalledWith('Kilkenny');
  });

  it('tells the caller whether the value is catalogue-backed', async () => {
    const onKnownChange = vi.fn();
    render(
      <CityPicker value="Dublin" onChange={() => {}} country="Ireland" label="City"
        onKnownChange={onKnownChange} />,
    );
    await waitFor(() => expect(onKnownChange).toHaveBeenCalledWith(true));
  });

  it('a catalogue that fails to load degrades to free entry, it does not lock the form', async () => {
    listEmployeeDestinations.mockRejectedValue(new Error('offline'));
    const onChange = vi.fn();
    render(<CityPicker value="" onChange={onChange} country="Ireland" label="City" />);
    await waitFor(() => expect(screen.getByLabelText('City')).not.toBeDisabled());
    fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Galway' } });
    expect(onChange).toHaveBeenCalledWith('Galway');
  });
});
