import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Select } from './Select';

afterEach(cleanup);

describe('Select', () => {
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
