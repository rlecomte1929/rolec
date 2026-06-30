import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { Switch } from './Switch';

afterEach(cleanup);

describe('Switch', () => {
  it('exposes role=switch with aria-checked reflecting state', () => {
    const { rerender } = render(<Switch checked={false} onChange={() => {}} aria-label="Live" />);
    const sw = screen.getByRole('switch');
    expect(sw).toHaveAttribute('aria-checked', 'false');
    rerender(<Switch checked onChange={() => {}} aria-label="Live" />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('toggles to the opposite state on click', () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} aria-label="Live" />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('associates a visible label', () => {
    render(<Switch checked onChange={() => {}} label="Enabled" />);
    expect(screen.getByRole('switch', { name: 'Enabled' })).toBeInTheDocument();
  });

  it('does not fire onChange when disabled', () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} disabled aria-label="Live" />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
