import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { ConfirmFromIntake } from './ConfirmFromIntake';

afterEach(cleanup);

const ROWS = [
  { label: 'Legal name', value: 'Priya Nair' },
  { label: 'Nationality', value: 'Indian', flag: 'Indian' },
];

describe('ConfirmFromIntake', () => {
  it('renders each carried-over field as a read-only value (no inputs)', () => {
    const { container } = render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={() => {}} />);
    expect(screen.getByText('Priya Nair')).toBeInTheDocument();
    expect(screen.getByText('Indian')).toBeInTheDocument();
    expect(container.querySelector('input')).toBeNull(); // ask-once: never a blank input
  });
  it('renders a flag when a row provides one', () => {
    const { container } = render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={() => {}} />);
    expect(container.querySelector('.fi.fi-in')).toBeTruthy();
  });
  it('fires onConfirmAll when the confirm button is clicked', () => {
    const onConfirmAll = vi.fn();
    render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={onConfirmAll} />);
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    expect(onConfirmAll).toHaveBeenCalled();
  });
});
