import { describe, expect, it } from 'vitest';
import {
  OFFICE_UNKNOWN,
  SELF_EMPLOYED_CONTRACT,
  applyWorkModePatch,
  hydrateWorkMode,
  workAndPlaceComplete,
  type WorkMode,
} from './workStepComplete';

const employed = {
  work_mode: 'employed' as WorkMode,
  job_title: 'Engineer',
  contract_type: 'Permanent',
  contract_start: '2026-10-01',
  office_address: '1 Rue de Rivoli, Paris',
  work_pattern: 'Hybrid',
  salary_band: '50–100k€',
  assignment_type: 'LTA',
};

describe('workAndPlaceComplete (BUG-260828-87B8)', () => {
  it('still requires start date and office for employed people', () => {
    expect(workAndPlaceComplete({ ...employed, contract_start: '' })).toBe(false);
    expect(workAndPlaceComplete({ ...employed, office_address: '' })).toBe(false);
    expect(workAndPlaceComplete(employed)).toBe(true);
  });

  it('lets entrepreneurs skip contract start and office', () => {
    expect(
      workAndPlaceComplete({
        ...employed,
        work_mode: 'self_employed',
        contract_type: SELF_EMPLOYED_CONTRACT,
        contract_start: '',
        office_address: '',
      }),
    ).toBe(true);
  });

  it('lets digital nomads skip office, contract, and work-pattern chips', () => {
    expect(
      workAndPlaceComplete({
        ...employed,
        work_mode: 'digital_nomad',
        contract_type: '',
        contract_start: '',
        office_address: '',
        work_pattern: '',
      }),
    ).toBe(true);
  });

  it('still requires job title and income band in every mode', () => {
    expect(workAndPlaceComplete({ ...employed, work_mode: 'digital_nomad', job_title: '' })).toBe(
      false,
    );
    expect(workAndPlaceComplete({ ...employed, work_mode: 'self_employed', salary_band: '' })).toBe(
      false,
    );
  });
});

describe('applyWorkModePatch', () => {
  it('defaults nomads to fully remote and STA when they were on the LTA default', () => {
    const next = applyWorkModePatch(employed, 'digital_nomad');
    expect(next.work_mode).toBe('digital_nomad');
    expect(next.work_pattern).toBe('Fully remote');
    expect(next.assignment_type).toBe('STA');
  });

  it('does not overwrite a nomad who already chose PERMANENT', () => {
    const next = applyWorkModePatch({ ...employed, assignment_type: 'PERMANENT' }, 'digital_nomad');
    expect(next.assignment_type).toBe('PERMANENT');
  });

  it('sets the entrepreneur contract label and restores Permanent when switching back', () => {
    const self = applyWorkModePatch(employed, 'self_employed');
    expect(self.contract_type).toBe(SELF_EMPLOYED_CONTRACT);
    expect(applyWorkModePatch(self, 'employed').contract_type).toBe('Permanent');
  });

  it('keeps an unknown-office token valid for employed people', () => {
    expect(workAndPlaceComplete({ ...employed, office_address: OFFICE_UNKNOWN })).toBe(true);
  });
});

describe('hydrateWorkMode', () => {
  it('infers entrepreneur from the old contract-type label', () => {
    const next = hydrateWorkMode({
      work_mode: 'employed' as WorkMode,
      contract_type: SELF_EMPLOYED_CONTRACT,
    });
    expect(next.work_mode).toBe('self_employed');
  });

  it('defaults missing or unknown modes to employed', () => {
    expect(hydrateWorkMode({ contract_type: 'Permanent' }).work_mode).toBe('employed');
    expect(hydrateWorkMode({ work_mode: 'contractor', contract_type: 'Fixed-term' }).work_mode).toBe(
      'employed',
    );
  });
});
