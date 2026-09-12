import { describe, expect, it } from 'vitest';
import { conversationFromSummary } from './utils';

describe('conversationFromSummary', () => {
  it('uses host country as the list subtitle so per-case threads are distinguishable', () => {
    const c = conversationFromSummary({
      assignment_id: 'aid-1',
      employee_name: 'probe spine 1786643842',
      last_message_preview: 'hello',
      case_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      host_country: 'SG',
    });
    expect(c.list_subtitle).toBe('Singapore');
  });

  it('falls back to a short case ref when destination is missing', () => {
    const c = conversationFromSummary({
      assignment_id: 'aid-2',
      employee_name: 'MSG02 Probe',
      case_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
    });
    expect(c.list_subtitle).toBe('Case EEEEEEEE');
  });
});
