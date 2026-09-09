import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { CountryFlag } from './CountryFlag';

afterEach(cleanup);

describe('CountryFlag', () => {
  it('renders the flag glyph plus the visible country label', () => {
    const { container } = render(<CountryFlag country="Indian" />);
    expect(screen.getByText('Indian')).toBeInTheDocument();
    expect(container.querySelector('.fi.fi-in')).toBeTruthy();
  });
  it('marks the flag glyph as decorative (aria-hidden)', () => {
    const { container } = render(<CountryFlag country="Germany" />);
    expect(container.querySelector('.fi.fi-de')?.getAttribute('aria-hidden')).toBe('true');
  });
  it('renders Norway for the ISO code NO (not the letters NO)', () => {
    const { container } = render(<CountryFlag country="NO" />);
    expect(screen.getByText('Norway')).toBeInTheDocument();
    expect(container.querySelector('.fi.fi-no')).toBeTruthy();
  });
  it('renders a flag for a full name that is not in the old corridor map', () => {
    const { container } = render(<CountryFlag country="Argentina" />);
    expect(screen.getByText('Argentina')).toBeInTheDocument();
    expect(container.querySelector('.fi.fi-ar')).toBeTruthy();
  });
  it('applies flag-icons ISO classes for FR/GB without a visible label', () => {
    const { container, rerender } = render(<CountryFlag country="FR" hideLabel />);
    expect(container.querySelector('.fi.fi-fr')).toBeTruthy();
    rerender(<CountryFlag country="GB" hideLabel />);
    expect(container.querySelector('.fi.fi-gb')).toBeTruthy();
  });
  it('renders just the label when the country is unknown', () => {
    const { container } = render(<CountryFlag country="Atlantis" />);
    expect(screen.getByText('Atlantis')).toBeInTheDocument();
    expect(container.querySelector('.fi')).toBeNull();
  });
});
