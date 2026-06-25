import { describe, it, expect } from 'vitest';
import { assertSafeUrl } from '../url';

describe('assertSafeUrl', () => {
  it('allows http/https absolute URLs', () => {
    expect(assertSafeUrl('https://example.com/doc.pdf')).toBe('https://example.com/doc.pdf');
    expect(assertSafeUrl('http://example.com')).toBe('http://example.com');
  });

  it('allows relative paths, hashes, queries and protocol-relative URLs', () => {
    expect(assertSafeUrl('/forms/abc')).toBe('/forms/abc');
    expect(assertSafeUrl('./x')).toBe('./x');
    expect(assertSafeUrl('#section')).toBe('#section');
    expect(assertSafeUrl('?q=1')).toBe('?q=1');
    expect(assertSafeUrl('//cdn.example.com/x.js')).toBe('//cdn.example.com/x.js');
    expect(assertSafeUrl('docs/file.pdf')).toBe('docs/file.pdf');
  });

  it('rejects javascript: / data: / vbscript: / other schemes', () => {
    expect(assertSafeUrl('javascript:alert(1)')).toBe('#');
    expect(assertSafeUrl('JaVaScRiPt:alert(1)')).toBe('#');
    expect(assertSafeUrl('  javascript:alert(1)')).toBe('#');
    expect(assertSafeUrl('data:text/html,<script>alert(1)</script>')).toBe('#');
    expect(assertSafeUrl('vbscript:msgbox(1)')).toBe('#');
    expect(assertSafeUrl('file:///etc/passwd')).toBe('#');
  });

  it('defeats control-char obfuscation (java\\tscript:)', () => {
    expect(assertSafeUrl('java\tscript:alert(1)')).toBe('#');
    expect(assertSafeUrl('java\nscript:alert(1)')).toBe('#');
  });

  it('returns the fallback for empty/nullish input', () => {
    expect(assertSafeUrl(null)).toBe('#');
    expect(assertSafeUrl(undefined)).toBe('#');
    expect(assertSafeUrl('')).toBe('#');
    expect(assertSafeUrl('   ')).toBe('#');
  });

  it('honours a custom fallback (empty string for window.open guards)', () => {
    expect(assertSafeUrl('javascript:alert(1)', '')).toBe('');
    expect(assertSafeUrl('https://ok.com', '')).toBe('https://ok.com');
  });
});
