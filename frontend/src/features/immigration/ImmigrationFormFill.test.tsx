/**
 * [AIQ-1855] ImmigrationFormFill — wires the IMM-11 pre-fill backend for HR + employee.
 * The dossier API is mocked so this stays out of axios/supabase under jsdom.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/dossier', () => ({
  immigrationFormsAPI: { available: vi.fn(), generate: vi.fn() },
}));

import { immigrationFormsAPI } from '../../api/dossier';
import { ImmigrationFormFill } from './ImmigrationFormFill';

const mockAvailable = immigrationFormsAPI.available as unknown as ReturnType<typeof vi.fn>;
const mockGenerate = immigrationFormsAPI.generate as unknown as ReturnType<typeof vi.fn>;

const FORM = {
  form_id: 'f1', form_name: 'EU Blue Card', corridor_to: 'DE',
  visa_type: 'blue_card', field_count: 3, form_url: null,
};

afterEach(cleanup);
beforeEach(() => {
  mockAvailable.mockReset();
  mockGenerate.mockReset();
});

describe('ImmigrationFormFill', () => {
  it('renders nothing when the corridor has no fillable forms', async () => {
    mockAvailable.mockResolvedValue({ corridor_to: 'NO', visa_type: null, forms: [] });
    const { container } = render(<ImmigrationFormFill caseId="c1" audience="employee" />);
    await waitFor(() => expect(mockAvailable).toHaveBeenCalledWith('c1', 'employee'));
    expect(container.textContent).toBe('');
  });

  it('renders nothing when available-forms fails (unresolved corridor)', async () => {
    mockAvailable.mockRejectedValue({ response: { status: 422 } });
    const { container } = render(<ImmigrationFormFill caseId="c1" audience="hr" />);
    await waitFor(() => expect(mockAvailable).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('generates a three-state fill report with a signed-URL download and no PII values', async () => {
    mockAvailable.mockResolvedValue({ corridor_to: 'DE', visa_type: 'blue_card', forms: [FORM] });
    mockGenerate.mockResolvedValue({
      download_url: 'https://signed.example/prefilled.pdf',
      fill_report: {
        form_id: 'f1', filled_count: 1, blank_count: 1, warning_count: 1, not_in_pdf_count: 0,
        fields: [
          { form_field_id: 'a', vault_field_path: 'p', label: 'Full name', status: 'filled', value: 'PIIVALUE123', warning: null },
          { form_field_id: 'b', vault_field_path: 'p', label: 'Passport number', status: 'blank_missing_data', value: null, warning: null },
          { form_field_id: 'c', vault_field_path: 'p', label: 'Home address', status: 'warning', value: 'PIIVALUE456', warning: 'low confidence' },
        ],
      },
    });
    render(<ImmigrationFormFill caseId="c1" audience="employee" />);
    fireEvent.click(await screen.findByRole('button', { name: /generate pre-filled pdf/i }));
    await waitFor(() => expect(mockGenerate).toHaveBeenCalledWith('c1', 'employee', 'f1'));

    // Three distinct states rendered per the fill report.
    expect(await screen.findByText('Filled')).toBeInTheDocument();
    expect(screen.getByText('Missing')).toBeInTheDocument();
    expect(screen.getByText('Needs review')).toBeInTheDocument();

    // Download is a signed URL, opened safely.
    const link = screen.getByRole('link', { name: /download pdf/i });
    expect(link).toHaveAttribute('href', 'https://signed.example/prefilled.pdf');
    expect(link).toHaveAttribute('rel', 'noreferrer');

    // Field VALUES (PII) are never rendered — only labels + states.
    expect(screen.queryByText(/PIIVALUE123/)).toBeNull();
    expect(screen.queryByText(/PIIVALUE456/)).toBeNull();
  });

  it('surfaces a readable message when generate returns a 4xx', async () => {
    mockAvailable.mockResolvedValue({ corridor_to: 'DE', visa_type: 'blue_card', forms: [FORM] });
    mockGenerate.mockRejectedValue({
      response: { status: 403, data: { detail: 'No valid immigration consent on record for this case.' } },
    });
    render(<ImmigrationFormFill caseId="c1" audience="employee" />);
    fireEvent.click(await screen.findByRole('button', { name: /generate pre-filled pdf/i }));
    expect(await screen.findByText(/consent on record/i)).toBeInTheDocument();
  });
});
