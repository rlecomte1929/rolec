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

  it('fullWidth constrains the native select so long options cannot overflow a grid track', () => {
    render(
      <Select
        fullWidth
        label="Company"
        value="long"
        onChange={() => {}}
        options={[{ value: 'long', label: 'Google Ireland T18-A-1786634420882' }]}
      />,
    );
    const select = screen.getByRole('combobox');
    expect(select).toHaveClass('w-full');
    expect(select).toHaveClass('min-w-0');
    expect(select).toHaveClass('max-w-full');
    expect(select.parentElement).toHaveClass('min-w-0');
  });
});
