import { describe, expect, it } from 'vitest';
import { isV2FlagOn } from './flags';

// AIQ-759: companies_resizable now defaults ON so the resizable/reorderable
// admin companies table is live without an env var or localStorage opt-in.
// (The localStorage 'off' override still wins at runtime — that path is the
// pre-existing resolution order in isV2FlagOn and isn't exercised here because
// this vitest/jsdom setup has no window.localStorage.)

describe('platform-v2 flags — AIQ-759 default-on', () => {
  it('companies_resizable defaults ON (no override, no env)', () => {
    expect(isV2FlagOn('companies_resizable')).toBe(true);
  });

  it('other flags still default OFF', () => {
    expect(isV2FlagOn('companies')).toBe(false);
    expect(isV2FlagOn('inbox')).toBe(false);
    expect(isV2FlagOn('mobility_control')).toBe(false);
  });
});
