/**
 * Slice 3a — diff category grouping tests.
 *
 * Locks down: canonical category order, fallback bucket, small-section
 * default-open heuristic, and the collapsed-by-default UX for the
 * common big-diff case the user complained about.
 */
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import {
  CollapsibleCategory,
  groupByCategory,
  shouldDefaultOpen,
} from '../diffCategoryGrouping';

afterEach(cleanup);

describe('groupByCategory', () => {
  it('returns categories in canonical order', () => {
    const rows = [
      { id: 1, category: 'tax_payroll' },
      { id: 2, category: 'compensation_allowances' },
      { id: 3, category: 'pre_assignment_support' },
    ];
    const groups = groupByCategory(rows, (r) => r.category);
    expect(groups.map((g) => g.key)).toEqual([
      'pre_assignment_support',
      'compensation_allowances',
      'tax_payroll',
    ]);
  });

  it('uses canonical labels, not raw keys', () => {
    const groups = groupByCategory([{ category: 'compensation_allowances' }], (r) => r.category);
    expect(groups[0].label).toBe('Compensation & Allowances');
  });

  it('drops empty buckets', () => {
    const groups = groupByCategory(
      [{ category: 'tax_payroll' }],
      (r) => r.category
    );
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('tax_payroll');
  });

  it('puts unknown categories at the end under "Other"', () => {
    const groups = groupByCategory(
      [
        { category: 'tax_payroll' },
        { category: '' },
        { category: undefined },
        { category: 'pre_assignment_support' },
      ],
      (r) => r.category
    );
    expect(groups.map((g) => g.label)).toEqual([
      'Pre-Assignment Support',
      'Tax & Payroll',
      'Other',
    ]);
    // Both null/empty rows merged into "Other"
    expect(groups[2].rows).toHaveLength(2);
  });
});

describe('shouldDefaultOpen', () => {
  it('opens small sections (<= 5 rows) automatically', () => {
    expect(shouldDefaultOpen(1)).toBe(true);
    expect(shouldDefaultOpen(5)).toBe(true);
  });
  it('keeps larger sections collapsed', () => {
    expect(shouldDefaultOpen(6)).toBe(false);
    expect(shouldDefaultOpen(41)).toBe(false);
  });
  it('treats zero as collapsed (caller should not render at all)', () => {
    expect(shouldDefaultOpen(0)).toBe(false);
  });
});

describe('CollapsibleCategory', () => {
  const group = {
    key: 'compensation_allowances',
    label: 'Compensation & Allowances',
    rows: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
  };

  it('renders the label, count, and is collapsed by default', () => {
    render(
      <CollapsibleCategory
        group={group}
        renderRow={(r) => <li data-testid="r">{(r as { id: string }).id}</li>}
      />
    );
    expect(screen.getByText('Compensation & Allowances')).toBeInTheDocument();
    expect(screen.getByText('(3)')).toBeInTheDocument();
    expect(screen.queryAllByTestId('r')).toHaveLength(0); // collapsed
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
  });

  it('expands on click and shows rows', () => {
    render(
      <CollapsibleCategory
        group={group}
        renderRow={(r) => <li data-testid="r">{(r as { id: string }).id}</li>}
      />
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByTestId('r')).toHaveLength(3);
  });

  it('honors defaultOpen when explicitly set', () => {
    render(
      <CollapsibleCategory
        group={group}
        defaultOpen
        renderRow={(r) => <li data-testid="r">{(r as { id: string }).id}</li>}
      />
    );
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByTestId('r')).toHaveLength(3);
  });
});
