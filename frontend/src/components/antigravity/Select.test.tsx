import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { Select } from './Select';

afterEach(cleanup);

const STATUS = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

describe('Select', () => {
  it('keeps caller order by default so status lists are not A–Z', () => {
    render(<Select value="pending" onChange={() => {}} options={STATUS} />);
    const labels = screen.getAllByRole('option').map((el) => el.textContent);
    expect(labels).toEqual(['Pending', 'Approved', 'Rejected']);
  });

  it('sorts by label when sort="label"', () => {
    render(<Select value="pending" onChange={() => {}} options={STATUS} sort="label" />);
    const labels = screen.getAllByRole('option').map((el) => el.textContent);
    expect(labels).toEqual(['Approved', 'Pending', 'Rejected']);
  });
});
