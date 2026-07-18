import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { AddressAutocompleteInput } from './AddressAutocompleteInput';
import * as geo from '../api/geo';

// Mock the api module (also avoids importing the real client → supabase in jsdom).
vi.mock('../api/geo', () => ({ getAddressAutocomplete: vi.fn() }));

describe('AddressAutocompleteInput', () => {
  beforeEach(() => {
    vi.mocked(geo.getAddressAutocomplete).mockReset();
  });

  it('renders the value and forwards typing (free text stays valid)', () => {
    vi.mocked(geo.getAddressAutocomplete).mockResolvedValue({ disabled: true, suggestions: [] });
    const onChange = vi.fn();
    render(<AddressAutocompleteInput value="10 Down" onChange={onChange} testId="addr" />);
    const input = screen.getByTestId('addr') as HTMLInputElement;
    expect(input.value).toBe('10 Down');
    fireEvent.change(input, { target: { value: '10 Downing' } });
    expect(onChange).toHaveBeenCalledWith('10 Downing');
  });

  it('shows a dropdown and fills on select when the backend returns suggestions', async () => {
    vi.mocked(geo.getAddressAutocomplete).mockResolvedValue({
      disabled: false,
      suggestions: [{ formatted: '10 Downing Street, London, UK' }],
    });
    const onChange = vi.fn();
    render(<AddressAutocompleteInput value="10 Downing" onChange={onChange} testId="addr" />);
    const option = await screen.findByRole('option', {}, { timeout: 1500 });
    expect(option).toHaveTextContent('10 Downing Street, London, UK');
    fireEvent.click(option);
    expect(onChange).toHaveBeenCalledWith('10 Downing Street, London, UK');
  });

  it('degrades to a plain input (no dropdown) when the backend is disabled', async () => {
    vi.mocked(geo.getAddressAutocomplete).mockResolvedValue({ disabled: true, suggestions: [] });
    render(<AddressAutocompleteInput value="10 Downing Street" onChange={() => {}} testId="addr" />);
    await waitFor(() => expect(geo.getAddressAutocomplete).toHaveBeenCalled(), { timeout: 1500 });
    expect(screen.queryByRole('option')).toBeNull();
  });
});
