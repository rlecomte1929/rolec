import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SLABadge } from '../SLABadge';

afterEach(cleanup);

describe('SLABadge (W2-1)', () => {
  it('renders an em-dash when status is null/unknown', () => {
    const { container } = render(<SLABadge status={null} />);
    expect(container.textContent).toBe('—');
  });

  it('renders On track with a future day count', () => {
    render(<SLABadge status="on_track" daysUntilMove={45} />);
    expect(screen.getByText('On track')).toBeInTheDocument();
    expect(screen.getByText('· 45d')).toBeInTheDocument();
  });

  it('renders At risk', () => {
    render(<SLABadge status="at_risk" daysUntilMove={10} />);
    expect(screen.getByText('At risk')).toBeInTheDocument();
    expect(screen.getByText('· 10d')).toBeInTheDocument();
  });

  it('renders Overdue with a past day count', () => {
    render(<SLABadge status="overdue" daysUntilMove={-7} />);
    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.getByText('· 7d ago')).toBeInTheDocument();
  });

  it('omits the day suffix when daysUntilMove is missing', () => {
    render(<SLABadge status="on_track" />);
    expect(screen.getByText('On track')).toBeInTheDocument();
    expect(screen.queryByText(/·/)).toBeNull();
  });
});
