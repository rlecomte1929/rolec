import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { SuccessProbabilityDial } from '../SuccessProbabilityDial';

const DISCLAIMER =
  'This is an estimate of process complexity based on the official requirements for your corridor. ' +
  'It is not a legal guarantee of outcome. Immigration authorities exercise discretion.';

afterEach(() => cleanup());

describe('SuccessProbabilityDial', () => {
  it('refuses to render without a disclaimer prop', () => {
    // Suppress the expected React error boundary noise.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    // @ts-expect-error — intentionally omitting the required disclaimer.
    expect(() => render(<SuccessProbabilityDial scorePct={90} />)).toThrow(/disclaimer/i);
    spy.mockRestore();
  });

  it('refuses to render with a blank disclaimer', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<SuccessProbabilityDial scorePct={90} disclaimer="   " />)).toThrow(/disclaimer/i);
    spy.mockRestore();
  });

  it('always renders the disclaimer text when provided', () => {
    render(<SuccessProbabilityDial scorePct={90} disclaimer={DISCLAIMER} />);
    const note = screen.getByTestId('success-probability-disclaimer');
    expect(note).toHaveTextContent('not a legal guarantee');
    expect(note).toHaveTextContent('discretion');
  });

  // Visual smoke across all three colour bands.
  it.each([
    { pct: 90, band: 'On track' }, // green ≥80
    { pct: 70, band: 'Some complexity' }, // amber 60–79
    { pct: 40, band: 'High complexity' }, // red <60
  ])('renders the $band band for $pct%', ({ pct, band }) => {
    render(<SuccessProbabilityDial scorePct={pct} disclaimer={DISCLAIMER} />);
    expect(screen.getByText(`${pct}%`)).toBeInTheDocument();
    expect(screen.getByText(band)).toBeInTheDocument();
  });

  it('re-rounds the score to the nearest 5%', () => {
    render(<SuccessProbabilityDial scorePct={83} disclaimer={DISCLAIMER} />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('notes the platform-data basis when provided', () => {
    render(<SuccessProbabilityDial scorePct={88} disclaimer={DISCLAIMER} confidenceBasis="platform_data" />);
    expect(screen.getByText(/anonymised outcomes/i)).toBeInTheDocument();
  });
});
