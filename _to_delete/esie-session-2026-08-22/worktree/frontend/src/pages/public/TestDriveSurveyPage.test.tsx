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

  it('renders the referral block directly under the pilot-interest question', () => {
    renderAt('?corridor=GB_US&session=s1');
    const html = document.body.innerHTML;
    const pilotAt = html.indexOf('Would you or your company want to run a real pilot?');
    const referralAt = html.indexOf('Who else runs or oversees relocations');
    const frictionAt = html.indexOf('Where did you get stuck, confused, or slowed down?');
    expect(pilotAt).toBeGreaterThan(-1);
    // Referral sits after pilot-interest…
    expect(referralAt).toBeGreaterThan(pilotAt);
    // …and the pair is above the free-text block, so a mid-survey drop-off still leaves them.
    expect(frictionAt).toBeGreaterThan(referralAt);
    // One empty referral row to start with.
    expect(screen.getAllByLabelText('Name')).toHaveLength(1);
  });

  it('"Add another" adds referral rows and sends them all, mirroring the first to the legacy fields', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    fireEvent.click(screen.getByRole('button', { name: 'Yes' })); // segment

    const fillRow = (i: number, name: string, role: string, contact: string) => {
      fireEvent.change(screen.getAllByLabelText('Name')[i], { target: { value: name } });
      fireEvent.change(screen.getAllByLabelText('Company / role')[i], { target: { value: role } });
      fireEvent.change(screen.getAllByLabelText(/How to reach them/i)[i], {
        target: { value: contact },
      });
    };

    fillRow(0, 'Jordan Peer', 'Head of Mobility, Globex', 'jordan@globex.test');
    fireEvent.click(screen.getByLabelText(/You can mention I referred them/i)); // row 0 consent
    fireEvent.click(screen.getByRole('button', { name: /Add another person/i }));
    fillRow(1, 'Sam Two', 'HRD, Initech', 'sam@initech.test');
    fireEvent.click(screen.getByRole('button', { name: /Add another person/i }));
    fillRow(2, 'Robin Three', 'People Ops, Umbrella', 'robin@umbrella.test');
    expect(screen.getAllByLabelText('Name')).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));

    const payload = mockSubmit.mock.calls[0][0];
    expect(payload.referrals).toHaveLength(3);
    expect(payload.referrals.map((r: { name?: string }) => r.name)).toEqual([
      'Jordan Peer',
      'Sam Two',
      'Robin Three',
    ]);
    expect(payload.referrals[0].consent).toBe(true);
    expect(payload.referrals[1].consent).toBe(false);
    // Legacy single fields still carry referrals[0] — the admin "intro" count and the daily
    // warm-lead alert read those columns, and a stale backend captures at least the first.
    expect(payload.referral_name).toBe('Jordan Peer');
    expect(payload.referral_company_role).toBe('Head of Mobility, Globex');
    expect(payload.referral_contact).toBe('jordan@globex.test');
    expect(payload.referral_consent).toBe(true);
  });

  it('caps "Add another" and drops untouched rows at submit', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    fireEvent.click(screen.getByRole('button', { name: 'Yes' })); // segment

    for (let i = 0; i < 4; i += 1) {
      fireEvent.click(screen.getByRole('button', { name: /Add another person/i }));
    }
    expect(screen.getAllByLabelText('Name')).toHaveLength(5);
    // Cap reached — the button is gone.
    expect(screen.queryByRole('button', { name: /Add another person/i })).not.toBeInTheDocument();

    // Only one row filled; the other four are untouched and must not be sent.
    fireEvent.change(screen.getAllByLabelText('Name')[2], { target: { value: 'Only One' } });
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));

    const payload = mockSubmit.mock.calls[0][0];
    expect(payload.referrals).toHaveLength(1);
    expect(payload.referrals[0].name).toBe('Only One');
    expect(payload.referral_name).toBe('Only One');
  });

  it('submits with no referrals at all — empty array, no legacy values', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    fireEvent.click(screen.getByRole('button', { name: 'Yes' })); // segment
    fireEvent.click(screen.getByRole('button', { name: /^Submit$/ }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));

    const payload = mockSubmit.mock.calls[0][0];
    expect(payload.referrals).toEqual([]);
    expect(payload.referral_name).toBeUndefined();
    expect(payload.referral_consent).toBe(false);
  });

  it('removes a referral row and never drops below one', async () => {
    mockSubmit.mockResolvedValue({ ok: true, responseId: 'r1' });
    renderAt('?corridor=GB_US&session=sess-1');
    fireEvent.click(screen.getByRole('button', { name: /Add another person/i }));
    fireEvent.change(screen.getAllByLabelText('Name')[0], { target: { value: 'Keep Me' } });
    fireEvent.change(screen.getAllByLabelText('Name')[1], { target: { value: 'Drop Me' } });

    fireEvent.click(screen.getByRole('button', { name: /Remove person 2/i }));
    expect(screen.getAllByLabelText('Name')).toHaveLength(1);
    expect(screen.getAllByLabelText('Name')[0]).toHaveValue('Keep Me');
    // The last row has no remove control — the question stays answerable.
    expect(screen.queryByRole('button', { name: /Remove person/i })).not.toBeInTheDocument();
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
