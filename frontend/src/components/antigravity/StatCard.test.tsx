import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatCard, STAT_CARD_TOOLTIP_CLASS } from './StatCard';

describe('StatCard definition tooltip', () => {
  it('renders the definition as an overlay that does not use the native title', () => {
    const { container } = render(
      <StatCard label="Tenants" value={48} definition="Companies on the platform, excluding test tenants. · as of 1/1/2026" />,
    );
    const tooltip = screen.getByTestId('stat-card-definition');
    expect(tooltip).toHaveTextContent('Companies on the platform, excluding test tenants.');
    expect(tooltip).toHaveClass('opacity-0');
    expect(tooltip.className).toBe(STAT_CARD_TOOLTIP_CLASS);
    expect(container.firstChild).not.toHaveAttribute('title');
    expect(container.firstChild).toHaveClass('group');
    expect(container.firstChild).toHaveClass('relative');
  });
});
