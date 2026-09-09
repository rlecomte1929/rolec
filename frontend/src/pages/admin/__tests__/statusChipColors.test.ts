import { describe, it, expect } from 'vitest';
import { STATUS_STYLES } from '../AdminAttestationsPage';
import { STATUS_CLASSES } from '../OutreachPage';
import { STATUS_MAP } from '../../../components/outreach/ProspectDrawer';

describe('status chips (no indigo)', () => {
  it('maps in_review and message_sent to navy, not indigo', () => {
    expect(STATUS_STYLES.in_review).toContain('navy');
    expect(STATUS_STYLES.in_review).not.toMatch(/indigo/);
    expect(STATUS_CLASSES.message_sent).toContain('navy');
    expect(STATUS_CLASSES.message_sent).not.toMatch(/indigo/);
    expect(STATUS_MAP.message_sent).toContain('navy');
    expect(STATUS_MAP.message_sent).not.toMatch(/indigo/);
  });
});
