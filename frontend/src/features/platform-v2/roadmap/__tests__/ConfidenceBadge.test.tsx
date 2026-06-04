import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ConfidenceBadge } from '../ConfidenceBadge';
import { CONFIDENCE_TOKENS, resolveConfidenceLevel, type ConfidenceLevel } from '../confidence.tokens';

afterEach(cleanup);

const LEVELS: ConfidenceLevel[] = ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'];

describe('ConfidenceBadge', () => {
  it('renders the label for every level', () => {
    for (const level of LEVELS) {
      const { unmount } = render(<ConfidenceBadge level={level} />);
      expect(screen.getByText(CONFIDENCE_TOKENS[level].label)).toBeInTheDocument();
      unmount();
    }
  });

  it('exposes the level + tooltip via aria-label (visible without a click)', () => {
    render(<ConfidenceBadge level="HIGH" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-label', expect.stringContaining('Confidence: High'));
    expect(btn).toHaveAttribute('aria-label', expect.stringContaining(CONFIDENCE_TOKENS.HIGH.tooltip));
  });

  it('toggles the tooltip on click and reflects aria-expanded', () => {
    render(<ConfidenceBadge level="LOW" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('tooltip')).toHaveTextContent(CONFIDENCE_TOKENS.LOW.tooltip);

    fireEvent.click(btn);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('appends the numeric score to the tooltip when provided', () => {
    render(<ConfidenceBadge level="MEDIUM" score={0.92} forceTooltipOpen />);
    expect(screen.getByRole('tooltip')).toHaveTextContent('(0.92)');
  });
});

describe('resolveConfidenceLevel', () => {
  it('keeps the level when a source is present', () => {
    expect(resolveConfidenceLevel({ level: 'HIGH', sourceUrl: 'https://gov.example/x' })).toBe('HIGH');
  });

  it('downgrades a sourceless HIGH/MEDIUM/LOW to UNKNOWN (never claim confidence we cannot back)', () => {
    expect(resolveConfidenceLevel({ level: 'HIGH', sourceUrl: null })).toBe('UNKNOWN');
    expect(resolveConfidenceLevel({ level: 'MEDIUM' })).toBe('UNKNOWN');
    expect(resolveConfidenceLevel({ level: 'LOW', sourceUrl: '' })).toBe('UNKNOWN');
  });

  it('leaves UNKNOWN as UNKNOWN', () => {
    expect(resolveConfidenceLevel({ level: 'UNKNOWN' })).toBe('UNKNOWN');
  });
});
