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
  it('renders just the label when the country is unknown', () => {
    const { container } = render(<CountryFlag country="Atlantis" />);
    expect(screen.getByText('Atlantis')).toBeInTheDocument();
    expect(container.querySelector('.fi')).toBeNull();
  });
});
