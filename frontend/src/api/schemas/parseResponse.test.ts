import { describe, it, expect, vi, afterEach } from 'vitest';
import { z } from 'zod';
import { parseResponse } from './parseResponse';

const schema = z.object({ a: z.number(), b: z.string() });

afterEach(() => vi.restoreAllMocks());

describe('parseResponse — tolerant API-boundary validation', () => {
  it('returns the parsed value on a valid response', () => {
    expect(parseResponse(schema, { a: 1, b: 'x' }, 'test')).toEqual({ a: 1, b: 'x' });
  });

  it('NEVER throws on a malformed response — returns the raw data', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const bad = { a: 'not-a-number' };
    expect(() => parseResponse(schema, bad, 'test')).not.toThrow();
    expect(parseResponse(schema, bad, 'test')).toBe(bad); // same reference, untouched
  });

  it('returns raw data on null without throwing (boundary returned nothing)', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(parseResponse(schema, null, 'test')).toBeNull();
  });
});
