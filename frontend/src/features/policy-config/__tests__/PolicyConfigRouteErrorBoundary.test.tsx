import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyConfigRouteErrorBoundary } from '../PolicyConfigRouteErrorBoundary';

const Thrower: React.FC = () => {
  throw new Error('Simulated render failure');
};

describe('PolicyConfigRouteErrorBoundary', () => {
  it('renders fallback instead of propagating to the root boundary', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <PolicyConfigRouteErrorBoundary>
        <Thrower />
      </PolicyConfigRouteErrorBoundary>
    );
    expect(screen.getByText(/This section could not be displayed/i)).toBeInTheDocument();
    expect(screen.getByText(/Simulated render failure/)).toBeInTheDocument();
    spy.mockRestore();
  });
});
