import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { CountryCoverageText } from './CountryCoverageText';

afterEach(cleanup);

describe('CountryCoverageText', () => {
  it('replaces ISO codes in a coverage summary with full names', () => {
    render(<CountryCoverageText summary="Global | NO, FR" />);
    expect(screen.getByText('Norway')).toBeInTheDocument();
    expect(screen.getByText('France')).toBeInTheDocument();
    expect(screen.getByText(/Global/)).toBeInTheDocument();
    expect(screen.queryByText('NO')).not.toBeInTheDocument();
  });
});
