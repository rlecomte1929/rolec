import { describe, expect, it } from 'vitest';
import { blockerSummaryMessage } from './blockerSummaryCopy';

describe('blockerSummaryMessage', () => {
  it('reports an on-track state when there are no blocking items', () => {
    expect(blockerSummaryMessage(0)).toBe(
      'Your case is on track — no items are blocking your plan right now.',
    );
  });

  it('reports "10 items" for a case with ten blocking items', () => {
    expect(blockerSummaryMessage(10, 'Passport scans')).toBe(
      'You have 10 items to complete before your plan can move forward. The most important: Passport scans.',
    );
  });

  it('reports "3 items" for a case with three blocking items', () => {
    expect(blockerSummaryMessage(3, 'Employment letter')).toContain('You have 3 items to complete');
  });

  it('uses the singular noun for exactly one blocking item', () => {
    expect(blockerSummaryMessage(1, 'Bank statements')).toBe(
      'You have 1 item to complete before your plan can move forward. The most important: Bank statements.',
    );
  });

  it('omits the "most important" clause when no top task is available', () => {
    expect(blockerSummaryMessage(2)).toBe(
      'You have 2 items to complete before your plan can move forward.',
    );
  });

  it('never claims zero blockers while also implying work remains (no contradiction)', () => {
    // The contradiction the task fixes: a non-zero readiness gap with "0 blocking items".
    // Any positive count must surface a "to complete" instruction, never an on-track message.
    for (const n of [1, 3, 10]) {
      const msg = blockerSummaryMessage(n, 'Some task');
      expect(msg).toContain('to complete before your plan can move forward');
      expect(msg).not.toContain('on track');
    }
  });
});
