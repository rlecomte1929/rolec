/**
 * Combobox (AIQ-1656) — searchable suggestions that never block free-text entry.
 *
 * Covers:
 *   1. Focus opens the suggestion list.
 *   2. Typing filters the options (case-insensitive contains).
 *   3. Clicking an option commits it via onChange.
 *   4. A typed value that isn't an option is still passed through (never blocked).
 */
import '@testing-library/jest-dom/vitest';
import React, { useState } from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { Combobox } from '../Combobox';

afterEach(cleanup);

function Harness({ options }: { options: string[] }) {
  const [value, setValue] = useState('');
  return <Combobox value={value} onChange={setValue} options={options} testId="cb" />;
}

const CITIES = ['Berlin', 'Munich', 'Frankfurt', 'Hamburg'];

describe('Combobox', () => {
  it('opens the suggestion list on focus', () => {
    render(<Harness options={CITIES} />);
    fireEvent.focus(screen.getByTestId('cb'));
    expect(screen.getByText('Berlin')).toBeInTheDocument();
    expect(screen.getByText('Munich')).toBeInTheDocument();
  });

  it('filters options case-insensitively as you type', () => {
    render(<Harness options={CITIES} />);
    const input = screen.getByTestId('cb');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'fr' } });
    expect(screen.getByText('Frankfurt')).toBeInTheDocument();
    expect(screen.queryByText('Berlin')).not.toBeInTheDocument();
  });

  it('commits a clicked option', () => {
    render(<Harness options={CITIES} />);
    const input = screen.getByTestId('cb') as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.click(screen.getByText('Munich'));
    expect(input.value).toBe('Munich');
  });

  it('keeps a typed value that is not in the options (never blocks)', () => {
    render(<Harness options={CITIES} />);
    const input = screen.getByTestId('cb') as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Timbuktu' } });
    expect(input.value).toBe('Timbuktu');
  });
});
