import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { Skeleton } from './Skeleton';

afterEach(cleanup);

describe('Skeleton', () => {
  it('is decorative (aria-hidden) and animates', () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveAttribute('aria-hidden', 'true');
    expect(el.className).toContain('animate-pulse');
  });

  it('applies the circle variant radius and custom sizing', () => {
    const { container } = render(<Skeleton variant="circle" width="w-8" height="h-8" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('rounded-full');
    expect(el.className).toContain('w-8');
    expect(el.className).toContain('h-8');
  });
});
