import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { Badge } from './Badge';

afterEach(cleanup);

describe('Badge', () => {
  it('uses emerald for success so teal stays the accent, not a status fill', () => {
    const { container } = render(<Badge variant="success">Done</Badge>);
    expect(container.firstChild).toHaveClass('bg-emerald-50', 'text-emerald-700');
  });

  it('uses rose for error to match AppShell nav-error treatment', () => {
    const { container } = render(<Badge variant="error">Failed</Badge>);
    expect(container.firstChild).toHaveClass('bg-rose-50', 'text-rose-800');
  });
});
