/**
 * Slice 5 (policy bridge) — the domain router decides whether a question goes to
 * the immigration engine or the company-policy engine, deferring to a clarifier
 * when genuinely unsure. Deterministic; coverage-intent ("does my company pay
 * for…") beats an immigration noun, since each engine still grounds/refuses.
 */
import { describe, it, expect } from 'vitest';
import { classifyAssistantDomain } from './assistantDomainRouter';

describe('classifyAssistantDomain', () => {
  it.each([
    'What documents do I need for my visa?',
    'How long does the work permit take?',
    'Do I need an apostille for my passport?',
    'Where do I register my residence?',
  ])('routes immigration: %s', (q) => {
    expect(classifyAssistantDomain(q)).toBe('immigration');
  });

  it.each([
    'Does my company cover temporary housing?',
    'What is my relocation allowance?',
    'Will my employer reimburse my flights?',
    'Am I entitled to school fees for my kids?',
  ])('routes policy: %s', (q) => {
    expect(classifyAssistantDomain(q)).toBe('policy');
  });

  it.each([
    'Can you help me?',
    '',
    'Tell me more about this',
  ])('routes ambiguous: %s', (q) => {
    expect(classifyAssistantDomain(q)).toBe('ambiguous');
  });

  it('treats coverage-intent over a visa noun as policy', () => {
    expect(classifyAssistantDomain('Does my company pay for the visa?')).toBe('policy');
  });
});
