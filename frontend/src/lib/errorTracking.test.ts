import { describe, it, expect } from 'vitest';
import { scrubPii, redactUrl } from './errorTracking';

describe('scrubPii', () => {
  it('redacts emails', () => {
    expect(scrubPii('failed for jane.doe@example.com here')).toBe('failed for [email] here');
  });

  it('redacts JWT / sk- tokens and Bearer headers', () => {
    expect(scrubPii('token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')).toBe('token [token]');
    expect(scrubPii('key sk-ABCDEF1234567890')).toBe('key [token]');
    expect(scrubPii('Authorization: Bearer abc.def-123')).toBe('Authorization: [token]');
  });

  it('redacts UUIDs (case ids etc.)', () => {
    expect(scrubPii('case a2230534-1111-2222-3333-444455556666 failed')).toBe('case [id] failed');
  });

  it('leaves clean text untouched', () => {
    expect(scrubPii('Cannot read property x of undefined')).toBe('Cannot read property x of undefined');
  });
});

describe('redactUrl', () => {
  it('drops the query string', () => {
    expect(redactUrl('https://app.relopass.com/employee/case/x?token=secret&email=a@b.com'))
      .toBe('https://app.relopass.com/employee/case/x');
  });

  it('scrubs a UUID in the path', () => {
    expect(redactUrl('https://app.relopass.com/case/a2230534-1111-2222-3333-444455556666'))
      .toBe('https://app.relopass.com/case/[id]');
  });
});
