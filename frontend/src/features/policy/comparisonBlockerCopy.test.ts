import { describe, it, expect } from 'vitest';
import { comparisonBlockerMessage } from './comparisonBlockerCopy';

describe('comparisonBlockerMessage (TASK-004)', () => {
  it('never renders the raw internal code for a missing category', () => {
    const msg = comparisonBlockerMessage('MISSING_COMPARISON_CATEGORY:shipment');
    expect(msg).not.toContain('MISSING');
    expect(msg).not.toContain('_');
    expect(msg).toContain('Shipment');
    expect(msg).toContain('Policy builder');
  });

  it('humanizes multi-word benefit keys', () => {
    const msg = comparisonBlockerMessage('MISSING_COMPARISON_CATEGORY:temporary_housing');
    expect(msg).toContain('Temporary Housing');
    expect(msg).not.toContain('MISSING');
    expect(msg).not.toContain('temporary_housing');
  });

  it('handles the covered-without-decision-fields code', () => {
    const msg = comparisonBlockerMessage('COVERED_WITHOUT_DECISION_FIELDS:temporary_housing');
    expect(msg).toContain('Temporary Housing');
    expect(msg).not.toContain('COVERED_WITHOUT');
  });

  it('maps the no-policy and error codes to plain messages', () => {
    expect(comparisonBlockerMessage('NO_MATCHING_PUBLISHED_POLICY')).not.toContain('_');
    expect(comparisonBlockerMessage('ERROR_LOADING_POLICY')).not.toContain('ERROR_');
  });

  it('falls back to a generic message for an unknown code (never the raw code)', () => {
    const msg = comparisonBlockerMessage('SOME_FUTURE_BLOCKER:weird_key');
    expect(msg).not.toContain('SOME_FUTURE_BLOCKER');
    expect(msg).not.toContain('weird_key');
    expect(msg).not.toContain('_');
    expect(msg).toContain('Policy builder');
  });
});
