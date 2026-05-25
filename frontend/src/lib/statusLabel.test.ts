import { describe, it, expect } from 'vitest';
import { statusLabel } from './statusLabel';

describe('statusLabel', () => {
  // Immigration readiness
  it('maps GREEN → On track', () => expect(statusLabel('GREEN')).toBe('On track'));
  it('maps AMBER → Needs attention', () => expect(statusLabel('AMBER')).toBe('Needs attention'));
  it('maps RED → At risk', () => expect(statusLabel('RED')).toBe('At risk'));

  // Quote / RFQ
  it('maps fulfilled → Quote received', () => expect(statusLabel('fulfilled')).toBe('Quote received'));
  it('maps acknowledged → Acknowledged', () => expect(statusLabel('acknowledged')).toBe('Acknowledged'));

  // Claim / invite states
  it('maps invite_revoked → Invitation cancelled by HR message', () =>
    expect(statusLabel('invite_revoked')).toBe('Invitation cancelled by HR — contact them to reissue'));
  it('maps expired → Invitation expired message', () =>
    expect(statusLabel('expired')).toBe('Invitation expired — ask HR to resend'));
  it('maps claimed → Already accepted', () => expect(statusLabel('claimed')).toBe('Already accepted'));

  // General lifecycle
  it('maps pending → Pending', () => expect(statusLabel('pending')).toBe('Pending'));
  it('maps active → Active', () => expect(statusLabel('active')).toBe('Active'));
  it('maps inactive → Inactive', () => expect(statusLabel('inactive')).toBe('Inactive'));
  it('maps active_for_assistant → Active', () => expect(statusLabel('active_for_assistant')).toBe('Active'));
  it('maps draft → Draft', () => expect(statusLabel('draft')).toBe('Draft'));
  it('maps approved → Approved', () => expect(statusLabel('approved')).toBe('Approved'));
  it('maps rejected → Not approved', () => expect(statusLabel('rejected')).toBe('Not approved'));
  it('maps submitted → Submitted', () => expect(statusLabel('submitted')).toBe('Submitted'));

  // Task statuses
  it('maps not_started → Not started', () => expect(statusLabel('not_started')).toBe('Not started'));
  it('maps in_progress → In progress', () => expect(statusLabel('in_progress')).toBe('In progress'));
  it('maps done → Done', () => expect(statusLabel('done')).toBe('Done'));
  it('maps skipped → Skipped', () => expect(statusLabel('skipped')).toBe('Skipped'));
  it('maps overdue → Overdue', () => expect(statusLabel('overdue')).toBe('Overdue'));
  it('maps blocked → Blocked', () => expect(statusLabel('blocked')).toBe('Blocked'));
  it('maps revision_requested → Needs revision', () =>
    expect(statusLabel('revision_requested')).toBe('Needs revision'));

  // Form statuses
  it('maps auto_filled → Pre-filled', () => expect(statusLabel('auto_filled')).toBe('Pre-filled'));
  it('maps pending_doc → Waiting for document', () =>
    expect(statusLabel('pending_doc')).toBe('Waiting for document'));
  it('maps ready → Ready to submit', () => expect(statusLabel('ready')).toBe('Ready to submit'));

  // Edge cases
  it('returns — for empty string', () => expect(statusLabel('')).toBe('—'));
  it('title-cases unknown codes gracefully', () =>
    expect(statusLabel('some_new_status')).toBe('Some New Status'));
  it('accepts optional locale arg without throwing', () =>
    expect(() => statusLabel('active', 'fr')).not.toThrow());
});
