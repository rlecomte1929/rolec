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
    // TD-QA batch 0719 (#5): the three-question spine — friction, buy signal, roadmap.
    expect(screen.getByText(/Where did you get lost\?/i)).toBeInTheDocument();
    expect(screen.getByText(/Would you trust this with a real move\?/i)).toBeInTheDocument();
    expect(screen.getByText(/One thing that would make it a yes\./i)).toBeInTheDocument();
    // TD-EEA: the permit-relevance probe renders for every corridor.
    expect(screen.getByText(/sponsoring a work permit/i)).toBeInTheDocument();
    // The old Q4 was folded into the roadmap prompt — it must not render anymore.
    expect(screen.queryByText(/If you could change one thing/i)).not.toBeInTheDocument();
  });

  it('maps answers + session/corridor from the URL and shows the thank-you state', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');

    // #5: the segment self-ID and the trust question are now BOTH plain Yes/No taps,
    // so select by position — [0] is the segment lead-in, [1] is the trust buy signal.
    const yesButtons = screen.getAllByRole('button', { name: 'Yes' });
    fireEvent.click(yesButtons[0]); // segment: prospect (TD-FIX-2)
    fireEvent.click(yesButtons[1]); // trust: yes (#5 buy signal)
    fireEvent.click(screen.getByRole('button', { name: '4' })); // Q1 = 4
    // TD-EEA: Q3b permit relevance — the option label is unique, no positional pick needed.
    fireEvent.click(screen.getByRole('button', { name: /Not yet — but it could be/i }));
    fireEvent.click(screen.getByRole('button', { name: /Maybe, tell me more/i })); // Q6
    fireEvent.click(screen.getByLabelText(/You can quote me/i)); // Q5 consent
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));

    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    const payload = mockSubmit.mock.calls[0][0];
    expect(payload.session_id).toBe('sess-1');
    expect(payload.corridor_id).toBe('GB_US');
    expect(payload.tester_segment).toBe('prospect');
    expect(payload.trust_intent).toBe('yes');
    expect(payload.permit_relevance).toBe('not_yet');
    expect(payload.q1_overall).toBe(4);
    expect(payload.pilot_interest).toBe('maybe');
    expect(payload.testimonial_consent).toBe(true);

    expect(await screen.findByText(/genuinely useful/i)).toBeInTheDocument();
    // #2: CALENDAR_URL still holds the {{CALENDAR_URL}} placeholder in the repo, so the
    // demo-bridge CTA must hide itself rather than render a dead link.
    expect(screen.queryByText(/Grab 20 minutes with me/i)).not.toBeInTheDocument();
  });

  it('requires the segment tap before submitting (TD-FIX-2)', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    // Submit with no segment chosen → blocked with the required prompt, no network call.
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    expect(await screen.findByText(/weight your feedback correctly/i)).toBeInTheDocument();
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it("stores 'internal' when the tester answers No (TD-FIX-2)", async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    // [0] = the segment lead-in 'No' (the trust question's 'No' is [1]).
    fireEvent.click(screen.getAllByRole('button', { name: 'No' })[0]); // segment: internal
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    expect(mockSubmit.mock.calls[0][0].tester_segment).toBe('internal');
  });

  it('surfaces an API error and stays on the form', async () => {
    mockSubmit.mockResolvedValue({ ok: false, error: 'Survey closed for now.' });
    renderAt();
    fireEvent.click(screen.getAllByRole('button', { name: 'Yes' })[0]); // segment required before submit
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    expect(await screen.findByText(/Survey closed for now/i)).toBeInTheDocument();
    expect(screen.queryByText(/genuinely useful/i)).not.toBeInTheDocument();
  });
});
