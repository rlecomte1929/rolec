import { test, expect } from '@playwright/test';
import { requestWithGatewayRetry } from '../_helpers';

/**
 * Harness contract test for requestWithGatewayRetry — the API-level analog of the
 * assertLogicalPage B10 cold-start tolerance fix. No network (fake `send` thunks),
 * so it's deterministic and fast. Locks the deploy-window tolerance: a transient
 * gateway 502/503/504 (Render rolling restart on every merge to main) must be
 * retried so it doesn't file a false-positive P0, while a genuinely-unreachable API
 * (persistent 5xx) must still surface as a failure. backoffMs:1 keeps it instant.
 */
const fastOpts = { retries: 3, backoffMs: 1 };

function statusStub(code: number) {
  return { status: () => code };
}

test.describe('requestWithGatewayRetry — deploy-window gateway tolerance', () => {
  test('a transient 502 that recovers returns the eventual 200 (slow ≠ down)', async () => {
    const seq = [502, 502, 200];
    let i = 0;
    const res = await requestWithGatewayRetry(() => Promise.resolve(statusStub(seq[i++])), fastOpts);
    expect(res.status()).toBe(200);
    expect(i).toBe(3); // retried past both 502s
  });

  test('a persistent gateway error still fails after the retries (real outage caught)', async () => {
    let calls = 0;
    const res = await requestWithGatewayRetry(() => { calls++; return Promise.resolve(statusStub(503)); }, fastOpts);
    expect(res.status()).toBe(503); // returns the last response — the `< 500` assertion still fails
    expect(calls).toBe(fastOpts.retries + 1); // initial + 3 retries
  });

  test('a network throw during a restart is retried then recovers', async () => {
    let i = 0;
    const res = await requestWithGatewayRetry(() => {
      i++;
      if (i < 3) return Promise.reject(new Error('ECONNRESET'));
      return Promise.resolve(statusStub(200));
    }, fastOpts);
    expect(res.status()).toBe(200);
    expect(i).toBe(3);
  });

  test('a non-gateway response (real app 500) is NOT retried — returned immediately', async () => {
    let calls = 0;
    const res = await requestWithGatewayRetry(() => { calls++; return Promise.resolve(statusStub(500)); }, fastOpts);
    expect(res.status()).toBe(500);
    expect(calls).toBe(1); // a bare 500 is an app error, not a gateway restart — no retry
  });

  test('a 2xx on the first try makes no extra calls', async () => {
    let calls = 0;
    const res = await requestWithGatewayRetry(() => { calls++; return Promise.resolve(statusStub(200)); }, fastOpts);
    expect(res.status()).toBe(200);
    expect(calls).toBe(1);
  });
});
