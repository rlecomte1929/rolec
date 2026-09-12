import { describe, expect, it } from 'vitest';
import { classifyOverviewLoadError, overviewLoadAlertTitle } from './overviewLoadError';

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

describe('overviewLoadAlertTitle', () => {
  it('titles session, access, connection, and server distinctly', () => {
    expect(overviewLoadAlertTitle('unauthorized')).toBe('Sign in again');
    expect(overviewLoadAlertTitle('forbidden')).toBe('This account cannot open assignments');
    expect(overviewLoadAlertTitle('network')).toBe('Could not reach ReloPass');
    expect(overviewLoadAlertTitle('server')).toBe('Something went wrong');
    expect(overviewLoadAlertTitle('unknown')).toBe('Could not load assignments');
  });
});
