import { describe, expect, it } from 'vitest';
import { classifyOverviewLoadError } from './overviewLoadError';

describe('classifyOverviewLoadError', () => {
  it('maps 403 to a forbidden message, not a connection problem', () => {
    const out = classifyOverviewLoadError({ response: { status: 403 } });
    expect(out.kind).toBe('forbidden');
    expect(out.message).not.toMatch(/connection/i);
  });

  it('maps 401 and 5xx separately from network', () => {
    expect(classifyOverviewLoadError({ response: { status: 401 } }).kind).toBe('unauthorized');
    expect(classifyOverviewLoadError({ response: { status: 500 } }).kind).toBe('server');
    expect(classifyOverviewLoadError(new Error('offline')).kind).toBe('network');
  });
});
