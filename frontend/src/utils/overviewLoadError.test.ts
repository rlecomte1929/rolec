import { describe, it, expect } from 'vitest';
import { classifyOverviewLoadError } from './overviewLoadError';

describe('classifyOverviewLoadError (AIQ-2286)', () => {
  it('does not blame the network for a 401', () => {
    const result = classifyOverviewLoadError({ response: { status: 401 } });
    expect(result.kind).toBe('unauthorized');
    expect(result.message).toMatch(/sign in/i);
    expect(result.message).not.toMatch(/connection/i);
  });

  it('does not blame the network for a 403', () => {
    const result = classifyOverviewLoadError({ response: { status: 403 } });
    expect(result.kind).toBe('forbidden');
    expect(result.message).toMatch(/hr team/i);
    expect(result.message).not.toMatch(/connection/i);
  });

  it('asks for a retry on a 500', () => {
    const result = classifyOverviewLoadError({ response: { status: 500 } });
    expect(result.kind).toBe('server');
    expect(result.message).toMatch(/try again/i);
    expect(result.message).not.toMatch(/connection/i);
  });

  it('blames the network only when there is no HTTP response', () => {
    const result = classifyOverviewLoadError({ message: 'Network Error' });
    expect(result.kind).toBe('network');
    expect(result.message).toMatch(/connection/i);
  });
});
