import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

/**
 * A QueryClient tuned for deterministic tests: no retries (failures surface on the
 * first attempt) and a fresh instance per call so no cache bleeds between tests.
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

/**
 * `renderHook` wrapper providing both the QueryClient and a Router (some hooks call
 * `useNavigate`). Each call builds a fresh client.
 */
export function createWrapper(): React.FC<{ children: React.ReactNode }> {
  const client = createTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}
