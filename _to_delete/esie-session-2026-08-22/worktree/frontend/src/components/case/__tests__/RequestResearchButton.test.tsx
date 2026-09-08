import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { createResearchRequest } from '../../../api/researchRequests';
import { RequestResearchButton } from '../RequestResearchButton';

vi.mock('../../../api/researchRequests', () => ({
  createResearchRequest: vi.fn().mockResolvedValue({ id: 'rr-1' }),
}));

describe('RequestResearchButton', () => {
  it('renders nothing without a destCountry', () => {
    const { container } = render(<RequestResearchButton destCountry={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('files a request on click and confirms (company resolved server-side)', async () => {
    render(<RequestResearchButton destCountry="JP" originCountry="US" corridorLabel="US→JP" />);
    fireEvent.click(screen.getByText(/Request research/i));
    await waitFor(() =>
      expect(createResearchRequest).toHaveBeenCalledWith(
        expect.objectContaining({ dest_country: 'JP', origin_country: 'US' }),
      ),
    );
    expect(await screen.findByText(/Research requested/i)).toBeTruthy();
  });
});
