import { describe, expect, it } from 'vitest';
import { INTAKE_STEP_LABELS } from '../intakeSteps';

describe('INTAKE_STEP_LABELS', () => {
  it('names the first employee intake step Move details', () => {
    expect(INTAKE_STEP_LABELS[0]).toBe('Move details');
  });
});
