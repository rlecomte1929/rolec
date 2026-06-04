import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { FactorsPanel } from '../FactorsPanel';
import { successProbability, type ScoringRoadmap } from '../successProbability';

afterEach(() => cleanup());

const WEAKENED: ScoringRoadmap = {
  steps: [
    { id: 'a', title: 'EEA registration', confidence: 'high' },
    { id: 'b', title: 'Tax registration', confidence: 'low' },
    { id: 'c', title: 'Work permit', confidence: 'unknown' },
  ],
};

describe('FactorsPanel', () => {
  it('is collapsed by default and expands on click', () => {
    const { factors } = successProbability(WEAKENED);
    render(<FactorsPanel factors={factors} />);

    const header = screen.getByRole('button', { name: /factors affecting your score/i });
    expect(header).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(header);
    expect(header).toHaveAttribute('aria-expanded', 'true');
  });

  it('toggles with the keyboard (Enter / Space)', () => {
    const { factors } = successProbability(WEAKENED);
    render(<FactorsPanel factors={factors} defaultExpanded={false} />);
    const header = screen.getByRole('button', { name: /factors affecting your score/i });

    fireEvent.keyDown(header, { key: 'Enter' });
    expect(header).toHaveAttribute('aria-expanded', 'true');
    fireEvent.keyDown(header, { key: ' ' });
    expect(header).toHaveAttribute('aria-expanded', 'false');
  });

  it('renders factors that match the computed score (low/unknown lower it)', () => {
    const { factors } = successProbability(WEAKENED);
    render(<FactorsPanel factors={factors} defaultExpanded />);

    // The LOW tax-registration and UNKNOWN work-permit steps appear as lowering factors.
    expect(screen.getByText(/Tax registration — LOW confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Work permit — UNKNOWN confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/EEA registration — HIGH confidence/i)).toBeInTheDocument();
  });

  it('shows an empty-state message when there are no factors', () => {
    render(<FactorsPanel factors={[]} defaultExpanded />);
    expect(screen.getByText(/no scoring factors are available yet/i)).toBeInTheDocument();
  });
});
