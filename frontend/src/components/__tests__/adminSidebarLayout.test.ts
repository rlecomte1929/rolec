import { describe, it, expect, beforeEach } from 'vitest';
import {
  reconcileAdminLayout,
  applyAdminLayout,
  readAdminLayout,
  writeAdminLayout,
  clearAdminLayout,
  type AdminLayoutEntry,
} from '../adminSidebarLayout';

type Item = { id: string; label: string; group: string };

const CODE: Item[] = [
  { id: 'a', label: 'A', group: 'Overview' },
  { id: 'b', label: 'B', group: 'Overview' },
  { id: 'c', label: 'C', group: 'Content' },
  { id: 'd', label: 'D', group: 'Content' },
];

describe('reconcileAdminLayout', () => {
  it('returns the code order/groups when there is no stored override', () => {
    expect(reconcileAdminLayout(CODE, null)).toEqual([
      { id: 'a', group: 'Overview' },
      { id: 'b', group: 'Overview' },
      { id: 'c', group: 'Content' },
      { id: 'd', group: 'Content' },
    ]);
  });

  it('honours the stored order + group and drops ids no longer in code', () => {
    const stored: AdminLayoutEntry[] = [
      { id: 'd', group: 'Overview' }, // moved into Overview + reordered first
      { id: 'a', group: 'Overview' },
      { id: 'gone', group: 'Content' }, // no longer exists in code → dropped
      { id: 'c', group: 'Content' },
    ];
    expect(reconcileAdminLayout(CODE, stored)).toEqual([
      { id: 'd', group: 'Overview' },
      { id: 'a', group: 'Overview' },
      { id: 'c', group: 'Content' },
      { id: 'b', group: 'Overview' }, // new/absent code item appended with its code group
    ]);
  });
});

describe('applyAdminLayout', () => {
  it('reorders and regroups the full code items per the layout, preserving other fields', () => {
    const layout: AdminLayoutEntry[] = [
      { id: 'c', group: 'Overview' },
      { id: 'a', group: 'Overview' },
    ];
    expect(applyAdminLayout(CODE, layout)).toEqual([
      { id: 'c', label: 'C', group: 'Overview' },
      { id: 'a', label: 'A', group: 'Overview' },
    ]);
  });

  it('ignores layout entries whose id is missing from code', () => {
    const layout: AdminLayoutEntry[] = [{ id: 'ghost', group: 'X' }, { id: 'b', group: 'Content' }];
    expect(applyAdminLayout(CODE, layout)).toEqual([{ id: 'b', label: 'B', group: 'Content' }]);
  });
});

describe('storage round-trip', () => {
  beforeEach(() => {
    // jsdom in this config doesn't expose window.localStorage — install a minimal shim.
    if (typeof window !== 'undefined' && !window.localStorage) {
      const store = new Map<string, string>();
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: {
          getItem: (k: string) => store.get(k) ?? null,
          setItem: (k: string, v: string) => void store.set(k, String(v)),
          removeItem: (k: string) => void store.delete(k),
          clear: () => store.clear(),
        },
      });
    }
    clearAdminLayout();
  });

  it('reads back what was written and clears', () => {
    expect(readAdminLayout()).toBeNull();
    const entries: AdminLayoutEntry[] = [{ id: 'a', group: 'Overview' }];
    writeAdminLayout(entries);
    expect(readAdminLayout()).toEqual(entries);
    clearAdminLayout();
    expect(readAdminLayout()).toBeNull();
  });

  it('returns null for malformed stored JSON', () => {
    window.localStorage.setItem('admin_sidebar_layout_v1', '{not json');
    expect(readAdminLayout()).toBeNull();
  });
});
