import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { CountrySelect } from './CountrySelect';

afterEach(cleanup);

describe('CountrySelect', () => {
  it('shows the full country name for a stored ISO value', () => {
    render(<CountrySelect value="NO" onChange={() => {}} />);
    expect(screen.getByText('Norway')).toBeInTheDocument();
  });

  it('lists full names (not ISO codes) in the open dropdown', () => {
    render(<CountrySelect value="" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Ireland')).toBeInTheDocument();
    expect(screen.queryByText('Select a country')).toBeInTheDocument();
  });

  it('resolves API codes to full names when restricting the list', () => {
    render(<CountrySelect value="" onChange={() => {}} codes={['NO', 'FR']} allowEmpty />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Norway')).toBeInTheDocument();
    expect(screen.getByText('France')).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'NO' })).not.toBeInTheDocument();
  });

  it('emits the ISO code when a name is chosen', () => {
    const onChange = vi.fn();
    render(<CountrySelect value="" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('option', { name: 'Ireland' }));
    expect(onChange).toHaveBeenCalledWith('IE');
  });
});
