import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { StatusPill } from './StatusPill';

afterEach(cleanup);

describe('StatusPill', () => {
  it('renders the provided label', () => {
    render(<StatusPill status="in-progress">In progress</StatusPill>);
    expect(screen.getByText('In progress')).toBeInTheDocument();
  });
  it('applies the teal treatment for in-progress', () => {
    render(<StatusPill status="in-progress">In progress</StatusPill>);
    expect(screen.getByText('In progress').className).toContain('text-accent-600');
  });
  it('applies the amber treatment for action', () => {
    render(<StatusPill status="action">Action needed</StatusPill>);
    expect(screen.getByText('Action needed').className).toContain('#7a5e2a');
  });
});
