import { describe, it, expect } from 'vitest';
import { deriveRiskItems, isVisaAlert, daysUntil } from './riskDashboard.helpers';
import type { CommandCenterCaseRow } from '../../../api/client';
import type { ComplianceAlert } from '../../../api/compliance';

const mkCase = (o: Partial<CommandCenterCaseRow>): CommandCenterCaseRow =>
  ({ id: o.id ?? 'x', employeeIdentifier: 'e', status: 'active', riskStatus: 'green', tasksDonePercent: 0, ...o } as CommandCenterCaseRow);

describe('deriveRiskItems', () => {
  it('keeps only non-green cases', () => {
    const items = deriveRiskItems([
      mkCase({ id: 'g', riskStatus: 'green' }),
      mkCase({ id: 'r', riskStatus: 'red' }),
      mkCase({ id: 'y', riskStatus: 'yellow' }),
    ]);
    expect(items.map((c) => c.id)).toEqual(['r', 'y']);
  });

  it('orders red before yellow, then soonest move first', () => {
    const items = deriveRiskItems([
      mkCase({ id: 'y-soon', riskStatus: 'yellow', daysUntilMove: 3 }),
      mkCase({ id: 'r-late', riskStatus: 'red', daysUntilMove: 40 }),
      mkCase({ id: 'r-soon', riskStatus: 'red', daysUntilMove: 5 }),
    ]);
    expect(items.map((c) => c.id)).toEqual(['r-soon', 'r-late', 'y-soon']);
  });

  it('empty input → empty', () => {
    expect(deriveRiskItems([])).toEqual([]);
  });
});

const mkAlert = (o: Partial<ComplianceAlert>): ComplianceAlert =>
  ({ id: 'a', case_id: 'c', status: 'open', severity: 'high', category: '', description: null, detail: {}, fired_at: null, employee_id: null, host_country: null, home_country: null, ...o } as ComplianceAlert);

describe('isVisaAlert / daysUntil', () => {
  it('matches visa/permit/residence/expiry categories', () => {
    expect(isVisaAlert(mkAlert({ category: 'permit_expiring' }))).toBe(true);
    expect(isVisaAlert(mkAlert({ category: 'other', description: 'visa expires soon' }))).toBe(true);
    expect(isVisaAlert(mkAlert({ category: 'missing_reg_number' }))).toBe(false);
  });
  it('reads days_until from detail, else +Infinity', () => {
    expect(daysUntil(mkAlert({ detail: { days_until: 14 } }))).toBe(14);
    expect(daysUntil(mkAlert({ detail: {} }))).toBe(Number.POSITIVE_INFINITY);
  });
});
