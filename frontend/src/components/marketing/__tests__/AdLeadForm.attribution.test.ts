import { describe, it, expect } from 'vitest';
import { campaignWithAngle, ANGLE_DELIMITER } from '../AdLeadForm';

/**
 * [AIQ-1784] Angle attribution survives into the one column that exists.
 *
 * The leads table has utm_source and utm_campaign and nothing else. The creative angle
 * arrives as utm_content and must not be dropped — it is what decides where spend goes
 * at Gate 2. These pin the encoding so a later "tidy-up" cannot silently lose it.
 */
describe('campaignWithAngle', () => {
  const q = (s: string) => new URLSearchParams(s);

  it('joins campaign and angle for a fully tagged ad URL', () => {
    expect(
      campaignWithAngle(q('utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A3'), 'mobility-teams'),
    ).toBe('segment-a|A3');
  });

  it('emits no trailing delimiter when there is no angle', () => {
    const out = campaignWithAngle(q('utm_campaign=segment-a'), 'mobility-teams');
    expect(out).toBe('segment-a');
    expect(out.endsWith(ANGLE_DELIMITER)).toBe(false);
  });

  it('falls back to a page-scoped campaign for untagged organic visits', () => {
    expect(campaignWithAngle(q(''), 'relocation-checklist')).toBe('ads-relocation-checklist');
  });

  it('still records the angle when the campaign itself is missing', () => {
    // A malformed ad URL should not cost us the angle.
    expect(campaignWithAngle(q('utm_content=B2'), 'relocation-checklist')).toBe(
      'ads-relocation-checklist|B2',
    );
  });

  it('round-trips: splitting on the delimiter recovers campaign and angle', () => {
    const stored = campaignWithAngle(q('utm_campaign=segment-b&utm_content=B1'), 'relocation-checklist');
    const [campaign, angle] = stored.split(ANGLE_DELIMITER);
    expect(campaign).toBe('segment-b');
    expect(angle).toBe('B1');
  });

  it('covers every angle in the campaign matrix', () => {
    for (const angle of ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'B1', 'B2']) {
      const stored = campaignWithAngle(q(`utm_campaign=seg&utm_content=${angle}`), 'p');
      expect(stored.split(ANGLE_DELIMITER)[1]).toBe(angle);
    }
  });
});
