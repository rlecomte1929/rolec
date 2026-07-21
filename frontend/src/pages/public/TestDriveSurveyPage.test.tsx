import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../api/testDrive', () => ({ submitSurvey: vi.fn() }));
vi.mock('../../api/supabase', () => ({ supabase: { functions: { invoke: vi.fn() } } }));
// Passthrough layout — avoids PublicHeader/Footer's DemoBookingProvider requirement.
vi.mock('../../components/public', () => ({
  PublicLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { submitSurvey } from '../../api/testDrive';
import { TestDriveSurveyPage } from './TestDriveSurveyPage';

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

const mockSubmit = submitSurvey as unknown as ReturnType<typeof vi.fn>;

function renderAt(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/test-drive/survey${search}`]}>
      <TestDriveSurveyPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TestDriveSurveyPage', () => {
  it('renders the completion intro + key questions', () => {
    renderAt('?corridor=GB_US&session=s1');
    expect(screen.getByRole('heading', { name: /A few quick questions/i })).toBeInTheDocument();
    expect(screen.getByText(/how did running this case feel/i)).toBeInTheDocument();
    expect(screen.getByText(/want to run a real pilot/i)).toBeInTheDocument();
  });

  it('maps answers + session/corridor from the URL and shows the thank-you state', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');

    fireEvent.click(screen.getByRole('button', { name: 'Yes' })); // segment: prospect (TD-FIX-2)
    fireEvent.click(screen.getByRole('button', { name: '4' })); // Q1 = 4
    fireEvent.click(screen.getByRole('button', { name: /Maybe, tell me more/i })); // Q6
    fireEvent.click(screen.getByLabelText(/You can quote me/i)); // Q5 consent
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));

    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    const payload = mockSubmit.mock.calls[0][0];
    expect(payload.session_id).toBe('sess-1');
    expect(payload.corridor_id).toBe('GB_US');
    expect(payload.tester_segment).toBe('prospect');
    expect(payload.q1_overall).toBe(4);
    expect(payload.pilot_interest).toBe('maybe');
    expect(payload.testimonial_consent).toBe(true);

    expect(await screen.findByText(/genuinely useful/i)).toBeInTheDocument();
  });

  it('[AIQ-1645] blocks on the segment question — names it, marks it inline, keeps answers', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    // Answer other questions first — these must survive a failed submit (criterion 5).
    fireEvent.click(screen.getByRole('button', { name: '4' })); // Q1 = 4
    fireEvent.click(screen.getByRole('button', { name: /Maybe, tell me more/i })); // Q6

    // Submit with no segment chosen → blocked, no network call.
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    expect(mockSubmit).not.toHaveBeenCalled();
    // The error NAMES the unanswered question, and the field is marked inline beside it.
    expect(
      await screen.findByText(/Please answer: Do you work in HR, mobility, or relocation\?/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/pick one so I can weight your feedback correctly/i)).toBeInTheDocument();

    // Answering clears the inline mark; submit then succeeds with the earlier answers intact.
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }));
    expect(screen.queryByText(/pick one so I can weight your feedback correctly/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    expect(mockSubmit.mock.calls[0][0].q1_overall).toBe(4);
    expect(mockSubmit.mock.calls[0][0].pilot_interest).toBe('maybe');
    expect(mockSubmit.mock.calls[0][0].tester_segment).toBe('prospect');
  });

  it("stores 'internal' when the tester answers No (TD-FIX-2)", async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    fireEvent.click(screen.getByRole('button', { name: 'No' })); // segment: internal
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    expect(mockSubmit.mock.calls[0][0].tester_segment).toBe('internal');
  });

  it('surfaces an API error and stays on the form', async () => {
    mockSubmit.mockResolvedValue({ ok: false, error: 'Survey closed for now.' });
    renderAt();
    fireEvent.click(screen.getByRole('button', { name: 'Yes' })); // segment required before submit
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    expect(await screen.findByText(/Survey closed for now/i)).toBeInTheDocument();
    expect(screen.queryByText(/genuinely useful/i)).not.toBeInTheDocument();
  });
});
