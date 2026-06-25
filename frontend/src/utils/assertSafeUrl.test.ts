import { describe, it, expect } from 'vitest';
import { assertSafeUrl } from './assertSafeUrl';

describe('assertSafeUrl', () => {
  it('allows http(s) absolute URLs', () => {
    expect(assertSafeUrl('https://example.com/doc.pdf')).toBe('https://example.com/doc.pdf');
    expect(assertSafeUrl('http://example.com')).toBe('http://example.com');
  });

  it('allows relative paths, anchors, and query strings', () => {
    expect(assertSafeUrl('/employee/dashboard')).toBe('/employee/dashboard');
    expect(assertSafeUrl('./x')).toBe('./x');
    expect(assertSafeUrl('#section')).toBe('#section');
    expect(assertSafeUrl('?tab=2')).toBe('?tab=2');
  });

  it('allows mailto/tel', () => {
    expect(assertSafeUrl('mailto:a@b.com')).toBe('mailto:a@b.com');
    expect(assertSafeUrl('tel:+15551234')).toBe('tel:+15551234');
  });

  it('rejects dangerous schemes → fallback', () => {
    expect(assertSafeUrl('javascript:alert(1)')).toBe('#');
    expect(assertSafeUrl('JavaScript:alert(1)')).toBe('#');
    expect(assertSafeUrl('data:text/html,<script>alert(1)</script>')).toBe('#');
    expect(assertSafeUrl('vbscript:msgbox(1)')).toBe('#');
  });

  it('rejects empty/nullish → fallback', () => {
    expect(assertSafeUrl(null)).toBe('#');
    expect(assertSafeUrl(undefined)).toBe('#');
    expect(assertSafeUrl('   ')).toBe('#');
  });

  it('honors a custom fallback', () => {
    expect(assertSafeUrl('javascript:x', '/safe')).toBe('/safe');
  });
});
