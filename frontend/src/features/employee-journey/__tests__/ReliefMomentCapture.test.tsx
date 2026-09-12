import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ReliefMomentCapture } from '../ReliefMomentCapture';

const trackReliefMomentCaptured = vi.fn();

vi.mock('../../../analyticsEvents', () => ({
  trackReliefMomentCaptured: (...args: unknown[]) => trackReliefMomentCaptured(...args),
}));

describe('ReliefMomentCapture', () => {
  beforeEach(() => {
    trackReliefMomentCaptured.mockClear();
    const store: Record<string, string> = {};
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => {
        store[k] = v;
      },
      removeItem: (k: string) => {
        delete store[k];
      },
      clear: () => {
        Object.keys(store).forEach((k) => {
          delete store[k];
        });
      },
      key: () => null,
      length: 0,
    });
  });

  it('fires a ranked yes with the selected non-obvious item', () => {
    render(
      <ReliefMomentCapture
        caseId="case-1"
        corridorId="FR-NO"
        items={[{ id: 'd-number', text: 'You cannot apply for a D-number yourself' }]}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }));
    fireEvent.change(screen.getByLabelText(/most surprising/i), { target: { value: 'd-number' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    expect(trackReliefMomentCaptured).toHaveBeenCalledWith({
      corridor_id: 'FR-NO',
      case_id: 'case-1',
      response_yes_no: true,
      surprising_item_id: 'd-number',
      surprising_item_text: 'You cannot apply for a D-number yourself',
    });
  });

  it('fires no without a dropdown', () => {
    render(
      <ReliefMomentCapture caseId="case-1" corridorId="FR-NO" items={[]} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'No' }));
    expect(trackReliefMomentCaptured).toHaveBeenCalledWith({
      corridor_id: 'FR-NO',
      case_id: 'case-1',
      response_yes_no: false,
      surprising_item_id: null,
      surprising_item_text: null,
    });
  });
});
