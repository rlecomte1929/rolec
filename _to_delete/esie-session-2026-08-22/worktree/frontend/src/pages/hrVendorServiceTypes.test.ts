import { describe, it, expect } from 'vitest';
import { rowServiceTypes, serviceTypeOptions, filterByServiceType } from './hrVendorServiceTypes';

const row = (service_types?: unknown) => ({ attributes: service_types === undefined ? {} : { service_types } });

describe('rowServiceTypes', () => {
  it('returns string tags and ignores empties / non-arrays', () => {
    expect(rowServiceTypes(row(['International', ' Storage ', '']))).toEqual(['International', ' Storage ']);
    expect(rowServiceTypes(row('International'))).toEqual([]);
    expect(rowServiceTypes(row(undefined))).toEqual([]);
    expect(rowServiceTypes({})).toEqual([]);
  });
});

describe('serviceTypeOptions', () => {
  it('is the sorted, case-insensitively de-duplicated union with first-seen casing', () => {
    const rows = [
      row(['International', 'Storage']),
      row(['international', 'Local']),
      row([]),
    ];
    expect(serviceTypeOptions(rows)).toEqual(['International', 'Local', 'Storage']);
  });
});

describe('filterByServiceType', () => {
  const rows = [
    { id: 'a', attributes: { service_types: ['International', 'Storage'] } },
    { id: 'b', attributes: { service_types: ['Local'] } },
    { id: 'c', attributes: {} }, // untagged
  ];

  it('empty filter returns every row ("All")', () => {
    expect(filterByServiceType(rows, '').map((r) => r.id)).toEqual(['a', 'b', 'c']);
  });

  it('narrows to rows whose tags include the selected type (case-insensitive)', () => {
    expect(filterByServiceType(rows, 'storage').map((r) => r.id)).toEqual(['a']);
    expect(filterByServiceType(rows, 'Local').map((r) => r.id)).toEqual(['b']);
  });

  it('untagged rows appear only under "All"', () => {
    expect(filterByServiceType(rows, 'International').some((r) => r.id === 'c')).toBe(false);
  });
});
