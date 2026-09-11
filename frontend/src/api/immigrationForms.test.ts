import { describe, it, expect, vi, beforeEach } from 'vitest';
import { immigrationFormsAPI } from './immigrationForms';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('./client', () => ({ api: { get, post }, default: { get, post } }));

describe('immigrationFormsAPI', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it('getAvailableForms calls the employee route and returns the payload', async () => {
    get.mockResolvedValue({ data: { corridor_to: 'FR', visa_type: 'long_stay', forms: [] } });
    const res = await immigrationFormsAPI.getAvailableForms('case-1');
    expect(get).toHaveBeenCalledWith(
      '/api/employee/cases/case-1/immigration/available-forms',
      { params: {} },
    );
    expect(res.visa_type).toBe('long_stay');
  });

  it('encodes the case id and passes visa_type / corridor_to as query params', async () => {
    get.mockResolvedValue({ data: { corridor_to: 'FR', visa_type: 'long_stay', forms: [] } });
    await immigrationFormsAPI.getAvailableForms('c 2', { visaType: 'long_stay', corridorTo: 'FR' });
    expect(get).toHaveBeenCalledWith(
      '/api/employee/cases/c%202/immigration/available-forms',
      { params: { visa_type: 'long_stay', corridor_to: 'FR' } },
    );
  });

  it('generateForm posts the form_id and returns the fill report', async () => {
    post.mockResolvedValue({
      data: {
        download_url: 'https://storage/x.pdf',
        fill_report: { form_id: 'FR_cerfa_14571_v2024', filled_count: 3, fields: [] },
      },
    });
    const res = await immigrationFormsAPI.generateForm('case-1', 'FR_cerfa_14571_v2024');
    expect(post).toHaveBeenCalledWith(
      '/api/employee/cases/case-1/immigration/generate-form',
      { form_id: 'FR_cerfa_14571_v2024' },
    );
    expect(res.fill_report.filled_count).toBe(3);
    expect(res.download_url).toBe('https://storage/x.pdf');
  });
});
