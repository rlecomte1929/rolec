import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  hrWhatsExpected,
  hrTaskTimeline,
  roadmapWhatsExpected,
  roadmapTaskTimeline,
  sourceHostLabel,
} from '../taskCardCopy';

afterEach(() => {
  vi.useRealTimers();
});

describe('hrWhatsExpected', () => {
  it('always gives a plain-English instruction even with no description', () => {
    const { instruction, detail } = hrWhatsExpected('document_upload', null);
    expect(instruction).toMatch(/Upload the document/i);
    expect(detail).toBeNull();
  });

  it('keeps HR’s own description as extra detail', () => {
    const { detail } = hrWhatsExpected('custom', '  Scan both sides of your passport.  ');
    expect(detail).toBe('Scan both sides of your passport.');
  });
});

describe('hrTaskTimeline', () => {
  it('explains a missing due date', () => {
    expect(hrTaskTimeline(null)[0].kind).toBe('open');
    expect(hrTaskTimeline(null)[0].text).toMatch(/No due date/);
  });

  it('counts days left for a near deadline', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-09T12:00:00Z'));
    const lines = hrTaskTimeline('2026-09-12T00:00:00Z');
    expect(lines[0].kind).toBe('due');
    expect(lines[0].text).toMatch(/days left/);
  });
});

describe('roadmapWhatsExpected', () => {
  it('uses the step description when present', () => {
    const { instruction, howTo } = roadmapWhatsExpected({
      description: 'Register at the Bürgeramt within 14 days of moving in.',
      ai_suggestion: 'Book an appointment online first.',
    });
    expect(instruction).toMatch(/Bürgeramt/);
    expect(howTo).toMatch(/appointment/);
  });

  it('falls back to generic expected copy when description is empty', () => {
    const { instruction, howTo } = roadmapWhatsExpected({
      description: '  ',
      ai_suggestion: null,
    });
    expect(instruction).toMatch(/official source/i);
    expect(howTo).toBeNull();
  });
});

describe('roadmapTaskTimeline', () => {
  it('labels a suggested due date as not a legal deadline', () => {
    const lines = roadmapTaskTimeline({
      due_date: '2026-10-01',
      due_date_is_suggested: true,
      estimated_effort: '~15 min',
    });
    expect(lines.some((l) => l.kind === 'suggested' && /not a legal deadline/.test(l.text))).toBe(
      true,
    );
    expect(lines.some((l) => l.kind === 'effort' && /~15 min/.test(l.text))).toBe(true);
  });

  it('explains a missing date', () => {
    const lines = roadmapTaskTimeline({
      due_date: null,
      due_date_is_suggested: false,
      estimated_effort: null,
    });
    expect(lines).toHaveLength(1);
    expect(lines[0].kind).toBe('open');
  });
});

describe('sourceHostLabel', () => {
  it('strips www from a government host', () => {
    expect(sourceHostLabel('https://www.revenue.ie/en/starting-a-business')).toBe('revenue.ie');
  });
});
