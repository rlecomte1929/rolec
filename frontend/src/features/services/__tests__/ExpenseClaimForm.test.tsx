import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ExpenseClaimForm } from '../ExpenseClaimForm';
import api from '../../../api/client';

vi.mock('../../../api/client', () => ({
  default: { post: vi.fn(), get: vi.fn(), patch: vi.fn() },
}));

vi.mock('../../../api/expenseClaims', () => ({
  expenseClaimsAPI: { create: vi.fn(), list: vi.fn(), patch: vi.fn() },
}));

describe('ExpenseClaimForm OCR prefill', () => {
  beforeEach(() => vi.clearAllMocks());

  it('prefills vendor, amount, currency and date from OCR extracted_fields', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        id: 'ocr-1',
        extracted_fields: {
          vendor_name: 'Ikea',
          amount: 549,
          currency: 'EUR',
          date: '2026-09-01',
        },
      },
    });
    const { container } = render(<ExpenseClaimForm caseId="c1" />);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'receipt.png', { type: 'image/png' });
    await waitFor(() => expect(fileInput).toBeTruthy());
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(await screen.findByDisplayValue('Ikea')).toBeInTheDocument();
    expect(screen.getByDisplayValue('549')).toBeInTheDocument();
    expect(screen.getByDisplayValue('EUR')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2026-09-01')).toBeInTheDocument();
  });
});
