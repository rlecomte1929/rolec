/**
 * [AIQ-918] RefreshButton.test.tsx
 *
 * The standard subordinate refresh control: keeps manual refresh available
 * (calls onClick), exposes an accessible name, and reflects the loading state
 * without removing the affordance.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { RefreshButton } from './RefreshButton';

expect.extend(matchers);
afterEach(cleanup);

describe('RefreshButton', () => {
  it('calls onClick when pressed', () => {
    const onClick = vi.fn();
    render(<RefreshButton onClick={onClick} />);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is a low-emphasis control, not a primary CTA (no primary/outline styling)', () => {
    render(<RefreshButton onClick={() => {}} label="Refresh" />);
    const btn = screen.getByRole('button', { name: 'Refresh' });
    // ghost variant: no solid primary background, no outline border classes
    expect(btn.className).not.toMatch(/bg-\[#0b2b43\]/); // primary
    expect(btn.className).not.toMatch(/border-2/); // outline
    expect(btn.className).toMatch(/text-sm/); // small size
  });

  it('uses the label as the accessible name and shows it when provided', () => {
    render(<RefreshButton onClick={() => {}} label="Refresh assignment" />);
    expect(screen.getByRole('button', { name: 'Refresh assignment' })).toBeInTheDocument();
    expect(screen.getByText('Refresh assignment')).toBeInTheDocument();
  });

  it('disables and announces "Refreshing" while loading', () => {
    const onClick = vi.fn();
    render(<RefreshButton onClick={onClick} loading label="Refresh" />);
    const btn = screen.getByRole('button', { name: 'Refreshing' });
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});
