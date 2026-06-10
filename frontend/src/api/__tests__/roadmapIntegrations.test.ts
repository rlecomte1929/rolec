/**
 * I-4 — roadmapIntegrations wrapper.
 * Spies the shared axios instance to prove email/calendar calls hit the right
 * endpoints, and that the .ics is fetched as a blob and downloaded client-side.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

// client.ts builds the Supabase client at import time — stub those modules.
vi.mock('../supabase', () => ({ supabase: {} }));
vi.mock('../supabaseAuth', () => ({ signOutSupabase: vi.fn() }));

import api from '../client';
import { emailRoadmapPlan, downloadCaseCalendar } from '../roadmapIntegrations';

afterEach(() => vi.restoreAllMocks());

describe('emailRoadmapPlan', () => {
  it('POSTs to the case email endpoint with an empty body by default', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { emailed_to: 'me@x.com', subject: 'S' } } as never);
    const res = await emailRoadmapPlan('case-1');
    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/api/cases/case-1/roadmap/email');
    expect(body).toEqual({});
    expect(res.emailed_to).toBe('me@x.com');
  });

  it('passes { to } when an explicit recipient is given', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { emailed_to: 'hr@x.com', subject: 'S' } } as never);
    await emailRoadmapPlan('case-1', 'hr@x.com');
    expect(post.mock.calls[0][1]).toEqual({ to: 'hr@x.com' });
  });
});

describe('downloadCaseCalendar', () => {
  it('GETs the .ics as a blob and triggers a client-side download', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: new Blob(['BEGIN:VCALENDAR']) } as never);
    (URL as unknown as { createObjectURL: () => string }).createObjectURL = vi.fn(() => 'blob:abc');
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    await downloadCaseCalendar('case-9');

    expect(get).toHaveBeenCalledTimes(1);
    const [url, opts] = get.mock.calls[0];
    expect(url).toBe('/api/cases/case-9/calendar.ics');
    expect(opts).toMatchObject({ responseType: 'blob' });
    expect(click).toHaveBeenCalledTimes(1);
  });
});
