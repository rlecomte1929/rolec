import { describe, it, expect } from 'vitest';
import { renderMarkdown } from './MarkdownTextarea';

// SEC-FE-5 — the hand-rolled markdown preview HTML-escapes input before applying
// its tiny bold/italic/list regex, so it cannot be an XSS vector. These tests lock
// that property so a future "improvement" can't silently reintroduce raw HTML.
describe('renderMarkdown — XSS safety', () => {
  it('escapes script tags in user input', () => {
    const out = renderMarkdown('<script>alert(1)</script>');
    expect(out).not.toContain('<script>');
    expect(out).toContain('&lt;script&gt;');
  });

  it('escapes img/onerror injection', () => {
    const out = renderMarkdown('<img src=x onerror=alert(1)>');
    expect(out).not.toContain('<img');
    expect(out).toContain('&lt;img');
  });

  it('escapes raw angle brackets even inside bold', () => {
    const out = renderMarkdown('**<b>x</b>**');
    // the user's <b> is escaped; only our own <strong> wrapper is real HTML
    expect(out).toContain('<strong>');
    expect(out).toContain('&lt;b&gt;');
    expect(out).not.toContain('<b>x</b>');
  });

  it('still renders the supported markdown subset', () => {
    expect(renderMarkdown('**bold**')).toContain('<strong>bold</strong>');
    expect(renderMarkdown('*italic*')).toContain('<em>italic</em>');
    expect(renderMarkdown('- a\n- b')).toContain('<ul');
  });
});
